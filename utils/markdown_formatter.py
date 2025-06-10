import json
from datetime import datetime
from typing import Dict, Any

class MarkdownFormatter:
    @staticmethod
    def format_document(content: Dict[str, Any], layout_info: Dict[str, Any]) -> str:
        try:
            # Create markdown structure
            md_parts = [
                f"# {content.get('title', 'Untitled Document')}",
                "",
                "## Document Information",
                f"- File Type: {layout_info['file_info']['type']}",
                f"- Processing Date: {layout_info['processing_info']['timestamp']}",
                f"- OCR Provider: {content.get('metadata', {}).get('ocr_provider', 'unknown')}",
                f"- Characters: {content.get('metadata', {}).get('total_chars', 0)}",
                "",
                "## Extracted Content",
                "",
                "```text",
                content.get('content', 'No content available'),
                "```"
            ]
            
            return "\n".join(md_parts)
            
        except Exception as e:
            return f"""# Document Processing Error
            
Error: {str(e)}

Please check the document and try processing again."""

    @staticmethod
    def _create_searchable_text(content: Dict[str, Any]) -> str:
        """Create flattened, searchable text from content"""
        text_parts = []
        
        def flatten_dict(d: Dict, prefix=''):
            for k, v in d.items():
                if isinstance(v, dict):
                    flatten_dict(v, f"{k} - ")
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            flatten_dict(item, f"{k} - ")
                        else:
                            text_parts.append(f"{prefix}{k}: {item}")
                else:
                    text_parts.append(f"{prefix}{k}: {v}")
        
        flatten_dict(content.get('content', {}))
        return "\n".join(text_parts)
