from langchain_core.retrievers import BaseRetriever
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from pydantic import Field, BaseModel
from typing import List

QUERY_TRANSFORM_PROMPT = """Given a user question, generate multiple search queries to find relevant information.
Create queries that:
1. Focus on key technical terms and specifications
2. Include industry-standard terminology
3. Consider document structure (headers, lists, tables)
4. Break down complex questions
5. Add contextual terms from construction domain

Original Question: {question}

Generate these types of queries (2-3 each):

1. SPEC: Focus on technical specifications and standards
2. DOC: Consider document types and sections
3. PROCESS: Related to procedures or steps
4. CONTEXT: Add construction industry context
5. ENTITY: Focus on involved parties or departments

Output Format:
SPEC: <query>
DOC: <query>
PROCESS: <query>
CONTEXT: <query>
ENTITY: <query>"""

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
            
            # Parse generated queries and add weights
            for line in response.split('\n'):
                if ':' in line:
                    query_type, query_text = line.split(':', 1)
                    query_text = query_text.strip()
                    
                    # Add query type-specific terms
                    if query_type.upper() == 'SPEC':
                        query_text += " specification standard requirement"
                    elif query_type.upper() == 'DOC':
                        query_text += " document section"
                    elif query_type.upper() == 'PROCESS':
                        query_text += " procedure steps process"
                    elif query_type.upper() == 'CONTEXT':
                        query_text += " construction project"
                    
                    queries.add(query_text)
            
            # Always include original query
            queries.add(query)
            return list(queries)
            
        except Exception:
            return [query]  # Fallback to original query
    
    def _dedup_documents(self, docs: List[Document], threshold: float = 0.85) -> List[Document]:
        """Remove near-duplicate documents based on content similarity"""
        unique_docs = []
        seen_content = set()
        
        for doc in docs:
            doc_id = doc.metadata.get("source", "") + str(doc.metadata.get("chunk_index", ""))
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
        # Generate query variations
        queries = self._transform_query(query)
        
        # Collect documents from all queries
        all_docs = []
        seen_ids = set()
        
        for q in queries:
            try:
                docs = self.retriever.get_relevant_documents(q)
                for doc in docs:
                    doc_id = f"{doc.metadata.get('source', '')}-{doc.metadata.get('chunk_index', '')}"
                    if doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        all_docs.append(doc)
            except Exception:
                continue
                
        # Deduplicate and sort by relevance
        unique_docs = self._dedup_documents(all_docs)
        
        # Sort by score if available
        return sorted(
            unique_docs,
            key=lambda x: float(x.metadata.get("score", 0.0)),
            reverse=True
        )[:self.k]
