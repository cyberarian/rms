from langchain_core.retrievers import BaseRetriever
from typing import List, Any, Dict, Optional
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from pydantic import Field, BaseModel
from langchain_core.language_models.base import BaseLanguageModel
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

QUERY_EXPANSION_PROMPT = """Generate multiple search queries for the given user question. 
Focus on:
1. Key technical terms
2. Core concepts
3. Related specifications

Original Question: {question}

Return only the queries, one per line."""

class FusionRetriever(BaseRetriever, BaseModel):
    """Enhanced retriever with query expansion and RRF ranking"""
    
    retriever: BaseRetriever = Field(description="Base retriever to use")
    llm: Optional[BaseLanguageModel] = Field(default=None, description="LLM for query expansion")
    k: int = Field(default=4, ge=1, description="Number of documents to return")
    weight_k: float = Field(default=60.0, description="RRF weight constant")
    use_query_expansion: bool = Field(default=True, description="Enable query expansion")

    def _expand_query(self, query: str) -> List[str]:
        """Generate multiple query variations"""
        if not self.llm or not self.use_query_expansion:
            return [query]
            
        try:
            chain = LLMChain(
                llm=self.llm,
                prompt=PromptTemplate(
                    template=QUERY_EXPANSION_PROMPT,
                    input_variables=["question"]
                )
            )
            response = chain.invoke({"question": query})["text"]
            queries = [q.strip() for q in response.split('\n') if q.strip()]
            queries.append(query)  # Include original query
            return list(set(queries))  # Remove duplicates
        except Exception:
            return [query]

    def get_scores(self, docs: List[Document], queries: List[str]) -> Dict[str, float]:
        """Calculate enhanced RRF scores with multi-query support"""
        scores = {}
        for query in queries:
            # Sort docs by relevance to this query variation
            sorted_docs = sorted(
                docs,
                key=lambda x: x.metadata.get("score", 0.0) * 
                            self._calculate_query_similarity(query, x.page_content),
                reverse=True
            )
            
            # Calculate RRF score for each doc
            for rank, doc in enumerate(sorted_docs):
                doc_id = f"{doc.metadata.get('source', '')}-{doc.metadata.get('chunk_index', rank)}"
                score = 1.0 / (rank + self.weight_k)
                scores[doc_id] = scores.get(doc_id, 0.0) + score

        return scores

    def _calculate_query_similarity(self, query: str, content: str) -> float:
        """Calculate semantic similarity between query and content"""
        query_terms = set(query.lower().split())
        content_terms = set(content.lower().split())
        
        # Calculate Jaccard similarity
        intersection = query_terms & content_terms
        union = query_terms | content_terms
        
        return len(intersection) / len(union) if union else 0.0

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        # Expand query if enabled
        queries = self._expand_query(query)
        
        # Get documents for all query variations
        all_docs = []
        seen_ids = set()
        
        for q in queries:
            docs = self.retriever.get_relevant_documents(q)
            for doc in docs:
                doc_id = f"{doc.metadata.get('source', '')}-{doc.metadata.get('chunk_index', 0)}"
                if doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_docs.append(doc)
        
        # Calculate final scores using all queries
        scores = self.get_scores(all_docs, queries)
        
        # Assign final scores and sort
        for doc in all_docs:
            doc_id = f"{doc.metadata.get('source', '')}-{doc.metadata.get('chunk_index', 0)}"
            doc.metadata["score"] = scores.get(doc_id, 0.0)
        
        sorted_docs = sorted(all_docs, key=lambda x: x.metadata["score"], reverse=True)
        return sorted_docs[:self.k]
