from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.language_models.base import BaseLanguageModel
from pydantic import Field, BaseModel
from typing import List
from .reliable_retriever import ReliableRetriever
from .query_transform_retriever import QueryTransformRetriever
from .fusion_retriever import FusionRetriever

class EnhancedRetriever(BaseRetriever, BaseModel):
    """Combines multiple retrieval techniques with structural awareness"""
    
    base_retriever: BaseRetriever = Field(description="Base retriever")
    llm: BaseLanguageModel = Field(description="LLM for verification and transforms")
    k: int = Field(default=4, description="Final number of documents")
    
    def _rerank_by_structure(self, docs: List[Document], query: str) -> List[Document]:
        """Rerank documents using structural information"""
        for doc in docs:
            structure_score = 0.0
            metadata = doc.metadata
            
            # Boost documents with matching headers
            if any(header.lower() in query.lower() 
                  for header in metadata.get("document_structure", [])):
                structure_score += 0.3
                
            # Boost list items for "what" or "how" questions
            if metadata.get("is_list_item", False) and \
               any(w in query.lower() for w in ["what", "how", "list"]):
                structure_score += 0.2
                
            # Boost based on content type
            content_type_scores = {
                "table_or_figure": 0.3 if any(w in query.lower() 
                    for w in ["table", "figure", "diagram"]) else 0,
                "numbered_list": 0.2 if any(w in query.lower() 
                    for w in ["steps", "procedure", "how"]) else 0,
                "header": 0.1
            }
            structure_score += content_type_scores.get(
                metadata.get("content_type", ""), 0.0
            )
            
            # Update document score
            base_score = float(doc.metadata.get("score", 0.0))
            doc.metadata["score"] = base_score * (1 + structure_score)
            
        return sorted(docs, key=lambda x: float(x.metadata.get("score", 0.0)), reverse=True)
    
    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        # Setup pipeline
        transform_retriever = QueryTransformRetriever(
            retriever=self.base_retriever,
            llm=self.llm,
            k=self.k * 2
        )
        
        reliable_retriever = ReliableRetriever(
            retriever=transform_retriever,
            llm=self.llm,
            k=self.k * 2
        )
        
        fusion_retriever = FusionRetriever(
            retriever=reliable_retriever,
            k=self.k
        )
        
        # Get final results
        results = fusion_retriever.get_relevant_documents(query)
        final_results = self._rerank_by_structure(results, query)
        
        return final_results[:self.k]
