import streamlit as st

def render_help_info_tab():
    st.subheader("ℹ️ Help & Info")
    
    # About Section
    st.markdown("""
    ### 🎯 About Arsipy Records Management System
            
    Dengan Arsipy, informasi dari record digital diolah menjadi akurat dan terstruktur. Nikmati kemudahan akses, pemahaman dokumen, dan peningkatan efisiensi dalam mencari informasi.

    ### 📖 User Guide

    #### 1️⃣ Berinteraksi dengan Chatbot
    1. Pilih **💬 Chatbot** dari menu sidebar
    2. Ketik pertanyaan tentang manual arsip
    3. Tunggu jawaban dari chatbot
    4. Lihat referensi sumber yang disertakan

    #### 2️⃣ Manajemen Dokumen
    - Gunakan **📝 Records Management** untuk mengelola dokumen
    - Lihat daftar dokumen di **📋 Document List**
    - Upload dokumen baru melalui admin panel

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
    
    ### ⚠️ Penting
    * Aplikasi ini tidak merekam percakapan
    * Chatbot hanya menjawab pertanyaan seputar isi dari dokumen manual arsip
    * Untuk informasi lebih lanjut, silakan hubungi developer
    """)
    # Footer
    st.markdown("---")
    st.markdown("Powered by Arsipy", help="cyberariani@gmail.com")

