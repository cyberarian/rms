import streamlit as st
import pandas as pd

def render_help_info_tab():
    st.subheader("ℹ️ Help & Info")
    
    # About Section in a clean card
    st.info(
        "Arsipy adalah sistem manajemen dokumen cerdas yang mengintegrasikan teknologi AI "
        "untuk memproses, menganalisis, dan menemukan informasi dari berbagai jenis dokumen "
        "dengan cepat dan akurat."
    )
    
    # Features in DataFrames
    with st.expander("🤖 Fitur RAG Chatbot", expanded=True):
        chat_features = {
            'Fitur': [
                'Input Query',
                'Jenis Pertanyaan',
                'Format Jawaban',
                'Pencarian',
                'Verifikasi'
            ],
            'Deskripsi': [
                'Interface chat yang intuitif di sidebar',
                'Mendukung pertanyaan tentang konten, prosedur, dan data dalam dokumen',
                'Jawaban terstruktur dengan referensi sumber',
                'Pencarian semantik multi-dokumen',
                'Verifikasi otomatis dengan sumber dokumen'
            ]
        }
        st.dataframe(pd.DataFrame(chat_features), hide_index=True)

    with st.expander("📝 Fitur Manajemen Dokumen"):
        doc_features = {
            'Kategori': [
                'Upload',
                'Organisasi',
                'Pencarian',
                'Preview',
                'Metadata'
            ],
            'Kemampuan': [
                'PDF, Images, Multiple file upload',
                'Kategori, Tags, Hierarki folder',
                'Full-text & Semantic search',
                'In-app document preview',
                'Auto-ekstraksi & Custom fields'
            ],
            'Fitur Tambahan': [
                'OCR otomatis',
                'Auto-kategorisasi',
                'Filter advanced',
                'Download original',
                'Batch processing'
            ]
        }
        st.dataframe(pd.DataFrame(doc_features), hide_index=True)

    with st.expander("🔒 Admin Features"):
        admin_features = {
            'Fitur': [
                'User Management',
                'System Monitor',
                'Data Management',
                'Configuration'
            ],
            'Kapabilitas': [
                'Kontrol akses, Role management, User groups',
                'Usage analytics, Performance metrics, Logs',
                'Backup/Restore, Archive, Clean-up',
                'System settings, API keys, Integration'
            ]
        }
        st.dataframe(pd.DataFrame(admin_features), hide_index=True)

    # Technology Stack as clean bulletpoints in columns
    with st.expander("💻 Technology Stack"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**AI & Backend**")
            tech_ai = {
                'Component': [
                    'LLM Engine',
                    'Vision AI',
                    'Vector Store',
                    'Embeddings',
                    'OCR Stack'
                ],
                'Technology': [
                    'Groq (llama-4-maverick)',
                    'Google Gemini Pro',
                    'ChromaDB',
                    'All-MPNet-Base-v2',
                    'Tesseract + Gemini'
                ]
            }
            st.dataframe(pd.DataFrame(tech_ai), hide_index=True)

        with col2:
            st.markdown("**Infrastructure**")
            tech_infra = {
                'Component': [
                    'Frontend',
                    'Backend',
                    'Database',
                    'Search',
                    'Caching'
                ],
                'Technology': [
                    'Streamlit',
                    'Python',
                    'SQLite',
                    'Vector + Full-text',
                    'In-memory + Disk'
                ]
            }
            st.dataframe(pd.DataFrame(tech_infra), hide_index=True)

    # Important Notes in a warning box
    st.warning("""
    ⚠️ **Penting:**
    - Chatbot hanya mengakses dokumen dalam sistem
    - Validasi manual untuk informasi penting
    - Semua jawaban menyertakan referensi sumber
    """)

    # Version and Contact in a clean footer
    st.markdown("---")
    
    # Contact info in columns
    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        st.markdown("**Version 1.0**")
    with col2:
        st.markdown("📧 support@arsipy.com")
    with col3:
        st.markdown("Powered by **Arsipy**")

