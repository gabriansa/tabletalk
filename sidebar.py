import streamlit as st

def render_sidebar():
    """Render the navigation sidebar"""
    # st.logo("assets/logo.svg", size="large")
        
    # Define pages
    pages = [
        st.Page(
            "src/pages/homepage.py",
            title="Home",
            icon=":material/home:",
            default=True
        ),
        st.Page(
            "src/pages/transform.py",
            title="Transform Data",
            icon=":material/transform:",
        ),
        st.Page(
            "src/pages/status.py",
            title="Check Status",
            icon=":material/check_circle:",
        ),
    ]

    # Set up navigation
    pg = st.navigation(pages)

    # Custom CSS to reduce sidebar width and prevent resize animation
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"] {
                width: 200px !important;
            }
            [data-testid="stSidebar"][aria-expanded="true"] {
                min-width: 200px !important;
                max-width: 200px !important;
                width: 200px !important;
            }
            .support-link {
                position: fixed;
                bottom: 20px;
                left: 20px;
                font-size: 0.8em;
            }
        </style>
        """,
        unsafe_allow_html=True
    )
    
    # Add support email link at the fixed bottom position
    st.sidebar.markdown(f'<div class="support-link" style="text-align: center;">Need help? <a href="mailto:{st.secrets.SUPPORT_EMAIL}">Contact Us</a></div>', unsafe_allow_html=True)
        
    return pg