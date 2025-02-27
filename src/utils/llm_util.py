import json
from copy import deepcopy
import pandas as pd
from openai import OpenAI
from pydantic import BaseModel
from typing import Union, List
import io

class Response(BaseModel):
    field_name: str
    reasoning: str
    value: Union[str, float, int]

class ResponseList(BaseModel):
    responses: List[Response]

def _prepare_batch_requests(df, field_descriptions, model):
    """Generate the batch of requests in OpenAI batch API format"""
    
    available_columns = df.columns.tolist()

    with open('instructions.txt', 'r') as f:
        prompt_template = f.read()
    
    jsonl_requests = []
    
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
        
        # Create the OpenAI batch request in JSONL format
        jsonl_request = {
            "custom_id": f"{index}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "response_list",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "responses": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "field_name": {"type": "string"},
                                            "reasoning": {"type": "string"},
                                            "value": {
                                                "type": ["string", "number"]
                                            }
                                        },
                                        "required": ["field_name", "reasoning", "value"],
                                        "additionalProperties": False
                                    }
                                }
                            },
                            "required": ["responses"],
                            "additionalProperties": False
                        },
                        "strict": True
                    }
                }
            }
        }
        jsonl_requests.append(jsonl_request)
    
    # Return the JSONL requests directly instead of writing to a file
    return jsonl_requests

def _submit_batch_requests(api_key, batch_requests):
    client = OpenAI(api_key=api_key)
    
    # Create a string with each JSON object on a new line
    jsonl_content = "\n".join(json.dumps(request) for request in batch_requests)
    
    # Create a file-like object from the string
    jsonl_file = io.BytesIO(jsonl_content.encode('utf-8'))
    
    # Submit the batch directly using the file-like object
    batch_input_file = client.files.create(
        file=jsonl_file,
        purpose="batch"
    )
    
    batch_input_file_id = batch_input_file.id
    request = client.batches.create(
        input_file_id=batch_input_file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={
            "description": "nightly eval job"
        }
    )
    batch_id = request.id
    return batch_id

def apply_transformation(api_key, df, field_descriptions, model):
    """Apply the transformation to a single row and return multiple values"""
    batch_requests = _prepare_batch_requests(df, field_descriptions, model)
    batch_id = _submit_batch_requests(api_key, batch_requests)
    return batch_id

def _parse_batch_response(response_content):
    """Helper function to parse batch response content"""
    try:
        # Parse the JSONL response
        response_data = json.loads(response_content)
        
        # Extract the actual message content
        message_content = response_data['response']['body']['choices'][0]['message']['content']
        
        # Parse the JSON string into ResponseList
        return ResponseList.model_validate_json(message_content)
    except Exception as e:
        print(f"Error parsing response: {e}")
        return None

def check_batch_status(batch_id, api_key):
    client = OpenAI(api_key=api_key)
    batch = client.batches.retrieve(batch_id=batch_id)
    

    if batch.status == 'completed' and batch.output_file_id is not None:
        # Download the output file
        file_response = client.files.content(batch.output_file_id)
        
        # Initialize dict to store data for DataFrame
        data = {}
        field_names = set()
        
        # Process each line in the JSONL response
        for line in file_response.text.strip().split('\n'):
            response = _parse_batch_response(line)
            if response:
                custom_id = json.loads(line)['custom_id']
                data[custom_id] = {'row_number': custom_id}
                
                # Add each field_name: value pair to the row
                for field in response.responses:
                    field_names.add(field.field_name)
                    data[custom_id][field.field_name] = field.value
        
        # Ensure all rows have all columns (fill with None for missing values)
        for row_data in data.values():
            for field_name in field_names:
                if field_name not in row_data:
                    row_data[field_name] = None
        
        # Convert results to DataFrame
        results_df = pd.DataFrame(list(data.values()))
        return True, results_df, batch
    else:
        return False, None, batch
    
def apply_test_transformation(df, field_descriptions, api_key, model):
    """Apply the transformation to a random row from the dataset"""
    # Select a random row
    random_row = df.sample(n=1)
    
    # Get the available columns
    available_columns = df.columns.tolist()
    
    # Prepare the request
    batch_requests = _prepare_batch_requests(random_row, field_descriptions, model)
    messages = batch_requests[0]['body']['messages']
    
    # Setup client
    client = OpenAI(api_key=api_key)


    completion = client.beta.chat.completions.parse(
        model=model,
        messages=messages,
        response_format=ResponseList
    )
    
    response_text = completion.choices[0].message.parsed

    # Get the row based on the custom_id
    row_idx = int(batch_requests[0]['custom_id'])
    row = df.loc[[row_idx]].copy()  # Create an explicit copy

    # Add the new columns to the row
    for new_column in response_text.responses:  # Access the 'responses' attribute
        row.loc[:, new_column.field_name] = new_column.value

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