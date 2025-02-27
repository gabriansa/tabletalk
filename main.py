import streamlit as st
from sidebar import render_sidebar

# Configure the page
st.set_page_config(
    page_title="TableTalk",
    menu_items={
        'Get Help': f"mailto:{st.secrets.SUPPORT_EMAIL}",
        'Report a bug': f"mailto:{st.secrets.SUPPORT_EMAIL}",
        'About': f"mailto:{st.secrets.SUPPORT_EMAIL}"
    }
)

# Get the current page from navigation and run it
page = render_sidebar()
page.run()
