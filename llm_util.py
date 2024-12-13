import json
import os
from litellm import completion, completion_cost
import pandas as pd
from pprint import pprint
import streamlit as st


def extract_columns_from_prompt(prompt, available_columns):
    """Extract column names from prompt that start with @"""
    columns = []
    for col in available_columns:
        if f"@{col}" in prompt:
            columns.append(col)
    return columns


def apply_transformation(row, field_descriptions, available_columns):
    """Apply the transformation to a single row and return multiple values"""
    
    # Create a deep copy of field_descriptions to avoid modifying the original
    field_descriptions = json.loads(json.dumps(field_descriptions))
    
    # Replace @col_name with row[col_name] in field_descriptions[i]['description']
    for field in field_descriptions:
        instructions = field['instructions']
        for col in available_columns:
            instructions = instructions.replace(f'@{col}', str(row[col]))
        field['instructions'] = instructions

    result, response = process_llm_request(field_descriptions)
    
    # Get the cost from the LLM response
    cost = completion_cost(completion_response=response) if response else 0
    
    return result, cost


def process_llm_request(field_descriptions, max_retries=3):
    """Process the LLM request with error handling and retries"""
    for attempt in range(max_retries):
        try:
            # Read prompt template
            with open('instructions.txt', 'r') as f:
                prompt_template = f.read()
            
            # Convert field descriptions to formatted string
            field_desc_str = json.dumps(field_descriptions, indent=2)
            
            # Replace placeholder in template
            prompt = prompt_template.replace('{{FIELD_DESCRIPTIONS}}', field_desc_str)
            
            # Use API key from session state
            os.environ["ANTHROPIC_API_KEY"] = st.session_state.get("api_key")
            response = completion(
                model="anthropic/claude-3-5-sonnet-20240620",
                messages=[
                    {"role": "user", "content": f"{prompt}"}
                ]
            )
            
            # Extract JSON from between <json_response> tags
            content = response.choices[0].message.content.strip()
            json_start = content.find('<json_response>') + len('<json_response>')
            json_end = content.find('</json_response>')
            json_str = content[json_start:json_end].strip()
            
            # Parse JSON response and convert to required format
            result = json.loads(json_str)
            
            return result, response  # Return both the parsed result and the full response object
            
        except Exception as e:
            if attempt < max_retries - 1:  # Don't show error if we still have retries left
                continue
            else:
                st.toast(f"Error in LLM request: {str(e)}", icon=":material/error:")
                return None, None
