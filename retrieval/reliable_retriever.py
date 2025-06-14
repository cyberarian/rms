from langchain_core.retrievers import BaseRetriever
from typing import List, Dict, Any
from langchain_core.documents import Document
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.language_models.base import BaseLanguageModel
from pydantic import Field, BaseModel
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

EVAL_PROMPT = """Analyze this document's relevance and factual grounding for the given question.
Use strict criteria to ensure information quality and relevance.

QUESTION: {question}
DOCUMENT: {document}

Score each criteria (0-10) and provide evidence.
Only score based on explicit information in the document, not inferences:

1. RELEVANCE: Does it directly address the question?
   Score based on how much of the question is answered explicitly.
   
2. FACTUAL: Is all information explicitly stated?
   Score based on verifiable facts, not interpretations.
   
3. GROUNDING: Can claims be traced to specific text?
   Score based on evidence presence and clarity.
   
4. COMPLETENESS: Is context fully provided?
   Score based on self-contained information.

Format:
RELEVANCE: [score]
EVIDENCE: [quote text that directly answers question]
FACTUAL: [score]
EVIDENCE: [quote supporting facts]
GROUNDING: [score]
EVIDENCE: [list document sections used]
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
            "relevance": 0.45,
            "factual": 0.3,
            "grounding": 0.15,
            "completeness": 0.1
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
        
        # Track evidence coverage
        total_evidence = 0
        valid_evidence = 0
        
        # Verify each piece of evidence
        for evidence_type, ev in evidence.items():
            if isinstance(ev, str) and ev.strip():
                total_evidence += 1
                # Check if evidence text exists in document
                if ev.lower().strip() in doc_text:
                    valid_evidence += 1
                    
        # Calculate evidence coverage ratio
        if total_evidence == 0:
            return False
            
        coverage = valid_evidence / total_evidence
        return coverage >= self.evidence_threshold
    
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
                            score = float(value.strip())
                            # Validate score range
                            scores[key] = max(0.0, min(10.0, score))
                        except ValueError:
                            scores[key] = 0.0
                    elif key == 'evidence' and current_metric:
                        evidence[current_metric] = value.strip()
            
            # Normalize scores to 0-1 range
            scores = {k: v/10.0 for k, v in scores.items()}
            
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
            except Exception:
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
        try:
            initial_docs = self.retriever.get_relevant_documents(query)
            verified_docs = self.verify_docs(initial_docs, query)
            return verified_docs[:self.k]
        except Exception:
            # Fallback to base retriever without verification
            initial_docs = self.retriever.get_relevant_documents(query)
            return initial_docs[:self.k]
