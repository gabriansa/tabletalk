import streamlit as st
import pandas as pd
import json
from src.utils.llm_util import apply_transformation, apply_test_transformation
from openai import OpenAI
import tiktoken

class Field:
    def __init__(self, name, instructions, field_type):
        self.name = name
        self.instructions = instructions
        self.field_type = field_type

def update_value(key):
    """Update session state new_columns based on input changes"""
    # Extract the type and index from the key (format: "type_index")
    input_type, index = key.split('_')
    index = int(index)
    
    # Update the corresponding value in session state
    if input_type == "name":
        st.session_state.new_columns[index].name = st.session_state[key]
    elif input_type == "instructions":
        st.session_state.new_columns[index].instructions = st.session_state[key]
    elif input_type == "type":
        st.session_state.new_columns[index].field_type = st.session_state[key]

def count_tokens(text, model):
    """Count the number of tokens in a text string"""
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def estimate_cost(df, field_descriptions):
    """Estimate the cost of running transformations on the dataset"""
    # Load the instruction template
    with open('instructions.txt', 'r') as f:
        prompt_template = f.read()
    
    # Create a sample prompt with field descriptions
    sample_prompt = prompt_template.replace('{{FIELD_DESCRIPTIONS}}', json.dumps(field_descriptions, indent=2))
    
    # Count tokens in the prompt
    input_tokens_per_row = count_tokens(sample_prompt, st.secrets["MODEL"])
    output_tokens_per_row = 100  # Assuming average output is around 100 tokens
    
    # Calculate total tokens
    total_rows = len(df)
    total_input_tokens = input_tokens_per_row * total_rows
    total_output_tokens = output_tokens_per_row * total_rows
    
    # Calculate cost using provided rates
    input_cost_per_million = 0.15  # $0.15 per million tokens
    output_cost_per_million = 0.60  # $0.60 per million tokens
    
    total_input_cost = (total_input_tokens / 1_000_000) * input_cost_per_million
    total_output_cost = (total_output_tokens / 1_000_000) * output_cost_per_million
    total_cost = total_input_cost + total_output_cost
    
    return {
        'input_tokens_per_row': input_tokens_per_row,
        'output_tokens_per_row': output_tokens_per_row,
        'total_rows': total_rows,
        'total_input_tokens': total_input_tokens,
        'total_output_tokens': total_output_tokens,
        'total_cost': total_cost
    }

def validate_api_key(api_key):
    """Validate OpenAI API key"""
    try:
        client = OpenAI(api_key=api_key)
        client.models.list()
        return True
    except Exception:
        return False

@st.cache_data
def load_dataframe(file):
    """Load and cache dataframe from uploaded file"""
    try:
        df = pd.read_csv(file)
        original_rows = len(df)
        if original_rows > 50000:
            df = df.head(50000)
            st.warning(f"⚠️ Dataset has been trimmed from {original_rows:,} to 50,000 rows due to size limitations.")
        return df
    except Exception as e:
        st.error(f"Error processing file. Please check your input and try again. Error: {str(e)}")
        return None
    
# Main app layout
st.title("Transform Data")

# **Added Step-by-Step Instructions Expander**
with st.expander("How to Use This App", icon=":material/help_outline:", expanded=False):
    st.markdown("""
1. **Upload Your File (CSV only)**

2. **View Original Data**
   - Once uploaded, the original data will be displayed for your reference

3. **Configure Transformations**
   - Enter your **OpenAI API Key** that you can get from [platform.openai.com](https://platform.openai.com/)
   - Ensure you have enough credits in your OpenAI account
   - Add new columns by clicking the **"Add New Column"** button
   - For each new column:
     - **Name**: Specify the name of the new column
     - **Instructions**: Provide instructions for transforming the data
     - **Type**: Select the data type (text or number)

4. **Apply Transformations**
   - After configuring all desired columns, click on the **"Apply Transformations"** button
   - The app will process your data and provide a **Batch ID** for tracking in the status page

**Note**: *The results might take up to 24 hours to be ready and might not be accurate. LLMs can make mistakes.*

""")

st.divider()

# File upload
uploaded_file = st.file_uploader("Start by uploading your CSV file", type=['csv'])

st.divider()

