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
from langchain_groq import ChatGroq
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_retrieval_chain
# from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain.schema import Document
from langchain.globals import set_verbose
from dotenv import load_dotenv
from streamlit.runtime.caching import cache_data, cache_resource
from datetime import datetime
import toml
import chromadb
import sqlite3
from image_analyzer import image_analyzer_main
from huggingface_hub import InferenceClient
from langchain_core.callbacks.manager import CallbackManager
from langchain_core.language_models.llms import LLM
from langchain.chains import LLMChain, RetrievalQA, StuffDocumentsChain
from langchain.prompts import PromptTemplate
from typing import Any, List, Optional
from document_processor import UnifiedDocumentProcessor
from landing_page import show_landing_page
from retrieval.fusion_retriever import FusionRetriever

def reset_chroma_db():
    """Reset the ChromaDB directory"""
    try:
        if os.path.exists(CHROMA_DB_DIR):
            shutil.rmtree(CHROMA_DB_DIR)
            os.makedirs(CHROMA_DB_DIR)
            st.session_state.vectorstore = None
            return True
    except Exception as e:
        logger.error(f"Error resetting ChromaDB: {str(e)}")
        return False
    
# Update CRUD import with error handling
try:
    from CRUD_st import create_document, read_documents, update_document, delete_document, init_db as crud_init_db, create_document_record
except ImportError as e:
    st.error(f"Error importing CRUD functions: {str(e)}")
    st.error("Please ensure CRUD_st.py is in the same directory and properly formatted")
    crud_init_db = None


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

def get_rag_chain(llm, vectorstore):
    """Create RAG chain with fusion retrieval"""
    # Create base retriever
    base_retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 8}  # Get more candidates for better fusion
    )
    
    # Initialize fusion retriever
    retriever = FusionRetriever(
        retriever=base_retriever,
        llm=llm,  # Pass LLM for query expansion
        k=4,  # Final number of documents
        weight_k=60.0,  # RRF ranking constant
        use_query_expansion=True  # Enable query expansion
    )

    QA_CHAIN_PROMPT = ChatPromptTemplate.from_template("""
    [SYSTEM]
    Anda adalah Arsipy, asisten ahli dokumentasi konstruksi untuk HKI Records Management System.

    [CONTEXT]
    {context}

    [QUESTION]
    {question}

    [FORMAT JAWABAN]
    RINGKASAN
    -------------------------------
    [Ringkasan singkat dan langsung dari jawaban utama]

    DETAIL INFORMASI
    -------------------------------
    A. [Poin Utama Pertama]
       - Spesifikasi: [detail spesifik]
       - Standar: [standar terkait]
       - Pengukuran: [nilai/satuan]

    B. [Poin Utama Kedua]
       - Spesifikasi: [detail spesifik]
       - Referensi: [referensi teknis]

    SPESIFIKASI TEKNIS
    -------------------------------
    | Parameter | Nilai/Keterangan |
    |-----------|------------------|
    | Standar   | [nilai/detail]  |
    | Dimensi   | [nilai/detail]  |
    | Teknis    | [nilai/detail]  |

    REFERENSI DOKUMEN
    -------------------------------
    [1] [Nama Dokumen] | Halaman [X] | [ID/Kode]
    [2] [Nama Dokumen] | Halaman [Y] | [ID/Kode]

    CATATAN PENTING
    -------------------------------
    [Informasi kritis atau peringatan jika ada]

    """)

    # Create the chain components
    document_prompt = PromptTemplate(
        template="""
Content:
{page_content}

Source: {source}
        """.strip(),
        input_variables=["page_content", "source"]
    )
    
    llm_chain = LLMChain(
        llm=llm,
        prompt=QA_CHAIN_PROMPT,
        output_key="answer"
    )
    
    qa_chain = RetrievalQA(
        combine_documents_chain=StuffDocumentsChain(
            llm_chain=llm_chain,
            document_prompt=document_prompt,
            document_variable_name="context",
            document_separator="\n---\n"
        ),
        retriever=retriever,
        return_source_documents=True
    )
    
    return qa_chain

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

def extract_text_from_pdf(pdf_file) -> str:
    """Extract text content from a PDF file"""
    try:
        pdf_document = fitz.open(stream=pdf_file.read(), filetype="pdf")
        text = ""
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            text += page.get_text()
        if not text.strip():
            raise ValueError("Extracted text from PDF is empty")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise
    finally:
        if 'pdf_document' in locals():
            pdf_document.close()

