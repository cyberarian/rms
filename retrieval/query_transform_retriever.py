from langchain_core.retrievers import BaseRetriever
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from pydantic import Field, BaseModel
from typing import List, Dict, Set
import itertools

QUERY_TRANSFORM_PROMPT = """Given a user question, generate multiple search queries to find relevant information.
Create queries that:
1. Focus on key technical terms
2. Include synonyms and related terms
3. Break down complex questions
4. Consider different aspects

Original Question: {question}

Generate these types of queries:
1. Literal: Direct search using main terms
2. Technical: Focus on specifications and standards
3. Contextual: Include project phase or document type
4. Relational: Connect to related documents/topics

Output Format (generate 2-3 per type):
LITERAL: <query>
TECHNICAL: <query>
CONTEXTUAL: <query>
RELATIONAL: <query>"""

class QueryTransformRetriever(BaseRetriever, BaseModel):
    """Retriever that transforms queries for better coverage"""
    
    retriever: BaseRetriever = Field(description="Base retriever")
    llm: BaseLanguageModel = Field(description="LLM for query transformation")
    k: int = Field(default=4, description="Number of final documents")
    
    def _transform_query(self, query: str) -> List[str]:
        """Generate multiple query variations"""
        transform_chain = LLMChain(
            llm=self.llm,
            prompt=PromptTemplate(
                template=QUERY_TRANSFORM_PROMPT,
                input_variables=["question"]
            )
        )
        
        try:
            response = transform_chain.invoke({"question": query})["text"]
            queries = set()
            
            # Parse generated queries
            for line in response.split('\n'):
                if ':' in line:
                    _, query_text = line.split(':', 1)
                    queries.add(query_text.strip())
            
            # Always include original query
            queries.add(query)
            return list(queries)
            
        except Exception:
            return [query]

    def _dedup_documents(self, docs: List[Document], threshold: float = 0.85) -> List[Document]:
        """Remove near-duplicate documents based on content similarity"""
        unique_docs = []
        seen_content = set()
        
        for doc in docs:
            doc_id = f"{doc.metadata.get('source', '')}-{doc.metadata.get('chunk_index', '')}"
            if doc_id not in seen_content:
                seen_content.add(doc_id)
                unique_docs.append(doc)
                
        return unique_docs

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """Get documents using transformed queries"""
        # Generate variations
        queries = self._transform_query(query)
        
        # Collect documents from all queries
        all_docs = []
        for q in queries:
            docs = self.retriever.get_relevant_documents(q)
            all_docs.extend(docs)
            
        # Deduplicate and sort by relevance
        unique_docs = self._dedup_documents(all_docs)
        
        return sorted(
            unique_docs,
            key=lambda x: float(x.metadata.get("score", 0.0)),
            reverse=True
        )[:self.k]
