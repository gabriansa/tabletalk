import streamlit as st
from src.utils.llm_util import check_batch_status
from openai import OpenAI


def validate_api_key(api_key):
    """Validate OpenAI API key"""
    try:
        client = OpenAI(api_key=api_key)
        client.models.list()
        return True
    except Exception:
        return False


st.title("Check Status")

col1, col2 = st.columns([6, 1])

with col1:
    api_key = st.text_input(
        "API Key", 
        type="password", 
        placeholder="Enter your API key"
    )

with col2:
    if api_key:
        if validate_api_key(api_key):
            st.markdown("<div style='margin-top: 34px;'></div>", unsafe_allow_html=True)
            st.write(":material/check_circle: Valid!")
        else:
            st.markdown("<div style='margin-top: 34px;'></div>", unsafe_allow_html=True)
            st.write(":material/error: Not valid!")
        

# Add API key validation
batch_id = st.text_input(
    "Batch ID", 
    placeholder="Enter your batch ID"
)

# Add button that's enabled only when both fields have values
check_status_button = st.button(
    "Check Status", 
    type="primary",
    icon=":material/check_circle:",
    disabled=not (batch_id and api_key),
)

if check_status_button:
    try:
        done, df, batch = check_batch_status(batch_id, api_key)

        if not done:
            st.info(f"Status: **{batch.status}**. Check back later (it can take up to 24 hours for a batch to complete)", icon=":material/info:")
        elif done and df is not None:
            # Calculate the percentage of non-null values for each column
            non_null_percentages = df.count() / len(df) * 100
            
            # Separate columns with high completion rate (e.g., >80%) from hallucinated ones
            # Exclude row_number from the percentage calculation
            columns_to_check = [col for col in df.columns if col != 'row_number']
            main_columns = [col for col in columns_to_check if non_null_percentages[col] > 80]
            hallucinated_columns = [col for col in columns_to_check if non_null_percentages[col] <= 80]
            
            # Always include row_number in main_df
            main_df = df[['row_number'] + main_columns]

            st.info("Batch completed successfully!", icon=":material/check_circle:")

            st.divider()
            with st.expander("Show main results", expanded=False):
                st.dataframe(main_df)
            
            # Download button for main results
            st.download_button(
                "Download Main Results CSV",
                main_df.to_csv(index=False),
                "main_results.csv",
                "text/csv",
                key="download-main-csv"
            )
            st.divider()

            # Show hallucinated fields if they exist
            st.warning("The following results may contain hallucinated fields (columns with sparse data):")
            with st.expander("Show hallucinated results", expanded=False):  
                st.dataframe(df)
            
            # Download button for hallucinated results
            st.download_button(
                "Download Hallucinated Results CSV",
                df.to_csv(index=False),
                "hallucinated_results.csv",
                "text/csv",
                key="download-hallucinated-csv"
            )
            st.divider()

        # Show the batch response in a collapsible section
        with st.expander("Show raw batch response", expanded=False):
            st.write(batch)


    except Exception as e:
        st.error(f"Error retrieving batch status. Check that the API key and batch ID are correct.")
        st.write(e)