import streamlit as st
from src.utils.llm_util import check_batch_status

st.title("Check Status")

api_key = st.text_input(
    "API Key", 
    type="password", 
    placeholder="Enter your API key"
)
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
    done, df = check_batch_status(batch_id, api_key)

    if not done:
        st.warning("Batch not done yet. Check back later (it can take up to 24 hours for a batch to complete)")
    elif done and df is None:
        st.warning("Batch failed. Check the API key and batch ID.")
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
