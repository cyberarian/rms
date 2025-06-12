#__import__('pysqlite3')
import sys
#sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import streamlit as st
import os
import time
import fitz  # PyMuPDF
import pandas as pd
import logging
import traceback
import gc
import sys
import shutil
from stqdm import stqdm
from contextlib import contextmanager
from typing import List
from langchain.globals import set_verbose
from dotenv import load_dotenv
from streamlit.runtime.caching import cache_data, cache_resource
from datetime import datetime
import toml

from langchain_groq import ChatGroq
from langchain_chroma import Chroma
from huggingface_hub import InferenceClient
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.language_models.llms import LLM
from typing import Any, List, Optional

from landing_page import show_landing_page
from rag_chain import get_rag_chain # Import from rag_chain.py

# Import new tab rendering functions
from tabs.chatbot_tab import render_chatbot_tab
from tabs.records_management_tab import render_records_management_tab
from tabs.document_list_tab import render_document_list_tab
from tabs.help_info_tab import render_help_info_tab
from tabs.admin_panel_tab import render_admin_panel_tab, CHROMA_DB_DIR as ADMIN_CHROMA_DB_DIR # Import CHROMA_DB_DIR if defined in admin_panel_tab

# Update CRUD import with error handling
try:
    from CRUD_st import create_document, read_documents, update_document, delete_document, init_db as crud_init_db, create_document_record
except ImportError as e:
    st.error(f"Error importing CRUD functions: {str(e)}")
    st.error("Please ensure CRUD_st.py is in the same directory and properly formatted")
    crud_init_db = None

CHROMA_DB_DIR = "chroma_db" # Define as a top-level constant


class DeepSeekLLM(LLM):
    """Custom LLM class for DeepSeek models from HuggingFace"""
    
    client: InferenceClient
    model: str
    temperature: float = 0.6
    max_tokens: int = 512
    
    def __init__(
        self,
        model: str,
        api_key: str,
        temperature: float = 0.6,
        max_tokens: int = 512,
        callback_manager: Optional[CallbackManager] = None
    ):
        super().__init__(callback_manager=callback_manager)
        self.client = InferenceClient(token=api_key)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @property
    def _llm_type(self) -> str:
        return "deepseek"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        response = self.client.text_generation(
            prompt,
            model=self.model,
            max_new_tokens=self.max_tokens,
            temperature=self.temperature,
            stop_sequences=stop or [],
            **kwargs
        )
        return response

# Modify the get_llm_model function
def get_llm_model(model_name: str):
    """
    Initialize and return the specified LLM model
    """
    models = {
        "meta-llama/llama-4-maverick-17b-128e-instruct": lambda: ChatGroq(
            groq_api_key=os.getenv('GROQ_API_KEY'),
            model_name="meta-llama/llama-4-maverick-17b-128e-instruct"
        ),
        "deepseek-coder": lambda: DeepSeekLLM(
            model="deepseek-ai/DeepSeek-V3-0324",
            api_key=os.getenv('HUGGINGFACE_API_KEY'),
            temperature=0.7,
            max_tokens=512
        )
    }
    
    if model_name not in models:
        raise ValueError(f"Unsupported model: {model_name}")
        
    return models[model_name]()

# Set the page layout to wide
st.set_page_config(layout="wide")
# Load the config.toml file
config = toml.load(".streamlit/config.toml")
# Apply the custom CSS
st.markdown(f"<style>{config['custom_css']['css']}</style>", unsafe_allow_html=True)
# Load the admin password from the .env file
admin_password = os.getenv('ADMIN_PASSWORD')
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Memory management context
@contextmanager
def memory_track():
    try:
        gc.collect()
        yield
    finally:
        gc.collect()

