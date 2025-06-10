import streamlit as st
from typing import Any
import time
from CRUD_st import create_document, read_documents, update_document, delete_document, init_db as crud_init_db
from rag_chain import get_rag_chain
from vectorstore_manager import initialize_or_load_vectorstore

def render_chat_interface(llm: Any):
    """Display the main chat interface with the new tab structure"""
    # Add logo
    col1, col2, col3 = st.columns([1,100,1])
    with col2:
        st.image("assets/logoHKI.png", width=150)
    
    # Create main tabs
    main_tabs = st.tabs([
        "💬 Chat & Search",
        "📋 Document Center",
        "ℹ️ Help & Info"
    ])
    
    # Chat & Search Tab
    with main_tabs[0]:
        chat_search_tabs = st.tabs([
            "🤖 AI Assistant",
            "🔍 Quick Search"
        ])
        
        # AI Assistant Tab
        with chat_search_tabs[0]:
            # Model selection inside chatbot tab            # Model info display
            st.info("Using llama-4-maverick-17b-128e-instruct model for AI assistance")
            
            # Add a greeting message
            if not st.session_state.get('uploaded_file_names'):
                st.info("👋 Welcome to HKI Records Management System")
            
            # Initialize chat history
            if 'chat_history' not in st.session_state:
                st.session_state.chat_history = []
            
            # Chat input form
            with st.form(key='chat_form'):
                prompt = st.text_input("Enter your question about the documents", key='question_input')
                submit_button = st.form_submit_button("Submit Question")
            
            # Display chat history
            for q, a in st.session_state.chat_history:
                with st.container():
                    st.info(f"❓ **Question:** {q}")
                    st.markdown(a)
                    st.divider()
            
            # Process new questions
            if submit_button and prompt:
                try:
                    if not st.session_state.get('vectorstore'):
                        st.session_state.vectorstore = initialize_or_load_vectorstore()
                    
                    vectorstore = st.session_state.vectorstore
                    if len(vectorstore.get()['ids']) > 0:
                        with st.spinner('Searching through documents...'):
                            start = time.process_time()
                            qa_chain = get_rag_chain(llm, vectorstore)
                            response = qa_chain.invoke({'query': prompt})
                            elapsed_time = time.process_time() - start
                            
                            st.session_state.chat_history.append((prompt, response['result']))
                            st.write("💡 **Latest Answer:**")
                            st.markdown(response['result'])
                            st.caption(f"⏱️ Response time: {elapsed_time:.2f} seconds")
                            st.rerun()
                    else:
                        st.warning("No documents found. Please ask an admin to upload some documents.")
                except Exception as e:
                    st.error(f"Error processing question: {str(e)}")
            
            # Clear chat history button
            if st.session_state.chat_history and st.button("Clear Chat History"):
                st.session_state.chat_history = []
                st.rerun()
        
        # Quick Search Tab
        with chat_search_tabs[1]:
            st.markdown("""
            ### 🔍 Quick Document Search
            Search through your documents using keywords or phrases.
            """)
            search_query = st.text_input("Enter search terms")
            if search_query:
                st.info("Search functionality coming soon!")
    
    # Document Center Tab
    with main_tabs[1]:
        doc_center_tabs = st.tabs([
            "📝 Records Management",
            "📋 Document List"
        ])
        
        with doc_center_tabs[0]:
            try:
                st.subheader("Records Management")
                if crud_init_db:
                    crud_init_db()
                    menu = ["Create", "Update", "Delete"]
                    choice = st.selectbox("Select Operation", menu, key="crud_operation")
                    
                    st.write("")
                    if choice == "Create":
                        create_document()
                    elif choice == "Update":
                        update_document()
                    elif choice == "Delete":
                        delete_document()
                else:
                    st.error("Records Management is currently unavailable")
            except Exception as e:
                st.error(f"Error in Records Management: {str(e)}")
        
        with doc_center_tabs[1]:
            try:
                st.subheader("Document List")
                if crud_init_db:
                    crud_init_db()
                    read_documents()
                else:
                    st.error("Document List is currently unavailable")
            except Exception as e:
                st.error(f"Error in Document List: {str(e)}")
    
    # Help & Info Tab
    with main_tabs[2]:
        help_info_tabs = st.tabs([
            "❓ User Guide",
            "📚 Resources",
            "ℹ️ About"
        ])
        
        with help_info_tabs[0]:
            st.subheader("📝 User Guide")
            st.markdown("""
            #### Using the Chat Interface
            1. Select an AI model from the dropdown
            2. Type your question in the text box
            3. Click Submit to get your answer
            4. View document references in the response
            
            #### Managing Documents
            1. Use the Document Center for all document operations
            2. Upload new documents through the admin panel
            3. View all documents in the Document List
            """)
        
        with help_info_tabs[1]:
            st.title("📚 Resources")
            st.markdown("""
            System documentation and resources will be listed here.
            """)
        
        with help_info_tabs[2]:
            st.write("""
            ### 🎯 About HKI Records Management System
            
            Transform your records management with AI-powered innovation.
            
            ### 🔍 Key Features
            - AI-powered document chat
            - Secure document management
            - Advanced search capabilities
            
            ### 💻 Technology Stack
            - Backend: Python, ChromaDB, LangChain
            - AI: Various LLM models
            - Frontend: Streamlit
            """)
    
    # Footer
    st.markdown("---")
    st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")