def get_document_text(file) -> str:
    """Get text content from a file based on its type"""
    try:
        if file.type == "application/pdf":
            text = extract_text_from_pdf(file)
        elif file.type == "text/plain":
            text = file.getvalue().decode('utf-8')
        else:
            raise ValueError(f"Unsupported file type: {file.type}")
        if not text.strip():
            raise ValueError("Extracted text is empty")
        return text
    except Exception as e:
        logger.error(f"Error extracting text from {file.name}: {str(e)}")
        raise

class EnhancedDocumentProcessor:
    """Advanced document processing with chunking and table detection"""
    def __init__(self, chunk_size=1000, chunk_overlap=200, ocr_enabled=True, table_detection_enabled=True):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ocr_enabled = ocr_enabled
        self.table_detection_enabled = table_detection_enabled
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def process_file_stream(self, file_stream, filename, metadata=None):
        """Process a file stream and return document chunks"""
        try:
            # Extract text based on file type
            text = get_document_text(file_stream)
            if not text:
                logger.warning(f"No text extracted from {filename}")
                return []
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)
            documents = []
            # Create documents with metadata
            base_metadata = {
                "source": filename,
                "chunk_size": self.chunk_size,
                "chunk_overlap": self.chunk_overlap
            }
            # Add custom metadata if provided
            if metadata:
                base_metadata.update(metadata)
            for i, chunk in enumerate(chunks):
                doc_metadata = base_metadata.copy()
                doc_metadata["chunk_index"] = i
                documents.append(
                    Document(
                        page_content=chunk,
                        metadata=doc_metadata
                    )
                )
            return documents
        except Exception as e:
            logger.error(f"Error processing file {filename}: {str(e)}")
            logger.error(traceback.format_exc())
            return []

    def get_tables(self, filepath):
        """Extract tables from document if supported"""
        if not self.table_detection_enabled:
            return []
            
        tables = []
        try:
            # Add table detection logic here if needed
            pass
        except Exception as e:
            logger.warning(f"Table extraction failed: {str(e)}")
        
        return tables

# Update process_uploaded_files to handle different file types
def process_uploaded_files(uploaded_files: List):
    try:
        if not uploaded_files:
            st.warning("No files selected for processing")
            return
        # Initialize vectorstore with consistent embeddings
        if st.session_state.vectorstore is None:
            try:
                st.session_state.vectorstore = initialize_or_load_vectorstore()
            except Exception as e:
                logger.error(f"Vectorstore error: {str(e)}")
                st.error("Failed to initialize document storage")
                return
        
        processor = UnifiedDocumentProcessor(vectorstore=st.session_state.vectorstore)
        with st.spinner('Processing documents...'):
            success_count = 0
            for file in stqdm(uploaded_files):
                try:
                    if file.name in st.session_state.uploaded_file_names:
                        st.info(f"Skipping {file.name} - already processed")
                        continue
                    
                    st.info(f"Processing: {file.name}")
                    if file.type == 'application/pdf':
                        st.info("Checking if OCR is needed...")
                    elif file.type.startswith('image/'):
                        st.info("Using OCR for image processing...")
                    elif file.type.endswith('spreadsheetml.sheet'):
                        st.info("Processing Excel file...")
                    elif file.type.endswith('wordprocessingml.document'):
                        st.info("Processing Word document...")
                    
                    result = processor.process_document(file)
                    if result['success']:
                        success_count += 1
                        st.session_state.uploaded_file_names.add(file.name)
                        # Create CRUD record with OCR status
                        crud_data = {
                            'title': result['metadata']['title'],
                            'file_title': file.name,
                            'description': result['metadata'].get('description', ''),
                            'doc_date': datetime.now().strftime('%Y-%m-%d'),
                            'doc_number': '',
                            'alt_number': '',
                            'department': 'Teknik dan Desain (TED)',
                            'project': 'TIP Medan - Binjai',
                            'archive_code': 'PRO100',
                            'security_class': 'Biasa/Umum/Terbuka',
                            'status': 'Versi Akhir',
                            'ocr_processed': result['metadata'].get('ocr_used', False)
                        }
                        try:
                            create_document_record(crud_data, file)
                            st.success(f"✓ CRUD record created for: {file.name}")
                            if result['metadata'].get('ocr_used'):
                                st.info("OCR was used to extract text")
                        except Exception as e:
                            logger.error(f"CRUD error: {str(e)}")
                            st.warning(f"⚠️ CRUD record creation failed")
                        st.success(f"✓ Document processed: {file.name}")
                        st.info(f"""
                        Document details:
                        - Characters: {result['total_chars']}
                        - Chunks: {result['document_count']}
                        - OCR used: {result['metadata'].get('ocr_used', False)}
                        """)
                    else:
                        st.error(f"Failed: {file.name} - {result.get('error')}")
                except Exception as e:
                    logger.error(f"Processing error: {str(e)}")
                    st.error(f"Error processing {file.name}")
            if success_count > 0:
                st.success(f"✅ Successfully processed {success_count} documents")
            else:
                st.error("No documents were processed successfully")
    except Exception as e:
        logger.error(f"Document processing error: {str(e)}")
        st.error("Processing failed. Check logs for details.")
        logger.error(traceback.format_exc())

