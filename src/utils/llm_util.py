import json
import anthropic
import litellm
from litellm import completion
import random
from copy import deepcopy
from anthropic.types.messages.batch_create_params import Request
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
import pandas as pd


def _prepare_batch_requests(df, field_descriptions):
    """Generate the batch of requests"""
    
    available_columns = df.columns.tolist()

    with open('instructions.txt', 'r') as f:
        prompt_template = f.read()

    batch_requests = []
    raw_prompts = []
    for index, row in df.iterrows():
        # Create a deep copy of field_descriptions to avoid modifying the original
        fields = deepcopy(field_descriptions)
        
        # Replace @col_name with row[col_name] in each field's description
        for field in fields:
            instructions = field['instructions']
            for col in available_columns:
                # Convert the value to a simple string without Series metadata
                instructions = instructions.replace(f'@{col}', str(row[col].item() if hasattr(row[col], 'item') else row[col]))
            field['instructions'] = instructions
        
        # Create the prompt with the processed field descriptions
        prompt = prompt_template.replace('{{FIELD_DESCRIPTIONS}}', json.dumps(fields, indent=2))
        
        # Create the Request object
        request = Request(
            custom_id=f"{index}",
            params=MessageCreateParamsNonStreaming(
                model="claude-3-5-sonnet-20240620",
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
        )
        batch_requests.append(request)
        raw_prompts.append(prompt)
    
    return batch_requests, raw_prompts

def _submit_batch_requests(api_key, batch_requests):
    client = anthropic.Anthropic(api_key=api_key)
    message_batch = client.messages.batches.create(requests=batch_requests)
    batch_id = message_batch.id
    return batch_id
    
def estimate_cost(df, field_descriptions):
    """Estimate the total cost for a batch of requests using litellm"""    

    batch_requests, raw_prompts = _prepare_batch_requests(df, field_descriptions)

    total_cost = 0
    for index, request in enumerate(batch_requests):
        # Extract the prompt from the request
        prompt = raw_prompts[index]
        
        # Use litellm's completion_cost to estimate the cost
        # Assuming an average completion length of 500 tokens for estimation
        estimated_cost = litellm.completion_cost(
            model="anthropic/claude-3-5-sonnet-20240620",
            prompt=prompt,
            completion=" " * 500  # Rough estimation for completion length
        )
        total_cost += estimated_cost
    
    return total_cost

def apply_transformation(api_key, df, field_descriptions):
    """Apply the transformation to a single row and return multiple values"""

    # 1. Generate the batch of requests
    batch_requests, raw_prompts = _prepare_batch_requests(df, field_descriptions)

    # 2. Submit the batch of requests
    batch_id = _submit_batch_requests(api_key, batch_requests)

    # 3. Return the batch ID
    return batch_id

def check_batch_status(batch_id, api_key):
    try:
        client = anthropic.Anthropic(api_key=api_key)
        batch = client.messages.batches.retrieve(batch_id)
        
        if batch.processing_status == 'ended':
            # Initialize dict to store data for DataFrame
            data = {}
            field_names = set()  # To keep track of all possible field names
            
            # Process all results
            for result in client.messages.batches.results(batch_id):
                # Initialize empty row data with the ID
                data[result.custom_id] = {'row_number': result.custom_id}
                
                if result.result.type == "succeeded":
                    message_content = result.result.message.content[0].text
                    new_columns = get_new_columns(message_content)
                    
                    if new_columns:
                        # Add each field_name: value pair to the row
                        for column in new_columns:
                            field_names.add(column['field_name'])
                            data[result.custom_id][column['field_name']] = column['value']
                else:
                    print(f"Request {result.custom_id} failed with status: {result.result.type}")
                    if result.result.type == "errored":
                        print(f"Error details: {result.result.error}")
            
            # Ensure all rows have all columns (fill with None for missing values)
            for row_data in data.values():
                for field_name in field_names:
                    if field_name not in row_data:
                        row_data[field_name] = None
            
            # Convert results to DataFrame
            results_df = pd.DataFrame(list(data.values()))
            return True, results_df
        else:
            return False, None
    
    except Exception as e:
        print(f"Error checking batch status: {e}")
        return False, None

def get_new_columns(response_text):
    """Get the new columns from the response text"""
    try:
        # 1. Try to get the response between ```json and ```
        start_index = response_text.find('```json') + len('```json')
        end_index = response_text.find('```', start_index)  # Start searching after the start_index
        json_response = response_text[start_index:end_index].strip()  # Add strip() to remove whitespace
        if json_response:  # Only try to parse if we have content
            new_columns = json.loads(json_response)
            return new_columns
    except Exception as e:
        return None

def apply_test_transformation(df, field_descriptions, api_key, max_retries=3):
    """Apply the transformation to a random row from the dataset"""
    # Select a random row
    random_row = df.sample(n=1)
    
    # Get the available columns
    available_columns = df.columns.tolist()
    
    # Prepare the request
    batch_requests, _ = _prepare_batch_requests(random_row, field_descriptions)
    messages = random.choice(batch_requests)['params']['messages']
    
    # Try up to max_retries times
    for attempt in range(max_retries):
        try:    
            response = completion(
                model="groq/llama-3.3-70b-versatile",
                api_key=api_key,
                messages=messages,
            )
            response_text = response.choices[0].message.content

            new_columns = get_new_columns(response_text)
            if new_columns is None:
                raise ValueError("Failed to parse response JSON")

            # Get the row based on the custom_id
            row_idx = int(batch_requests[0]['custom_id'])
            row = df.loc[[row_idx]].copy()  # Create an explicit copy

            # Add the new columns to the row
            for new_column in new_columns:
                row.loc[:, new_column['field_name']] = new_column['value']

            # get the instructions for the transformation
            # Create a deep copy of field_descriptions to avoid modifying the original
            fields = deepcopy(field_descriptions)
            
            # Replace @col_name with row[col_name] in each field's description
            for field in fields:
                instructions = field['instructions']
                for col in available_columns:
                    # Convert the value to a simple string without Series metadata
                    instructions = instructions.replace(f'@{col}', str(row[col].item() if hasattr(row[col], 'item') else row[col]))
                field['instructions'] = instructions

            try:
                instructions = fields

                instructions_text = ""
                for instr in instructions:
                    instructions = instr['instructions']
                    col_name = instr['field_name']
                    # add a row like this -> col_name: instructions
                    instr_text = f"{col_name}: {instructions}"
                    instructions_text += instr_text + "\n"
            except Exception as e:
                instructions_text = None

            return row, instructions_text

        except Exception as e:
            if attempt < max_retries - 1:  # If not the last attempt
                print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                continue
            else:  # Last attempt failed
                print(f"All {max_retries} attempts failed. Last error: {e}")
                return None, None
