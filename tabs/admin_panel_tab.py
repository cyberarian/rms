from components.markdown_editor import render_markdown_editor
import streamlit as st
import os
import shutil
import traceback
import logging
from datetime import datetime
from typing import List
from stqdm import stqdm

# Assuming CRUD_st.py is in the parent directory or accessible via sys.path
try:
    from CRUD_st import create_document_record
except ImportError:
    # Fallback or error message if direct import fails
    st.error("Failed to import CRUD_st.create_document_record. Ensure it's accessible.")
    def create_document_record(*args, **kwargs): # Dummy function
        st.error("CRUD functionality is impaired.")
        return None

# Assuming document_processor.py is in the parent directory or accessible
try:
    from document_processor import UnifiedDocumentProcessor
except ImportError:
    # st.error("Failed to import UnifiedDocumentProcessor. Ensure it's accessible.") # Avoid error during initial load
    class UnifiedDocumentProcessor: # Dummy class
        def __init__(self, *args, **kwargs):
            st.error("Document processing functionality is impaired.")
        def extract_document_content_and_metadata(self, *args, **kwargs):
            return {'success': False, 'error': 'UnifiedDocumentProcessor not loaded'}
        def finalize_and_add_to_vectorstore(self, *args, **kwargs):
            return {'success': False, 'error': 'UnifiedDocumentProcessor not loaded'}

from components.markdown_editor import render_markdown_editor


# Define CHROMA_DB_DIR here if it's specific to admin operations,
# or ensure it's passed correctly from app.py
CHROMA_DB_DIR = "chroma_db" # Or import from a central config

# Local logger for this module
logger = logging.getLogger(__name__)


def _reset_chroma_db(chroma_db_path):
    """Reset the ChromaDB directory"""
    try:
        if os.path.exists(chroma_db_path):
            shutil.rmtree(chroma_db_path)
            os.makedirs(chroma_db_path) # Recreate the directory
            if 'vectorstore' in st.session_state:
                 st.session_state.vectorstore = None # Reset vectorstore in session
            return True
    except Exception as e:
        logger.error(f"Error resetting ChromaDB at {chroma_db_path}: {str(e)}")
        return False

def _trigger_extraction_for_review(uploaded_files: List, chroma_db_path: str, initialize_or_load_vectorstore):
    try:
        if not uploaded_files:
            st.warning("No files selected for processing")
            return

        if 'vectorstore' not in st.session_state or st.session_state.vectorstore is None:
            try:
                st.session_state.vectorstore = initialize_or_load_vectorstore()
            except Exception as e:
                logger.error(f"Vectorstore error: {str(e)}")
                st.error("Failed to initialize document storage")
                return
        
        # Ensure vectorstore is not None after initialization attempt
        if st.session_state.vectorstore is None:
            st.error("Vectorstore could not be initialized. Cannot process files.")
            return

        processor = UnifiedDocumentProcessor(vectorstore=st.session_state.vectorstore)
        st.session_state.files_for_review = st.session_state.get('files_for_review', {})
        
        with st.spinner('Extracting content from documents for review...'):
            for file_obj in stqdm(uploaded_files):
                if file_obj.name in st.session_state.get('uploaded_file_names', set()): # Check against fully processed files
                    st.info(f"Skipping {file_obj.name} - already processed and stored.")
                    continue
                
                extraction = processor.extract_document_content_and_metadata(file_obj)
                if extraction['success']:
                    st.session_state.files_for_review[file_obj.name] = {
                        'initial_text': extraction['text'],
                        'metadata': extraction['metadata'],
                        'images_data': extraction['images_data'],
                        'layout_info': extraction['layout_info'],
                        'status': 'extracted', # New status: extracted, needs review
                        'file_object': file_obj 
                    }
                    st.info(f"📄 Content extracted for: {file_obj.name}. Ready for review below.")
                else:
                    st.error(f"Failed to extract content for {file_obj.name}: {extraction.get('error', 'Unknown error')}")
    except Exception as e:
        logger.error(f"Document processing error: {str(e)}")
        st.error("Processing failed. Check logs for details.")
        logger.error(traceback.format_exc())