def render_admin_controls_content_area():
    """Display admin controls in the main content area"""
    st.header("Document Management")
    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=["pdf", "txt", "png", "jpg", "jpeg", "xlsx", "docx"],
        accept_multiple_files=True,
        help="Supported formats: PDF, TXT, PNG, JPG, JPEG, XLSX, DOCX",
        key="admin_page_uploader"
    )
    if uploaded_files:
        if st.button("Process Documents", key="admin_page_process_docs"):
            with st.expander("Processing Details", expanded=True):
                for file_item in uploaded_files: # Renamed to avoid conflict with 'file' module
                    st.info(f"📄 Queued for Processing: {file_item.name}")
                    file_type = file_item.type
                    st.text(f"Type: {file_type}")
            process_uploaded_files(uploaded_files)

    if st.session_state.uploaded_file_names:
        st.write("Processed Documents:")
        for filename in st.session_state.uploaded_file_names:
            st.write(f"- {filename}")
    st.divider()
    st.header("System Reset")
    if st.button("Reset Everything", key="admin_page_reset_all"):
        if st.checkbox("Are you sure? This will delete all processed documents.", key="admin_page_reset_confirm"):
            try:
                clear_cache()
                if os.path.exists(CHROMA_DB_DIR):
                    shutil.rmtree(CHROMA_DB_DIR)
                    os.makedirs(CHROMA_DB_DIR)
                    st.session_state.uploaded_file_names.clear()
                    st.session_state.vectorstore = None
                st.success("Complete reset successful!")
                st.rerun()
            except Exception as e:
                st.error(f"Error during reset: {str(e)}")
                logger.error(traceback.format_exc())
    if st.button("Reset Document Database", key="admin_page_reset_db"):
        if reset_chroma_db():
            st.success("Document database reset successfully")
        else:
            st.error("Failed to reset document database")

