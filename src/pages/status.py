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
            st.info("Batch completed successfully. Here are the results:")
            st.dataframe(df)
            # Add a button to download the dataframe as a CSV
            st.download_button(
                "Download CSV",
                df.to_csv(index=False),
                "data.csv",
                "text/csv",
                key="download-csv"
            )

        # Show the batch response in a collapsible section
        with st.expander("Show raw batch response", expanded=False):
            st.write(batch)

    except Exception as e:
        st.error(f"Error retrieving batch status. Check that the API key and batch ID are correct.")