def _render_admin_controls_content_area(chroma_db_path: str, initialize_or_load_vectorstore_func, clear_cache_func):
    st.header("Document Ingestion & Management")
    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=["pdf", "txt", "png", "jpg", "jpeg", "xlsx", "docx"],
        accept_multiple_files=True,
        help="Supported formats: PDF, TXT, PNG, JPG, JPEG, XLSX, DOCX",
        key="admin_panel_uploader" # Unique key
    )
    if uploaded_files:
        if st.button("Extract Content for Review", key="admin_panel_extract_docs"):
            with st.expander("Extraction Queue", expanded=True):
                for file_item in uploaded_files:
                    st.info(f"📄 Queued for Extraction: {file_item.name}")
                    st.text(f"Type: {file_item.type}")
            _trigger_extraction_for_review(uploaded_files, chroma_db_path, initialize_or_load_vectorstore_func)
            st.rerun() # Rerun to display review section

    # --- Review and Finalize Section ---
    if 'files_for_review' in st.session_state and st.session_state.files_for_review:
        st.subheader("Review Extracted Content and Finalize")
        
        # Ensure vectorstore is loaded for the processor
        if 'vectorstore' not in st.session_state or st.session_state.vectorstore is None:
            try:
                st.session_state.vectorstore = initialize_or_load_vectorstore_func()
            except Exception as e:
                logger.error(f"Vectorstore error during review section: {str(e)}")
                st.error("Failed to initialize document storage. Cannot finalize.")
                return
        
        processor = UnifiedDocumentProcessor(vectorstore=st.session_state.vectorstore)

        for file_name, data in list(st.session_state.files_for_review.items()):
            safe_file_name_key = file_name.replace('.', '_').replace(' ', '_') # Make key safe

            if data['status'] == 'extracted':
                with st.expander(f"Review and Edit: {file_name}", expanded=True):
                    editor_key = f"editor_{safe_file_name_key}"
                    
                    # Initialize editor state if not present, or use existing if user was editing
                    if editor_key not in st.session_state:
                         st.session_state[editor_key] = data['initial_text']

                    # render_markdown_editor updates its own state st.session_state[editor_key]
                    # and returns the current content.
                    _ = render_markdown_editor( # We don't need the returned content here directly
                        value=st.session_state[editor_key], 
                        key=editor_key,
                        height=400,
                        show_submit_button=False 
                    )

                    if st.button(f"Finalize and Add to Storage: {file_name}", key=f"finalize_{safe_file_name_key}"):
                        edited_content_from_state = st.session_state[editor_key]
                        
                        with st.spinner(f"Finalizing and storing {file_name}..."):
                            result = processor.finalize_and_add_to_vectorstore(
                                edited_text=edited_content_from_state,
                                metadata=data['metadata'],
                                images_data=data['images_data'],
                                layout_info=data['layout_info']
                            )

                            if result['success']:
                                st.success(f"✅ Successfully processed and stored: {file_name}")
                                st.session_state.files_for_review[file_name]['status'] = 'submitted_to_vs'
                                
                                crud_metadata = result['metadata'] # Use potentially updated metadata (e.g., markdown_path)
                                crud_payload = {
                                    'title': crud_metadata.get('title', os.path.splitext(file_name)[0]),
                                    'file_title': file_name,
                                    'description': crud_metadata.get('description', edited_content_from_state[:200]), # Or a summary
                                    'doc_date': crud_metadata.get('processed_at', datetime.now().strftime('%Y-%m-%d')),
                                    'doc_number': crud_metadata.get('doc_number', ''), 
                                    'alt_number': crud_metadata.get('alt_number', ''),
                                    'department': crud_metadata.get('department', 'Teknik dan Desain (TED)'), # Default or from metadata
                                    'project': crud_metadata.get('project', 'TIP Medan - Binjai'), # Default or from metadata
                                    'archive_code': crud_metadata.get('archive_code', 'PRO100'), # Default or from metadata
                                    'security_class': crud_metadata.get('security_class', 'Biasa/Umum/Terbuka'),
                                    'status': crud_metadata.get('status', 'Versi Akhir'),
                                    'ocr_processed': crud_metadata.get('ocr_provider') is not None
                                }
                                try:
                                    create_document_record(crud_payload, data['file_object']) # Use the stored file_object
                                    st.success(f"✓ CRUD record created for: {file_name}")
                                except Exception as e_crud:
                                    logger.error(f"CRUD error for {file_name}: {str(e_crud)}")
                                    st.warning(f"⚠️ CRUD record creation failed for {file_name}")

                                if 'uploaded_file_names' not in st.session_state: # This tracks fully processed files
                                    st.session_state.uploaded_file_names = set()
                                st.session_state.uploaded_file_names.add(file_name)
                                st.rerun()
                            else:
                                st.error(f"Failed to store {file_name}: {result.get('error', 'Unknown error')}")
            elif data['status'] == 'submitted_to_vs':
                 st.success(f"👍 {file_name} has been processed and stored.")

    # Display list of fully processed documents
    if 'uploaded_file_names' in st.session_state and st.session_state.uploaded_file_names:
        st.subheader("Successfully Stored Documents:")
        for fname in sorted(list(st.session_state.uploaded_file_names)):
            st.markdown(f"- {fname}")

    st.divider()
    st.header("System Reset")
    if st.button("Reset Everything", key="admin_panel_reset_all"): # Unique key
        if st.checkbox("Are you sure? This will delete all processed documents.", key="admin_panel_reset_confirm"): # Unique key
            try:
                clear_cache_func()
                if os.path.exists(chroma_db_path): # Use passed chroma_db_path
                    shutil.rmtree(chroma_db_path)
                    os.makedirs(chroma_db_path)
                    st.session_state.uploaded_file_names.clear()
                    if 'vectorstore' in st.session_state:
                        st.session_state.vectorstore = None
                    if 'files_for_review' in st.session_state:
                        st.session_state.files_for_review.clear()
                st.success("Complete reset successful!")
                st.rerun()
            except Exception as e:
                st.error(f"Error during reset: {str(e)}")
                logger.error(traceback.format_exc())
    if st.button("Reset Document Database", key="admin_panel_reset_db"): # Unique key
        if _reset_chroma_db(chroma_db_path): # Use passed chroma_db_path
            st.success("Document database reset successfully")
        else:
            st.error("Failed to reset document database")

