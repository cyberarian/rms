from langchain_core.retrievers import BaseRetriever
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.language_models.base import BaseLanguageModel
from pydantic import Field, BaseModel
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

EVAL_PROMPT = """Analyze this document's relevance and factual grounding for the given question.
Your task is to ensure information is directly supported by the source document.

QUESTION: {question}
DOCUMENT: {document}

Score each criteria (0-10) and provide evidence:
1. RELEVANCE: Does it directly answer the question?
   Score based only on explicit information, not implications.
2. FACTUAL: Is the information explicitly stated in the document?
   Score 0 if requires external knowledge or inference.
3. GROUNDING: Can every claim be traced to specific text?
   Score based on verifiable content only.
4. COMPLETENESS: Does it contain all necessary context?
   Score based on self-contained information.

Provide scores and evidence in this format:
RELEVANCE: [score]
EVIDENCE: [quote exact text that answers the question]
FACTUAL: [score]
EVIDENCE: [quote supporting text for facts]
GROUNDING: [score]
EVIDENCE: [list specific document sections used]
COMPLETENESS: [score]
EVIDENCE: [quote context information]"""

class ReliableRetriever(BaseRetriever, BaseModel):
    """Retriever with strict source verification"""
    
    retriever: BaseRetriever = Field(description="Base retriever")
    llm: BaseLanguageModel = Field(description="LLM for verification")
    k: int = Field(default=4, description="Number of documents to return")
    min_score: float = Field(default=5.0, description="Minimum relevance score")
    weights: Dict[str, float] = Field(
        default={
            "relevance": 0.4,
            "accuracy": 0.3,
            "completeness": 0.2,
            "context": 0.1
        },
        description="Weights for different scoring factors"
    )
    evidence_threshold: float = Field(
        default=0.7,
        description="Minimum evidence support required"
    )
    require_evidence: bool = Field(
        default=True,
        description="Require explicit evidence for inclusion"
    )

    def _validate_evidence(self, response: Dict[str, Any], doc: Document) -> bool:
        """Verify that evidence is actually present in document"""
        if not self.require_evidence:
            return True
            
        evidence = response.get('evidence', {})
        doc_text = doc.page_content.lower()
        
        # Verify each piece of evidence exists in document
        for ev in evidence.values():
            if isinstance(ev, str) and ev.lower().strip() not in doc_text:
                return False
        return True

    def _parse_scores(self, response: str) -> Dict[str, Any]:
        """Parse scores and evidence with validation"""
        try:
            scores = {}
            evidence = {}
            current_metric = None
            
            for line in response.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.lower().strip()
                    
                    if key in ['relevance', 'factual', 'grounding', 'completeness']:
                        current_metric = key
                        try:
                            scores[key] = float(value.strip())
                        except:
                            scores[key] = 0.0
                    elif key == 'evidence' and current_metric:
                        evidence[current_metric] = value.strip()
            
            return {
                'scores': scores,
                'evidence': evidence
            }
        except Exception:
            return {'scores': {}, 'evidence': {}}

    def _calculate_weighted_score(self, scores: Dict[str, float]) -> float:
        """Calculate weighted average of scores"""
        return sum(
            scores.get(metric, 0.0) * weight 
            for metric, weight in self.weights.items()
        )

    def verify_docs(self, docs: List[Document], query: str) -> List[Document]:
        """Score and verify documents with strict evidence requirements"""
        eval_chain = LLMChain(
            llm=self.llm,
            prompt=PromptTemplate(
                template=EVAL_PROMPT,
                input_variables=["question", "document"]
            )
        )
        
        scored_docs = []
        for doc in docs:
            try:
                response = eval_chain.invoke({
                    "question": query,
                    "document": doc.page_content
                })["text"]
                
                parsed = self._parse_scores(response)
                scores = parsed['scores']
                
                # Only include if evidence is valid
                if self._validate_evidence(parsed, doc):
                    weighted_score = self._calculate_weighted_score(scores)
                    
                    if weighted_score >= self.min_score:
                        doc.metadata.update({
                            "relevance_score": weighted_score,
                            "detailed_scores": scores,
                            "evidence": parsed['evidence'],
                            "verified": True
                        })
                        scored_docs.append(doc)
            except Exception as e:
                continue

        # Sort by weighted score
        return sorted(
            scored_docs,
            key=lambda x: float(x.metadata.get("relevance_score", 0.0)),
            reverse=True
        )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> List[Document]:
        """Get and verify relevant documents"""
        initial_docs = self.retriever.get_relevant_documents(query)
        verified_docs = self.verify_docs(initial_docs, query)
        return verified_docs[:self.k]
