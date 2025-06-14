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
               any(w in query.lower() for w in ["what", "how", "list", "steps", "procedure"]):
                structure_score += 0.2
                
            # Boost tables and figures for technical queries
            if metadata.get("content_type") == "table_or_figure" and \
               any(w in query.lower() for w in ["table", "figure", "diagram", 
                                              "measurement", "specification", "spec"]):
                structure_score += 0.3
                
            # Boost sections with technical specifications
            if metadata.get("contains_specs", False) and \
               any(w in query.lower() for w in ["specification", "requirement", 
                                              "standard", "measurement", "spec"]):
                structure_score += 0.3
                
            # Boost based on content type
            content_type_scores = {
                "numbered_list": 0.2 if any(w in query.lower() 
                    for w in ["steps", "procedure", "how", "process"]) else 0,
                "header": 0.15,
                "table": 0.25 if "table" in query.lower() else 0,
                "technical_spec": 0.3 if any(w in query.lower() 
                    for w in ["spec", "technical", "requirement"]) else 0
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
        """Execute multi-stage retrieval pipeline"""
        # Setup retrieval pipeline with improved parameters
        
        # 1. Transform queries for better coverage
        transform_retriever = QueryTransformRetriever(
            retriever=self.base_retriever,
            llm=self.llm,
            k=self.k * 3  # Get more candidates initially
        )
        
        # 2. Verify document relevance and evidence
        reliable_retriever = ReliableRetriever(
            retriever=transform_retriever,
            llm=self.llm,
            k=self.k * 2,
            min_score=4.0,  # Lower threshold slightly for better recall
            weights={  # Adjusted weights
                "relevance": 0.45,
                "factual": 0.3,
                "grounding": 0.15,
                "completeness": 0.1
            },
            evidence_threshold=0.6  # Slightly relaxed for better coverage
        )
        
        # 3. Combine results using RRF
        fusion_retriever = FusionRetriever(
            retriever=reliable_retriever,
            llm=self.llm,
            k=self.k * 1.5,  # Get extra docs for final structure-based ranking
            weight_k=40.0,  # Adjusted RRF constant
            use_query_expansion=True
        )
        
        # Get results through the pipeline
        try:
            # Get initial results through fusion
            results = fusion_retriever.get_relevant_documents(query)
            
            # Final reranking using document structure
            final_results = self._rerank_by_structure(results, query)
            
            # Return top k results
            return final_results[:self.k]
            
        except Exception:
            # Fallback to base retrieval if pipeline fails
            results = self.base_retriever.get_relevant_documents(query)
            return results[:self.k]
