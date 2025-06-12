import streamlit as st

def render_records_management_tab(crud_init_db, create_document, update_document, delete_document):
    st.subheader("📝 Records Management System")
    try:
        if crud_init_db is None:
            st.error("Records Management System is currently unavailable due to CRUD module import issues.")
            return
        
        crud_init_db()
        # Create CRUD menu
        menu = ["Create", "Update", "Delete"]
        choice = st.selectbox(
            "Select Operation",
            menu,
            key="crud_operation_records_tab" # Unique key
        )
        # Add spacing
        st.write("")
        # Display operation title
        if choice:
            st.subheader(f"{choice} Document")
        # Call CRUD functions
        if choice == "Create":
            create_document()
        elif choice == "Update":
            update_document()
        elif choice == "Delete":
            delete_document()
    except Exception as e:
        st.error(f"Error in Records Management: {str(e)}")
        st.error("Please check the CRUD implementation and database connection.")
    
    # Footer
    st.markdown("---")
    st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")

