import os
import tempfile
import logging
from typing import List, Optional
from datetime import datetime
import pytesseract
import fitz  # PyMuPDF
from PIL import Image
import io
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import traceback
import numpy as np
import cv2
from utils.markdown_formatter import MarkdownFormatter
import google.generativeai as genai

logger = logging.getLogger(__name__)

class UnifiedDocumentProcessor:
    """Handle both vector storage and CRUD operations"""
    
    def __init__(self, vectorstore):
        self.vectorstore = vectorstore
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )
        logger.setLevel(logging.DEBUG)  # Set to DEBUG for more verbose logging
        self.min_text_threshold = 10  # Minimum characters to consider a page as text-based
        self.markdown_dir = "extracted_text"
        self.markdown_formatter = MarkdownFormatter()
        os.makedirs(self.markdown_dir, exist_ok=True)
        self.quality_threshold = 0.7  # Minimum quality score for Tesseract output
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.gemini_model = genai.GenerativeModel("gemini-2.5-flash-preview-04-17")
        self.image_analyze_prompt = """
        Analyze this image from a construction/engineering document:
        1. Describe what is shown in the image
        2. Identify any technical details (measurements, specifications, etc.)
        3. Note any relevant markings, labels, or annotations
        4. Explain the context/purpose of this image in construction documentation
        
        Format output in clear, professional language. 
        """

    def extract_text(self, file) -> dict:
        """Extract text with quality-based OCR cascade"""
        try:
            logger.debug(f"Starting text extraction for {file.name} ({file.type})")
            # Store original file position
            original_position = file.tell()
            file_content = file.read()
            file.seek(original_position)  # Reset file position
            
            if file.type == 'application/pdf':
                result = self._process_pdf(file_content)
            elif file.type.startswith('image/'):
                image = Image.open(io.BytesIO(file_content))
                result = self._process_image_with_cascade(image)
            elif file.type == 'text/plain':
                return {
                    'text': file_content.decode('utf-8'),
                    'ocr_provider': 'native',
                    'quality_score': 1.0
                }
            else:
                raise ValueError(f"Unsupported file type: {file.type}")
                
            return result
            
        except Exception as e:
            logger.error(f"Error extracting text: {str(e)}")
            return {'text': '', 'ocr_provider': None, 'quality_score': 0.0}

    def _process_pdf(self, content) -> dict:
        """Process PDF with cascading OCR"""
        pdf = fitz.open(stream=content, filetype="pdf")
        result = {
            'text': '',
            'ocr_provider': None,
            'quality_score': 0.0
        }
        
        try:
            for page_num in range(pdf.page_count):
                page = pdf[page_num]
                page_text = page.get_text()
                
                if len(page_text.strip()) < self.min_text_threshold:
                    # Convert page to image for OCR
                    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_result = self._process_image_with_cascade(img)
                    
                    result['text'] += page_result['text'] + '\n'
                    result['ocr_provider'] = page_result['ocr_provider']
                    result['quality_score'] = max(result['quality_score'], 
                                                page_result['quality_score'])
                else:
                    result['text'] += page_text + '\n'
                    result['ocr_provider'] = 'native'
                    result['quality_score'] = 1.0
                    
        finally:
            pdf.close()
        return result

    def _process_image_with_cascade(self, image) -> dict:
        """Process image with Tesseract first, fall back to Gemini if needed"""
        # Try Tesseract first
        enhanced_image = self._enhance_image_for_ocr(image)
        tesseract_text = pytesseract.image_to_string(enhanced_image, lang='eng+ind')
        
        # Assess Tesseract output quality
        quality_score = self._assess_text_quality(tesseract_text)
        
        if quality_score >= self.quality_threshold:
            return {
                'text': tesseract_text,
                'ocr_provider': 'tesseract',
                'quality_score': quality_score
            }
        
        # If quality is poor, try Gemini
        try:
            logger.info("Text quality below threshold, using Gemini for enhancement")
            gemini_prompt = """
            Extract and enhance the text from this image:
            1. Extract all visible text accurately
            2. Maintain document structure and formatting
            3. Preserve any headers, footers, and special sections
            4. Format numbers and special characters correctly
            5. Indicate any uncertainty with [?]
            
            Output the enhanced text only, no explanations.
            """
            
            gemini_response = self.gemini_model.generate_content([gemini_prompt, image])
            enhanced_text = gemini_response.text
            
            # Compare and combine results if needed
            combined_text = self._combine_ocr_results(tesseract_text, enhanced_text)
            
            return {
                'text': combined_text,
                'ocr_provider': 'gemini',
                'quality_score': 0.9  # Gemini typically provides better quality
            }
            
        except Exception as e:
            logger.error(f"Gemini enhancement failed: {str(e)}, using Tesseract result")
            return {
                'text': tesseract_text,
                'ocr_provider': 'tesseract_fallback',
                'quality_score': quality_score
            }

    def _assess_text_quality(self, text: str) -> float:
        """Assess the quality of OCR text"""
        if not text.strip():
            return 0.0
            
        words = text.split()
        if not words:
            return 0.0
            
        # Quality metrics
        word_count = len(words)
        avg_word_len = sum(len(w) for w in words) / word_count
        readable_words = sum(1 for w in words if len(w) > 1 and w.isalnum())
        
        # Calculate score (0.0 to 1.0)
        quality_score = (
            (readable_words / word_count * 0.6) +  # Weight readability higher
            (min(avg_word_len / 5.0, 1.0) * 0.4)  # Reasonable word length
        )
        
        return quality_score

    def _combine_ocr_results(self, tesseract_text: str, gemini_text: str) -> str:
        """Intelligently combine OCR results when possible"""
        if not tesseract_text.strip():
            return gemini_text
            
        if not gemini_text.strip():
            return tesseract_text
            
        # Use Gemini's structure but preserve any clearly correct Tesseract sections
        tesseract_paragraphs = tesseract_text.split('\n\n')
        gemini_paragraphs = gemini_text.split('\n\n')
        
        # Keep Gemini paragraphs but insert any high-quality Tesseract paragraphs
        result_paragraphs = []
        for g_para in gemini_paragraphs:
            # Find best matching Tesseract paragraph
            best_match = max(tesseract_paragraphs, 
                           key=lambda t: self._similarity_score(g_para, t))
            
            # If Tesseract version seems more accurate, use it
            if self._assess_text_quality(best_match) > 0.8:
                result_paragraphs.append(best_match)
            else:
                result_paragraphs.append(g_para)
                
        return '\n\n'.join(result_paragraphs)

    def _similarity_score(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text snippets"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0

    def _enhance_image_for_ocr(self, image):
        """Enhance image quality for better OCR results"""
        try:
            # Convert PIL Image to OpenCV format
            img = np.array(image)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply adaptive thresholding
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            
            # Noise reduction
            denoised = cv2.fastNlMeansDenoising(binary)
            
            # Increase contrast
            enhanced = cv2.convertScaleAbs(denoised, alpha=1.5, beta=0)
            
            # Convert back to PIL Image
            return Image.fromarray(enhanced)
            
        except Exception as e:
            logger.warning(f"Image enhancement failed: {str(e)}, using original image")
            return image

    def _extract_images_from_pdf(self, pdf_document) -> list:
        """Extract images from PDF pages"""
        images_data = []
        for page_num in range(pdf_document.page_count):
            page = pdf_document[page_num]
            image_list = page.get_images()
            
            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Convert to PIL Image
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    # Get Gemini analysis
                    try:
                        analysis = self.gemini_model.generate_content(
                            [self.image_analyze_prompt, image]
                        )
                        
                        images_data.append({
                            'page': page_num + 1,
                            'index': img_index + 1,
                            'analysis': analysis.text,
                            'image': image
                        })
                    except Exception as e:
                        logger.error(f"Image analysis failed: {str(e)}")
                        
                except Exception as e:
                    logger.error(f"Image extraction failed: {str(e)}")
                    continue
                    
        return images_data

    def _format_image_analyses(self, images_data: list) -> str:
        """Format image analyses for markdown"""
        if not images_data:
            return ""
            
        md_parts = [
            "\n## Document Images Analysis\n"
        ]
        
        for img_data in images_data:
            md_parts.extend([
                f"\n### Image {img_data['index']} (Page {img_data['page']})",
                "\n**Analysis:**",
                img_data['analysis'],
                "\n"
            ])
            
        return "\n".join(md_parts)

    def process_document(self, file) -> dict:
        """Process document with debugging output"""
        try:
            logger.info(f"Starting to process {file.name}")
            
            # Store original file position and get content
            original_position = file.tell()
            file_content = file.read()
            file.seek(original_position)
            
            # Extract text
            extraction_result = self.extract_text(file)
            text = extraction_result['text']
            if not text:
                return {'success': False, 'error': 'No text could be extracted'}

            # Create chunks
            chunks = self.text_splitter.split_text(text)
            if not chunks:
                return {'success': False, 'error': 'Text splitting produced no chunks'}

            # Extract metadata
            metadata = {
                'title': os.path.splitext(file.name)[0],
                'file_title': file.name,
                'source': file.name,
                'file_type': file.type,
                'processed_at': datetime.now().isoformat(),
                'total_chars': len(text),
                'ocr_provider': extraction_result['ocr_provider'],
                'quality_score': extraction_result['quality_score']
            }

            # Extract and analyze images if PDF
            images_data = []
            if file.type == 'application/pdf':
                pdf_document = fitz.open(stream=file_content, filetype="pdf")
                try:
                    images_data = self._extract_images_from_pdf(pdf_document)
                finally:
                    pdf_document.close()
            elif file.type.startswith('image/'):
                # Single image file
                image = Image.open(io.BytesIO(file_content))
                try:
                    analysis = self.gemini_model.generate_content(
                        [self.image_analyze_prompt, image]
                    )
                    images_data.append({
                        'page': 1,
                        'index': 1,
                        'analysis': analysis.text,
                        'image': image
                    })
                except Exception as e:
                    logger.error(f"Image analysis failed: {str(e)}")

            # Add image analyses to content
            image_analyses = self._format_image_analyses(images_data)
            content = {
                'content': text + image_analyses,  # Add image analyses to content
                'metadata': metadata,
                'title': metadata['title']
            }
            
            layout_info = {
                'file_info': {
                    'name': file.name,
                    'type': file.type,
                    'size': len(text)
                },
                'processing_info': {
                    'timestamp': metadata['processed_at'],
                    'ocr_used': file.type.startswith('image/')
                }
            }

            # Save markdown file
            markdown_path = self._save_markdown(content, layout_info)
            if markdown_path:
                metadata['markdown_path'] = markdown_path

            # Create documents for vectorstore
            documents = []
            for i, chunk in enumerate(chunks):
                doc_metadata = metadata.copy()
                doc_metadata['chunk_index'] = i
                documents.append(Document(
                    page_content=chunk,
                    metadata=doc_metadata
                ))

            # Add to vectorstore
            self.vectorstore.add_documents(documents)
            
            return {
                'success': True,
                'metadata': metadata,
                'document_count': len(documents),
                'total_chars': len(text)
            }

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            logger.error(traceback.format_exc())
            return {'success': False, 'error': str(e)}

    def _save_markdown(self, content: dict, layout_info: dict) -> str:
        """Save document content as markdown file"""
        try:
            markdown_content = self.markdown_formatter.format_document(content, layout_info)
            
            # Create safe filename
            safe_filename = "".join(c for c in content['metadata']['file_title'] 
                                  if c.isalnum() or c in (' -_.')).rstrip()
            safe_filename = safe_filename.replace(' ', '_')
            if not safe_filename.endswith('.md'):
                safe_filename += '.md'
                
            filepath = os.path.join(self.markdown_dir, safe_filename)
            
            # Save markdown file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
                
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving markdown file: {str(e)}")
            return None

    def process_multiple(self, files: List) -> List[dict]:
        """Process multiple documents"""
        results = []
        for file in files:
            result = self.process_document(file)
            results.append({
                'filename': file.name,
                'success': result['success'],
                'error': result.get('error', None)
            })
        return results