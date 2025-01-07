import streamlit as st

# Main welcome header with custom styling
st.markdown("""
    <h1 style='text-align: center; margin-bottom: ;'>
        TableTalk
    </h1>
""", unsafe_allow_html=True)

st.divider()
# To get started review the documentation and then use the simulator to run your first simulation.
st.markdown("""
    <p style='text-align: center;'>
        Transform your data using natural language instructions
    </p>
""", unsafe_allow_html=True)


# Call-to-action section
col1, col2, col3 = st.columns([1.5,2,1.5])
with col2:   
    if st.button("Get Started", 
             use_container_width=True,
             type="primary",
             icon=":material/rocket_launch:",
             ):
        st.switch_page("src/pages/transform.py")