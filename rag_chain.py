"""Module for RAG chain setup and configuration"""
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain
from langchain.chains import LLMChain, RetrievalQA, StuffDocumentsChain
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from retrieval.fusion_retriever import FusionRetriever

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
