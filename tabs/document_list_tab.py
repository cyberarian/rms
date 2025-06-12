import streamlit as st

def render_document_list_tab(crud_init_db, read_documents):
    st.subheader("📋 Document List")
    try:
        if crud_init_db is None:
            st.error("Document List is currently unavailable due to CRUD module import issues.")
            return
        # Initialize CRUD database
        crud_init_db()
        # Call only the read function
        read_documents()
    except Exception as e:
        st.error(f"Error in Document List: {str(e)}")
        st.error("Please check the database connection and CRUD implementation.")
    
    # Footer
    st.markdown("---")
    st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")

