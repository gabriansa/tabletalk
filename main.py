import streamlit as st
from sidebar import render_sidebar

# Configure the page
st.set_page_config(
    page_title="TableTalk",
    menu_items={
        'Get Help': 'mailto:hey.holodeck@gmail.com',
        'Report a bug': 'mailto:hey.holodeck@gmail.com',
        'About': 'mailto:hey.holodeck@gmail.com'
    }
)

# Get the current page from navigation and run it
page = render_sidebar()
page.run()
