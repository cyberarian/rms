import streamlit as st
import time
import traceback

def render_chatbot_tab(llm, initialize_or_load_vectorstore, get_rag_chain, memory_track, logger, traceback_module):
    st.subheader("💬 Chatbot")
    # Model selection inside chatbot tab
    model_options = {
        "llama-4-maverick-17b-128e-instruct (Groq)": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "DeepSeek-V3-0324 (HuggingFace)": "deepseek-ai/DeepSeek-V3-0324",
    }
    selected_model_display_name = st.radio(
        "Select AI Model",
        options=list(model_options.keys()),
        key='model_selector_radio', # Changed key to avoid conflict if 'model_selector' is used elsewhere
        horizontal=True,
        help="Note: The RAG chain currently uses the LLM initialized at startup for its primary operations."
    )
    # model_id = model_options[selected_model_display_name] # model_id is not directly used with the passed llm

    # Initialize chat history in session state if it doesn't exist
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # Create a form for the chat input
    with st.form(key='chat_form_tab'): # Changed key
        prompt1 = st.text_input("Enter your question about the documents", key='question_input_tab') # Changed key
        submit_button = st.form_submit_button("Submit Question")

    # Display chat history with better formatting
    for q, a in st.session_state.chat_history:
        with st.container():
            st.info(f"❓ **Pertanyaan:** {q}")
            st.markdown(a)  # Use markdown for formatted answer
            st.divider()
    
    if submit_button and prompt1:
        try:
            with memory_track(): # memory_track is passed
                if st.session_state.vectorstore is None:
                    st.session_state.vectorstore = initialize_or_load_vectorstore() # initialize_or_load_vectorstore is passed
                
                vectorstore = st.session_state.vectorstore
                if len(vectorstore.get()['ids']) > 0:
                    # Initialize the enhanced RAG chain
                    qa_chain = get_rag_chain(llm, vectorstore) # get_rag_chain and llm are passed
                    
                    with st.spinner('Searching through documents...'):
                        start = time.process_time()
                        response = qa_chain.invoke({'query': prompt1})
                        elapsed_time = time.process_time() - start
                        
                        # Add the new Q&A to the chat history
                        st.session_state.chat_history.append((prompt1, response['result']))
                        
                        # Display the latest response with proper formatting
                        st.write("💡 **Jawaban Terbaru:**")
                        st.markdown(response['result'])
                        st.caption(f"⏱️ Waktu respons: {elapsed_time:.2f} detik")
                        
                        # Clear the input box by rerunning the app
                        st.rerun()
                else:
                    st.warning("No documents found in the database. Please ask an admin to upload some documents.")
        except Exception as e:
            st.error(f"Error processing question: {str(e)}")
            logger.error(traceback_module.format_exc()) # logger and traceback_module are passed

    # Add a clear chat history button
    if st.session_state.chat_history and st.button("Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()
        
    # Footer
    st.markdown("---")
    st.markdown("Powered by Arsipy, Next-Gen Records Management, Driven by AI", help="cyberariani@gmail.com")