def initialize_or_load_vectorstore():
    """Initialize or load the vector store with consistent 768 dimensions"""
    try:
        from langchain_community.embeddings import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",
            model_kwargs={'device': 'cpu'}
        )
        # Reset ChromaDB if dimensions mismatch
        try:
            vectorstore = Chroma(
                persist_directory=CHROMA_DB_DIR,
                embedding_function=embeddings
            )
            # Test dimensions
            test_text = "Test embedding dimensions"
            emb = embeddings.embed_query(test_text)
            if len(emb) != 768:
                raise ValueError("Embedding dimensions mismatch")
        except Exception as e:
            logger.warning(f"ChromaDB reset needed: {str(e)}")
            # Force reset if dimensions mismatch
            if os.path.exists(CHROMA_DB_DIR):
                shutil.rmtree(CHROMA_DB_DIR)
                os.makedirs(CHROMA_DB_DIR)
            vectorstore = Chroma(
                persist_directory=CHROMA_DB_DIR,
                embedding_function=embeddings
            )
        
        return vectorstore
    except Exception as e:
        logger.error(f"Error initializing vector store: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def clear_cache():
    """Clear all cached data"""
    cache_data.clear()
    cache_resource.clear()

def show_chat_interface(llm):
    """Display the main interface with sidebar navigation"""
    # Create a centered title with modern styling
    st.markdown("""
        <div style='text-align: center; padding: 1rem 0 1rem 0;'>
            <h3 style='color: #FF4B4B; margin-bottom: 0.25rem;'>Next-Gen Records Management, Driven by AI</h3>
            <p style='color: #666; font-size: 1rem;'>Intelligent • Compliant • Streamlined</p>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar Navigation for main content
    st.sidebar.title("Menu Utama")
    page_options = {
        "💬 Chatbot": "chatbot",
        "📝 Records Management": "records_management",
        "📋 Document List": "document_list",
        "ℹ️ Help & Info": "help_info",
        "🔑 Admin Panel": "admin_panel" # Added Admin Panel
    }
    # Use labels for display and keys for logic
    selected_page_label = st.sidebar.radio(
        "",
        list(page_options.keys()),
        key='main_navigation_radio',
        label_visibility="collapsed"  # This hides the label while keeping the radio working
    )
    selected_page_key = page_options[selected_page_label]

    # Conditional rendering based on sidebar selection
    if selected_page_key == "chatbot":
        render_chatbot_tab(llm, initialize_or_load_vectorstore, get_rag_chain, memory_track, logger, traceback)
    elif selected_page_key == "help_info":
        render_help_info_tab()
    elif selected_page_key == "document_list":
        render_document_list_tab(crud_init_db, read_documents)
    elif selected_page_key == "records_management":
        render_records_management_tab(crud_init_db, create_document, update_document, delete_document)
    elif selected_page_key == "admin_panel":
        render_admin_panel_tab(admin_password, CHROMA_DB_DIR, initialize_or_load_vectorstore, clear_cache, logger)

def initialize_or_load_vectorstore():
    """Initialize or load the vector store with consistent embedding dimensions"""
    try:
        # Only use one embedding model with 768 dimensions
        from langchain_community.embeddings import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-mpnet-base-v2",  # Fixed 768 dimensions
            model_kwargs={'device': 'cpu'}
        )
        vectorstore = Chroma(
            persist_directory=CHROMA_DB_DIR,
            embedding_function=embeddings
        )
        return vectorstore
    except Exception as e:
        logger.error(f"Error initializing embeddings: {str(e)}")
        raise

def main():
    # Disable ChromaDB telemetry
    os.environ['ANONYMIZED_TELEMETRY'] = 'False'
    load_dotenv()
    
    set_verbose(True)
    # Initialize session state for showing admin panel
    if 'show_admin' not in st.session_state:
        st.session_state['show_admin'] = False
    # Show landing page if not accessing admin panel
    if not st.session_state['show_admin']:
        show_landing_page()  # Now using the imported function
        return

    # Load and validate API keys
    groq_api_key = os.getenv('GROQ_API_KEY')
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not groq_api_key or not google_api_key:
        st.error("Missing API keys. Please check your .env file.")
        st.stop()
    
    os.environ["GOOGLE_API_KEY"] = google_api_key
    
    # Create ChromaDB directory
    # CHROMA_DB_DIR is now a top-level constant
    if not os.path.exists(CHROMA_DB_DIR):
        os.makedirs(CHROMA_DB_DIR)
    
    # Initialize session state
    if 'uploaded_file_names' not in st.session_state:
        st.session_state.uploaded_file_names = set()
    if 'vectorstore' not in st.session_state:
        st.session_state.vectorstore = None
    
    try:
        # Initialize LLM and prompt template
        llm = ChatGroq(
            groq_api_key=groq_api_key,
            model_name="meta-llama/llama-4-maverick-17b-128e-instruct"
        )
    except Exception as e:
        st.error(f"Error initializing LLM: {str(e)}")
        st.stop()
    
    # Show main chat interface
    show_chat_interface(llm)

if __name__ == "__main__":
    main()