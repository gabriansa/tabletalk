import streamlit as st
import pandas as pd
from llm_util import apply_transformation
import time  # Add this at the top with other imports

# Set page config
st.set_page_config(
    page_title="TableTalk",
    layout="centered"
)

# Add this after imports
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
st.markdown("<h1 style='text-align: center'>TableTalk</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center'>Transform your data using natural language instructions</p>", unsafe_allow_html=True)

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
        
        # Display original data
        st.subheader("Original Data")
        st.dataframe(df, height=200)

        # Show available columns into pills st.pills https://docs.streamlit.io/develop/api-reference/widgets/st.pills
        available_columns = df.columns.tolist()
        st.pills("Columns in dataset", available_columns, disabled=True)

        
        st.divider()
        st.subheader("Start with TableTalk")
        
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

        # Add button moved below expanders
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(":material/add:", help="Add Column"):
                # Add check for maximum columns
                if len(st.session_state.new_columns) >= 4:
                    st.warning("Maximum of 4 columns allowed")
                else:
                    st.session_state.new_columns.append(Field("", "", "text"))
                    st.rerun()

        # API Key input
        with st.expander("🔑 API Key Configuration", expanded=not st.session_state.get("api_key")):
            st.info("""This application uses Anthropic's Claude 3.5 Sonnet model. 
            To use this app, you'll need an Anthropic API key. You can get one by:
            1. Going to [console.anthropic.com](https://console.anthropic.com/)
            2. Creating an account
            3. Navigating to API Keys section
            4. Creating a new API key
            """)
            
            api_key = st.text_input(
                "Enter your Anthropic API Key",
                type="password",
                value=st.session_state.get("api_key", ""),
                help="Your API key will be stored only for this session"
            )
            
            if api_key:
                st.session_state["api_key"] = api_key

        run_button = st.button(
            "Apply Transformations :material/bolt:", 
            type="primary",
            help="Apply the transformations to the data.",
            disabled=not st.session_state.new_columns or not all(
                col.name and col.instructions 
                for col in st.session_state.new_columns
            ) or not st.session_state.get("api_key")
        )
        if run_button:
            # Create prompt list in the new format
            field_descriptions = [
                {
                    "field_name": col.name,
                    "instructions": col.instructions,
                    "data_type": getattr(col, 'field_type', 'text')
                }
                for col in st.session_state.new_columns
            ]

            new_column_names = [col.name for col in st.session_state.new_columns]
            
            # Create progress bar
            col1, col2 = st.columns([4, 1])
            with col1:
                progress_bar = st.progress(0)
            with col2:
                spinner_placeholder = st.empty()

            # Initialize empty lists to store results and costs
            results = []
            costs = []
            
            # Initialize timing and cost variables
            start_time = time.time()
            times_per_row = []
            total_cost = 0
            
            # Create placeholder containers for metrics
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                time_metric = st.empty()
            with metric_col2:
                cost_metric = st.empty()
            with metric_col3:
                total_cost_metric = st.empty()
            
            # Wrap the processing loop in a spinner
            with spinner_placeholder.container():
                with st.spinner('Processing...'):
                    # Process each row with progress update
                    for index, row in df.iterrows():
                        row_start_time = time.time()
                        result, row_cost = apply_transformation(row, field_descriptions, available_columns)
                        
                        results.append(result)
                        costs.append(row_cost)
                        total_cost += row_cost
                        
                        # Calculate time taken for this row
                        row_time = time.time() - row_start_time
                        times_per_row.append(row_time)
                        
                        # Calculate averages
                        avg_time_per_row = sum(times_per_row) / len(times_per_row)
                        avg_cost_per_row = total_cost / (index + 1)
                        
                        # Calculate estimated remaining values
                        rows_remaining = len(df) - (index + 1)
                        estimated_time_remaining = rows_remaining * avg_time_per_row
                        estimated_remaining_cost = rows_remaining * avg_cost_per_row
                        estimated_total_cost = total_cost + estimated_remaining_cost
                        
                        # Convert seconds to HH:MM:SS format
                        hours = int(estimated_time_remaining // 3600)
                        minutes = int((estimated_time_remaining % 3600) // 60)
                        seconds = int(estimated_time_remaining % 60)
                        time_string = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        
                        # Update progress bar and metrics
                        progress = (index + 1) / len(df)
                        progress_bar.progress(
                            progress, 
                            f"Processing row {index + 1} of {len(df)}. "
                        )
                        time_metric.metric(
                            "Time remaining", 
                            f"{time_string}", 
                            delta_color="normal"
                        )
                        cost_metric.metric(
                            "Cost so far", 
                            f"${total_cost:.2f}", 
                            delta_color="normal"
                        )
                        total_cost_metric.metric(
                            "Estimated total cost", 
                            f"${estimated_total_cost:.2f}", 
                            delta_color="normal"
                        )
            
            # After processing display final cost metrics
            st.info(f"""
                **Processing Complete**
                - Total Cost: ${total_cost:.2f}
                - Average Cost per Row: ${total_cost/len(df):.2f}
                - Number of Rows Processed: {len(df)}
            """)
            
            # Create result dataframe from collected results
            result_df = pd.DataFrame(results, columns=new_column_names)
            
            # Add new columns to the dataframe
            for col in new_column_names:
                df[col] = result_df[col]
            
            # Display transformed data
            st.subheader("Transformed Data")
            st.dataframe(df)
            
            # Download button for transformed data
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download transformed data",
                data=csv,
                file_name="transformed_data.csv",
                mime="text/csv"
            )
    
    except Exception as e:
        st.error(f"Error processing file. Please check your input and try again. Error: {str(e)}")