def render_admin_page():
    """Render the admin panel page content"""
    st.subheader("🔑 Admin Panel")

    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        input_password = st.text_input("Admin Password", type="password", key="admin_page_password")
        if st.button("Login", key="admin_page_login"):
            if input_password == admin_password: # admin_password is a global variable
                st.session_state.admin_authenticated = True
                st.success("Admin authenticated!")
                st.rerun()
            else:
                st.error("Incorrect password")
    else:
        st.write("✅ Admin authenticated")
        if st.button("Logout", key="admin_page_logout"):
            st.session_state.admin_authenticated = False
            st.rerun()
        st.divider()
        render_admin_controls_content_area()

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
            <h1 style='color: #FF4B4B; margin-bottom: 0.25rem;'>Transforming Records Management with AI Innovation</h1>
            <p style='color: #666; font-size: 1.2rem;'>Efficient • Secure • Reliable</p>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar Navigation for main content
    st.sidebar.title("Menu Utama")
    page_options = {
        "💬 Chatbot": "chatbot",
        "📝 Records Management": "records_management",
        "📋 Document List": "document_list",
        "❓ Panduan": "panduan",
        "ℹ️ Tentang": "tentang",
        "📚 Resources": "resources",
        "🔑 Admin Panel": "admin_panel" # Added Admin Panel
    }
    # Use labels for display and keys for logic
    selected_page_label = st.sidebar.radio(
        "Pilih Halaman:",
        list(page_options.keys()),
        key='main_navigation_radio'
    )
    selected_page_key = page_options[selected_page_label]

    # Conditional rendering based on sidebar selection
    if selected_page_key == "chatbot":
        st.subheader("💬 Chatbot")
        # Model selection inside chatbot tab
        model_options = {
            "llama-4-maverick-17b-128e-instruct (Groq)": "meta-llama/llama-4-maverick-17b-128e-instruct",
            "DeepSeek-V3-0324 (HuggingFace)": "deepseek-ai/DeepSeek-V3-0324",
        }
        selected_model = st.radio(
            "Select AI Model",
            options=list(model_options.keys()),
            key='model_selector',
            horizontal=True,
            help="Note: The RAG chain currently uses the LLM initialized at startup."
        )
        model_id = model_options[selected_model]
        # Initialize chat history in session state if it doesn't exist
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        # Create a form for the chat input
        with st.form(key='chat_form'):
            prompt1 = st.text_input("Enter your question about the documents", key='question_input')
            submit_button = st.form_submit_button("Submit Question")
        # Display chat history with better formatting
        for q, a in st.session_state.chat_history:
            with st.container():
                st.info(f"❓ **Pertanyaan:** {q}")
                st.markdown(a)  # Use markdown for formatted answer
                st.divider()
        
        if submit_button and prompt1:
            try:
                with memory_track():
                    if st.session_state.vectorstore is None:
                        st.session_state.vectorstore = initialize_or_load_vectorstore()
                    
                    vectorstore = st.session_state.vectorstore
                    if len(vectorstore.get()['ids']) > 0:
                        # Create retriever from vectorstore
                        retriever = vectorstore.as_retriever(
                            search_type="similarity",
                            search_kwargs={"k": 4}  # Fetch top 4 most relevant chunks
                        )
                        
                        # Initialize the enhanced RAG chain
                        qa_chain = get_rag_chain(llm, vectorstore)
                        
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
                logger.error(traceback.format_exc())
        # Add a clear chat history button
        if st.session_state.chat_history and st.button("Clear Chat History"):
            st.session_state.chat_history = []
            st.rerun()
        # Footer
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")
    
    elif selected_page_key == "tentang":
        st.subheader("ℹ️ Tentang Arsipy Records Management System")
        st.markdown("""
        ### 🎯 Tentang Arsipy Records Management System
                
        Dengan Arsipy, informasi dari record digital diolah menjadi akurat dan terstruktur. Nikmati kemudahan akses, pemahaman dokumen, dan peningkatan efisiensi dalam mencari informasi.

        ### 🔍 Fitur Utama
        **RAG-based Chatbot**
        - Menjawab pertanyaan tentang manual arsip
        - Referensi dari sumber terpercaya
        - Konteks yang akurat dan relevan

        **Manajemen Arsip**
        - Penyimpanan dokumen digital
        - Pencarian cepat
        - Pengorganisasian otomatis

        ### 💻 Teknologi
        - **Backend**: Python, ChromaDB, LangChain
        - **AI Models**: llama-4-maverick-17b-128e-instruct (Groq's API), Google Gemini 2.0 Flash
        - **OCR**: pytesseract, Tesseract OCR
        - **Frontend**: Streamlit
        - **Database**: Vector Store dengan Google AI Embeddings
        
        """)
        st.subheader("⚠️ Penting")
        st.info("""
        * Aplikasi ini tidak merekam percakapan
        * Chatbot hanya menjawab pertanyaan seputar isi dari dokumen manual arsip
        * Untuk informasi lebih lanjut, silakan hubungi developer
        """)
        # Footer
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")
    
    elif selected_page_key == "panduan":
        st.subheader("❓ Panduan Dasar")
        st.markdown("""
        #### 1️⃣ Berinteraksi dengan Sistem
        1. Pilih halaman **💬 Chatbot** dari menu sidebar untuk bertanya pada AI.
        2. Ketik pertanyaan tentang manual arsip
        3. Tunggu jawaban dari chatbot
        4. Lihat referensi sumber yang disertakan    
    
        """)
        # Footer
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")
    
    elif selected_page_key == "resources":
        st.subheader("📚 Sumber Dokumen")
        st.markdown("""
        Sistem ini menggunakan sumber rekod dari berbagai departemen.
        """)
        # Footer
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")

    elif selected_page_key == "document_list":
        st.subheader("📋 Document List")
        try:
            if crud_init_db is None:
                st.error("Document List is currently unavailable")
            # Initialize CRUD database
            crud_init_db()
            # Call only the read function
            read_documents()
        except Exception as e:
            st.error(f"Error in Document List: {str(e)}")
            st.error("Please check the database connection")
        # Footer
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")

    elif selected_page_key == "records_management":
        st.subheader("📝 Records Management System")
        try:
            if crud_init_db is None:
                st.error("Records Management System is currently unavailable")
            
            crud_init_db()
            # Create CRUD menu but remove Read operation
            menu = ["Create", "Update", "Delete"]  # Removed "Read" since it's now in tab5
            choice = st.selectbox(
                "Select Operation",
                menu,
                key="crud_operation_tab6"
            ) # Unique key
            # Add spacing
            st.write("")
            # Display operation title
            if choice:
                st.subheader(f"{choice} Document")
            # Call CRUD functions except Read
            if choice == "Create":
                create_document()
            elif choice == "Update":
                update_document()
            elif choice == "Delete":
                delete_document()
        except Exception as e:
            st.error(f"Error in Records Management: {str(e)}")
            st.error("Please check the CRUD implementation")
        # Footer
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")
    
    elif selected_page_key == "admin_panel":
        render_admin_page()
        # Footer for admin page
        st.markdown("---")
        st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")

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
    global CHROMA_DB_DIR
    CHROMA_DB_DIR = "chroma_db"
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