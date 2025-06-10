from langchain_core.retrievers import BaseRetriever
from typing import List
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import Field, BaseModel

class HybridRetriever(BaseRetriever, BaseModel):
    """Hybrid retriever that combines semantic and keyword search"""
    
    retriever: BaseRetriever = Field(description="Base retriever to use")
    k: int = Field(default=4, ge=1, description="Number of documents to return")

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """Get relevant documents using hybrid retrieval"""
        # Get initial documents using base retriever
        docs = self.retriever.get_relevant_documents(query)

        # Sort by relevance score if available
        if docs:
            docs = sorted(
                docs,
                key=lambda x: float(x.metadata.get("score", 0.0)),
                reverse=True
            )

        # Return top k documents
        return docs[:self.k]
