from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List, Dict, Any
import re

class HierarchicalProcessor:
    """Process documents with hierarchical structure awareness"""
    
    def __init__(
        self,
        parent_split_size: int = 2000,
        child_split_size: int = 500,
        overlap: int = 50
    ):
        self.parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_split_size,
            chunk_overlap=overlap,
            separators=["\n\n", "\n", ".", "!", "?", ";", ",", " "]
        )
        self.child_splitter = RecursiveCharacterTextSplitter(
            chunk_size=child_split_size,
            chunk_overlap=overlap,
            separators=["\n", ".", "!", "?", ";", ",", " "]
        )

    def _detect_structure(self, text: str) -> Dict[str, Any]:
        """Detect document structure and sections"""
        structure = {
            "sections": [],
            "headers": [],
            "lists": [],
            "tables": []
        }
        
        # Detect section headers
        header_pattern = r'^(?:Section|Chapter|\d+\.)\s+.*$'
        structure["headers"] = [
            match.group() for match in re.finditer(header_pattern, text, re.MULTILINE)
        ]
        
        # Detect numbered/bulleted lists
        list_pattern = r'(?:^\s*[\-\*\•]\s.*$|^\s*\d+\.\s.*$)'
        structure["lists"] = [
            match.group() for match in re.finditer(list_pattern, text, re.MULTILINE)
        ]
        
        return structure

    def process_document(self, content: str, metadata: Dict[str, Any]) -> List[Document]:
        """Process document with hierarchical chunking and metadata"""
        # Detect document structure
        structure = self._detect_structure(content)
        
        # Create parent chunks
        parent_chunks = self.parent_splitter.split_text(content)
        documents = []
        
        for parent_idx, parent in enumerate(parent_chunks):
            # Create child chunks
            child_chunks = self.child_splitter.split_text(parent)
            
            # Detect local structure
            local_structure = self._detect_structure(parent)
            
            # Create enriched metadata
            for child_idx, child in enumerate(child_chunks):
                enriched_metadata = {
                    **metadata,
                    "parent_idx": parent_idx,
                    "child_idx": child_idx,
                    "local_headers": local_structure["headers"],
                    "is_list_item": bool(local_structure["lists"]),
                    "document_structure": structure["headers"],
                    "content_type": self._detect_content_type(child)
                }
                
                documents.append(Document(
                    page_content=child,
                    metadata=enriched_metadata
                ))
        
        return documents

    def _detect_content_type(self, text: str) -> str:
        """Detect type of content in chunk"""
        if re.search(r'^\s*(?:table|figure)\s+\d+', text, re.I):
            return "table_or_figure"
        elif re.search(r'^\s*\d+\.\s', text):
            return "numbered_list"
        elif re.search(r'^\s*[\-\*\•]\s', text):
            return "bulleted_list"
        elif re.search(r'^(?:section|chapter|\d+\.)\s+', text, re.I):
            return "header"
        else:
            return "text"
