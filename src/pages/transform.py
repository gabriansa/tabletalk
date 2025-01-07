import streamlit as st
import pandas as pd
import json
from src.utils.llm_util import apply_transformation, apply_test_transformation, estimate_cost
import anthropic

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

# Main app layout
st.title("Transform Data")

# **Added Step-by-Step Instructions Expander**
with st.expander("📖 How to Use This App", expanded=False):
    st.markdown("""
### Step-by-Step Guide

1. **Upload Your File**
   - Click on the **"Start by uploading your CSV or Excel file"** button.
   - Supported formats: `.csv`, `.xlsx`.

2. **View Original Data**
   - Once uploaded, the original data will be displayed for your reference.

3. **Configure Transformations**
   - In the **"Start with TableTalk"** section, enter your **Anthropic API Key**.
   - Add new columns by clicking the **"Add New Column"** button.
   - For each new column:
     - **Name**: Specify the name of the new column.
     - **Instructions**: Provide instructions for transforming the data (e.g., calculations or data manipulations).
     - **Type**: Select the data type (`text` or `number`).

4. **Apply Transformations**
   - After configuring all desired columns, click on the **"Apply Transformations"** button.
   - The app will process your data and provide a **Batch ID** for tracking.

5. **Download Configuration**
   - You can download your current configuration for future use.
   - To reuse a configuration, upload the previously saved JSON file.

6. **Estimate Cost**
   - An estimated cost for the transformation will be displayed based on your configurations.

**Note**: Ensure that all required fields are filled out and a valid API key is provided before applying transformations.

""")

st.divider()

# File upload
uploaded_file = st.file_uploader("Start by uploading your CSV or Excel file", type=['csv', 'xlsx'])

st.divider()

if uploaded_file is not None:
    # Load the data
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        df = None
        st.error(f"Error processing file. Please check your input and try again. Error: {str(e)}")
        
    if df is not None:
        # Display original data
        st.subheader("Original Data")
        st.dataframe(df, height=200)

        # Show available columns into pills st.pills https://docs.streamlit.io/develop/api-reference/widgets/st.pills
        available_columns = df.columns.tolist()
        st.pills("Columns in dataset", available_columns, disabled=True)

        
        st.divider()
        st.subheader("Start with TableTalk")

        # API Key input and validation
        col1, col2 = st.columns([6, 1])

        with col1:
            api_key = st.text_input(
                "Enter your Anthropic API Key - [Get API Key](https://console.anthropic.com/)",
                type="password",
                help="""This application uses Anthropic's LLMs to transform your data. 
                You'll need an Anthropic API key. To get one, go to [console.anthropic.com](https://console.anthropic.com/)
                and create an account. Then, navigate to API Keys section and create a new API key.
                """
            )

        with col2:
            if api_key:
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    client.models.list()
                    st.markdown("<div style='margin-top: 34px;'></div>", unsafe_allow_html=True)
                    st.write(":material/check_circle: Valid!")
                    
                except Exception:
                    st.markdown("<div style='margin-top: 34px;'></div>", unsafe_allow_html=True)
                    st.write(":material/error: Not valid!")
                    
        if api_key:
            st.session_state["api_key"] = api_key

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
                        help="This is the name of the new column in the transformed data."
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
            api_key_valid = False
            if api_key:
                try:
                    client = anthropic.Anthropic(api_key=api_key)
                    client.models.list()
                    api_key_valid = True
                except Exception:
                    api_key_valid = False

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
                "Test Single Row (Free)",
                type="primary",
                icon=":material/bolt:",
                help="Test the transformations",
                disabled=not st.session_state.new_columns or not all(
                    col.name and col.instructions 
                    for col in st.session_state.new_columns
                )
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
            estimated_cost = estimate_cost(df, field_descriptions)
            st.text(f"Estimated cost: ${estimated_cost:.2f}")

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
                result, instructions = apply_test_transformation(df, field_descriptions, st.secrets["GROQ_API_KEY"])

                # Display the result as a table - the result is a row of the dataframe (a pandas row)
                # Display the instructions
                if result is not None:
                    st.dataframe(result.head(1), height=50)
                    st.text(instructions)
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
                batch_id = apply_transformation(st.session_state.get('api_key'), df, field_descriptions)

                # Display the API key and Batch ID
                st.info(
                    "Please save these details to check your transformation status. If lost, you won't be able to check the status and retrieve the transformed data:\n\n"
                    f"**API Key**: {st.session_state.get('api_key')}\n\n"
                    f"**Batch ID**: {batch_id}\n\n"
                    "*Note*: Processing can take up to 24 hours."
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
            config_file = st.file_uploader(
                "Upload Configuration",
                type=['json'],
                help="Upload a previously saved configuration",
                key="config_uploader"
            )
            if config_file is not None:
                try:
                    config_data = json.load(config_file)
                    st.session_state.new_columns = [
                        Field(
                            col["name"],
                            col["instructions"],
                            col["field_type"]
                        )
                        for col in config_data["columns"]
                    ]
                    st.rerun()
                except Exception as e:
                    st.error(f"Error loading configuration: {str(e)}")