def _render_system_settings():
    st.subheader("⚙️ System Settings")
    with st.expander("General Settings", expanded=True):
        st.number_input("Maximum Upload Size (MB)", value=50, key="sys_max_upload")
        st.number_input("Maximum Concurrent Uploads", value=5, key="sys_max_concurrent")
        st.checkbox("Enable Debug Mode", value=False, key="sys_debug_mode")
    
    with st.expander("AI Model Settings"):
        st.selectbox(
            "Default AI Model",
            ["llama-4-maverick-17b-128e-instruct", "deepseek-ai/DeepSeek-V3-0324"],
            key="sys_ai_model"
        )
        st.slider("Temperature", 0.0, 1.0, 0.7, key="sys_ai_temp")
        st.number_input("Max Tokens", value=512, key="sys_ai_tokens")
    
    with st.expander("Database Settings"):
        st.text_input("Database Backup Directory", key="sys_db_backup_dir")
        if st.button("Backup Database Now", key="sys_db_backup_now"):
            st.info("Database backup started...")
        if st.button("Optimize Database", key="sys_db_optimize"):
            st.info("Database optimization started...")
    
    with st.expander("Email Settings"):
        st.text_input("SMTP Server", key="sys_email_smtp")
        st.text_input("SMTP Port", key="sys_email_port")
        st.text_input("Email Username", key="sys_email_user")
        st.text_input("Email Password", type="password", key="sys_email_pass")
        st.checkbox("Enable Email Notifications", value=True, key="sys_email_enable")
    
    if st.button("Save Settings", key="sys_save_settings"):
        st.success("Settings saved successfully!")


def render_admin_panel_tab(admin_password_env, chroma_db_dir_app, initialize_or_load_vectorstore_app, clear_cache_app, app_logger):
    global logger
    logger = app_logger

    st.subheader("🔑 Admin Panel")

    # Add custom CSS for admin login
    st.markdown("""
        <style>
        /* Admin login container styling */
        [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {
            max-width: 400px;
            margin: 0 auto;
            padding: 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            backdrop-filter: blur(10px);
        }
        
        /* Style for password input */
        [data-testid="stTextInput"] {
            max-width: 300px;
            margin: 0 auto;
        }
        
        /* Style for buttons */
        .stButton > button {
            max-width: 200px;
            margin: 10px auto;
            display: block;
        }
        </style>
    """, unsafe_allow_html=True)

    if 'admin_authenticated' not in st.session_state:
        st.session_state.admin_authenticated = False

    if not st.session_state.admin_authenticated:
        input_password = st.text_input("Admin Password", type="password", key="admin_panel_password_input") # Unique key
        if st.button("Login", key="admin_panel_login_button"): # Unique key
            if input_password == admin_password_env:
                st.session_state.admin_authenticated = True
                st.success("Admin authenticated!")
                st.rerun()
            else:
                st.error("Incorrect password")
    else:
        st.write("✅ Admin authenticated")
        if st.button("Logout", key="admin_panel_logout_button"): # Unique key
            st.session_state.admin_authenticated = False
            st.rerun()
          # Create columns for horizontal radio buttons
        cols = st.columns(4)
        admin_sections = ["Document Management", "User Management", "Analytics Dashboard", "System Settings"]
        
        if 'admin_section_selector' not in st.session_state:
            st.session_state.admin_section_selector = admin_sections[0]
        
        for i, section in enumerate(admin_sections):
            if cols[i].button(
                section,
                key=f"admin_section_{i}",
                type="secondary" if st.session_state.admin_section_selector != section else "primary"
            ):
                st.session_state.admin_section_selector = section
        
        admin_section = st.session_state.admin_section_selector
        st.divider()

        if admin_section == "Document Management":
            _render_admin_controls_content_area(chroma_db_dir_app, initialize_or_load_vectorstore_app, clear_cache_app)
        elif admin_section == "User Management":
            try:
                from pages.admin.user_management import render_user_management
                render_user_management()
            except ImportError:
                st.error("User Management module not found.")
            except Exception as e:
                st.error(f"Error loading User Management: {e}")
        elif admin_section == "Analytics Dashboard":
            try:
                from pages.admin.analytics import render_analytics_dashboard
                render_analytics_dashboard()
            except ImportError:
                st.error("Analytics Dashboard module not found.")
            except Exception as e:
                st.error(f"Error loading Analytics Dashboard: {e}")
        elif admin_section == "System Settings":
            _render_system_settings()
            
    # Footer for admin page
    st.markdown("---")
    st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")