if uploaded_file is not None:
    # Load the data using cached function
    df = load_dataframe(uploaded_file)
        
    if df is not None:
        # Display data info
        st.info(f"📊 Loaded dataset with {len(df):,} rows and {len(df.columns):,} columns")
        
        # Display original data
        st.subheader("Original Data (first 20 rows)")
        st.dataframe(df.head(20), height=200)

        # Show available columns
        available_columns = df.columns.tolist()
        st.pills("Columns in dataset", available_columns, disabled=True)
     
        st.divider()
        st.subheader("Start with TableTalk")

        # API Key input and validation
        col1, col2 = st.columns([6, 1])

        with col1:
            api_key = st.text_input(
                "Enter your OpenAI API Key - [Get API Key](https://platform.openai.com/api-keys)",
                type="password",
                help="""This application uses gpt-4o-mini to transform the data. 
                You'll need an OpenAI API key. To get one, go to [platform.openai.com](https://platform.openai.com/)
                and create an account. Then, navigate to API Keys section and create a new API key.
                """
            )
            st.session_state["api_key"] = None

        with col2:
            if api_key:
                if validate_api_key(api_key):
                    st.markdown("<div style='margin-top: 34px;'></div>", unsafe_allow_html=True)
                    st.write(":material/check_circle: Valid!")
                    st.session_state["api_key"] = api_key
                else:
                    st.markdown("<div style='margin-top: 34px;'></div>", unsafe_allow_html=True)
                    st.write(":material/error: Not valid!")

        # Display columns in expanders
        if "new_columns" not in st.session_state:
            st.session_state.new_columns = []

        for i, col in enumerate(st.session_state.new_columns):
            with st.expander(f"{col.name if col.name else f'Column {i + 1}'}", expanded=True):
                col1, col2, col3 = st.columns([3, 8, 1])
                
                # Column name input
                with col1:
                    new_name = st.text_input(
                        f"Column name",
                        value=col.name,
                        key=f"name_{i}",
                        on_change=update_value,
                        args=(f"name_{i}",),
                        help="This is the name of the new column in the transformed data.",
                        placeholder="New column name"
                    )

                    # radio for column type
                    field_type = st.radio(
                        "Column type", 
                        ["text", "number"], 
                        index=0, 
                        key=f"type_{i}",
                        on_change=update_value,
                        args=(f"type_{i}",),
                        help="Select what type of column this is."
                    )
                
                # Description input
                with col2:
                    new_instructions = st.text_area(
                        "Instructions",
                        value=col.instructions,
                        placeholder="Example: Calculate total by multiplying @quantity and @price",
                        key=f"instructions_{i}",
                        on_change=update_value,
                        args=(f"instructions_{i}",),
                        height=200,
                        help="This is the instructions of the new column in the transformed data."
                    )
                
                # Delete button
                with col3:
                    st.markdown("<div style='margin: 28px 0;'></div>", unsafe_allow_html=True)
                    if st.button(":material/delete:", key=f"delete_{i}", help=f"Delete column {i}"):
                        st.session_state.new_columns.pop(i)
                        st.rerun()

        # Add button
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(":material/add: New Column", help="Add Column"):
                # Add check for maximum columns
                if len(st.session_state.new_columns) >= 4:
                    st.warning("Maximum of 4 columns allowed")
                else:
                    st.session_state.new_columns.append(Field("", "", "text"))
                    st.rerun()

        # Apply Transformations button
        st.divider()

        col1, col2, _ = st.columns([1, 1, 1])
        with col1:
            # Check if API key is valid
            api_key_valid = validate_api_key(st.session_state.get('api_key'))

            apply_transformations_button = st.button(
                "Apply Transformations", 
                type="primary",
                icon=":material/bolt:",
                help="Apply the transformations to the data.",
                disabled=not st.session_state.new_columns or not all(
                    col.name and col.instructions 
                    for col in st.session_state.new_columns
                ) or not api_key_valid
            )

        with col2:
            test_button = st.button(
                "Test Single Row",
                type="primary",
                icon=":material/bolt:",
                help="Test the transformations",
                disabled=not st.session_state.new_columns or not all(
                    col.name and col.instructions 
                    for col in st.session_state.new_columns
                ) or not api_key_valid
            )

        # Estimate cost (moved outside columns)
        if st.session_state.new_columns:
            field_descriptions = [
                {
                    "field_name": col.name,
                    "instructions": col.instructions,
                    "data_type": getattr(col, 'field_type', 'text')
                }
                for col in st.session_state.new_columns
            ]
            cost_estimate = estimate_cost(df, field_descriptions)
            
            # Display cost estimation details
            st.subheader(f"Cost Estimation ${cost_estimate['total_cost']:.2f}")

        if test_button:
            try:
                # Create prompt list in the new format
                field_descriptions = [
                    {
                        "field_name": col.name,
                        "instructions": col.instructions,
                        "data_type": getattr(col, 'field_type', 'text')
                    }
                    for col in st.session_state.new_columns
                ]

                # Apply test transformation
                result, instructions = apply_test_transformation(df, field_descriptions, st.session_state.get('api_key'), st.secrets["MODEL"])

                # Display the result as a table - the result is a row of the dataframe (a pandas row)
                # Display the instructions
                if result is not None:
                    st.markdown("**Instructions**")
                    st.text(instructions)
                    st.markdown("**Test Result**")
                    st.dataframe(result.head(1), height=50)
                else:
                    st.error("Error running test transformation")
            except Exception as e:
                st.error(f"Error running test transformation: {str(e)}")

        if apply_transformations_button:
            try:
                # Create prompt list in the new format
                field_descriptions = [
                    {
                        "field_name": col.name,
                        "instructions": col.instructions,
                        "data_type": getattr(col, 'field_type', 'text')
                    }
                    for col in st.session_state.new_columns
                ]

                # Apply transformations
                batch_id = apply_transformation(st.session_state.get('api_key'), df, field_descriptions, st.secrets["MODEL"])

                # Display the API key and Batch ID
                st.info(
                    "Please save these details to check your transformation status. If lost, you won't be able to check the status and retrieve the transformed data:\n\n"
                    f"**API Key**: {st.session_state.get('api_key')}\n\n"
                    f"**Batch ID**: {batch_id}\n\n"
                    "**Note**: *Processing can take up to 24 hours.*"
                )

                # Add a button to download a json file with the API key and Batch ID ({"api_key": dummy_api_key, "batch_id": dummy_batch_id})
                st.download_button(
                    "Download API Key and Batch ID",
                    json.dumps({"api_key": st.session_state.get('api_key'), "batch_id": batch_id}),
                    file_name="api_key_and_batch_id.json",
                    mime="application/json"
                )
            except Exception as e:
                st.error(f"Error running transformations: {str(e)}")
        
        # Simplified Download Configuration button
        st.divider()
        col1, col2 = st.columns([3, 2])
        with col1:
            config_data = {
                "columns": [
                    {
                        "name": col.name,
                        "instructions": col.instructions,
                        "field_type": col.field_type
                    }
                    for col in st.session_state.new_columns
                ]
            }
            st.download_button(
                ":material/download: Download Configuration",
                data=json.dumps(config_data, indent=2),
                file_name="tabletalk_config.json",
                mime="application/json",
                help="Download current configuration"
            )

            # Initialize the processed_file_hash in session state if it doesn't exist
            if 'processed_file_hash' not in st.session_state:
                st.session_state.processed_file_hash = None

            config_file = st.file_uploader(
                "Upload Configuration",
                type=['json'],
                help="Upload a previously saved configuration",
                key="config_uploader"
            )
            
            if config_file is not None:
                # Get the current file contents
                current_file_contents = config_file.getvalue()
                # Create a simple hash of the file contents
                current_hash = hash(current_file_contents)
                
                # Only process if we haven't seen this exact file before
                if current_hash != st.session_state.processed_file_hash:
                    try:
                        # Reset file pointer to start
                        config_file.seek(0)
                        config_data = json.load(config_file)
                        st.session_state.new_columns = [
                            Field(
                                col["name"],
                                col["instructions"],
                                col["field_type"]
                            )
                            for col in config_data["columns"]
                        ]
                        # Store the hash of the processed file
                        st.session_state.processed_file_hash = current_hash
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error loading configuration: {str(e)}")