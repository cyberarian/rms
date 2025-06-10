import streamlit as st
import google.generativeai as genai
from groq import Groq
from huggingface_hub import InferenceClient
from PIL import Image, ImageEnhance, ImageFilter
import numpy as np
import cv2
import pytesseract
import os
import io
import base64
import logging
import traceback
from tenacity import retry, stop_after_attempt, wait_exponential
import fitz  # PyMuPDF
import re
from datetime import datetime
from transformers import AutoProcessor, AutoModelForVision2Seq
import torch

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe' # windows
#pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract' # linux

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedModelManager:
    """Enhanced model management with multiple AI models"""
    
    def __init__(self):
        # Initialize existing models
        self.groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.gemini_model = genai.GenerativeModel("gemini-2.5-pro-preview-03-25")
        
        # Initialize Donut model
        self.processor = AutoProcessor.from_pretrained("microsoft/donut-base-finetuned-docvqa")
        self.model = AutoModelForVision2Seq.from_pretrained("microsoft/donut-base-finetuned-docvqa")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def enhance_image(self, image):
        """Advanced image preprocessing with multiple enhancement techniques"""
        try:
            img = Image.fromarray(np.array(image)) if isinstance(image, Image.Image) else image
            
            # Apply multiple enhancement techniques
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.5)
            
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.3)
            
            # Apply adaptive thresholding
            img = img.filter(ImageFilter.EDGE_ENHANCE)
            img = img.convert('L')  # Convert to grayscale
            
            # Convert to numpy array for OpenCV operations
            img_array = np.array(img)
            
            # Apply additional OpenCV enhancements
            denoised = cv2.fastNlMeansDenoising(img_array)
            binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                         cv2.THRESH_BINARY, 11, 2)
            
            # Deskew if needed
            coords = np.column_stack(np.where(binary > 0))
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = 90 + angle
            
            (h, w) = binary.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(binary, M, (w, h), 
                                    flags=cv2.INTER_CUBIC, 
                                    borderMode=cv2.BORDER_REPLICATE)
            
            return Image.fromarray(rotated)
            
        except Exception as e:
            logger.error(f"Image enhancement error: {str(e)}")
            return image  # Return original image if enhancement fails

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def analyze_with_multiple_models(self, image, text):
        """Combine multiple AI models for better analysis"""
        try:
            results = {
                'title': None,
                'description': None,
                'date': None,
                'confidence': 0.0
            }
            
            # Use Tesseract OCR results
            ocr_results = [(None, line.strip(), 0.9) for line in text.split('\n') if line.strip()]
            
            # Use Donut for document understanding
            inputs = self.processor(image, return_tensors="pt")
            outputs = self.model.generate(**inputs, max_length=512)
            donut_text = self.processor.decode(outputs[0], skip_special_tokens=True)
            
            # Use Gemini for high-level analysis
            gemini_prompt = f"""
            Analyze this document and extract:
            1. Document title (usually at top, often in caps)
            2. Main description/summary (first paragraph)
            3. Any dates mentioned
            4. Document type/classification
            
            Context from OCR: {text}
            Additional context: {donut_text}
            """
            
            gemini_response = self.gemini_model.generate_content([gemini_prompt, image])
            
            # Combine and validate results
            results = self._combine_model_results(ocr_results, donut_text, gemini_response.text)
            
            return results
            
        except Exception as e:
            logger.error(f"Multi-model analysis error: {str(e)}")
            return None

    def _combine_model_results(self, ocr_results, donut_text, gemini_text):
        """Combine and validate results from multiple models"""
        combined = {
            'title': None,
            'description': None,
            'date': None,
            'confidence': 0.0,
            'metadata': {}
        }
        
        # Extract title (prefer OCR for headers)
        potential_titles = [text for (bbox, text, conf) in ocr_results[:3] if conf > 0.8]
        if potential_titles:
            combined['title'] = max(potential_titles, key=len)
        
        # Use Donut for structural understanding
        if 'title:' in donut_text.lower():
            donut_parts = donut_text.split('\n')
            for part in donut_parts:
                if 'title:' in part.lower():
                    combined['metadata']['donut_title'] = part.split(':', 1)[1].strip()
        
        # Use Gemini for high-level understanding
        if gemini_text:
            gemini_parts = gemini_text.split('\n')
            for part in gemini_parts:
                if ':' in part:
                    key, value = part.split(':', 1)
                    key = key.strip().lower()
                    if key in ['title', 'description', 'date']:
                        combined[key] = value.strip()
        
        # Calculate confidence based on agreement between models
        combined['confidence'] = self._calculate_combined_confidence(combined)
        
        return combined

    def _calculate_combined_confidence(self, results):
        """Calculate confidence score based on model agreement"""
        confidence = 0.0
        
        if results['title'] and results.get('metadata', {}).get('donut_title'):
            # Compare titles from different models
            title_similarity = self._calculate_similarity(
                results['title'],
                results['metadata']['donut_title']
            )
            confidence += title_similarity * 0.4
        
        if results['description']:
            confidence += 0.3
            
        if results['date']:
            confidence += 0.3
            
        return min(confidence, 1.0)

    def _calculate_similarity(self, text1, text2):
        """Calculate text similarity score"""
        if not text1 or not text2:
            return 0.0
            
        # Simple similarity based on common words
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0

class TextProcessor:
    @staticmethod
    def format_text(text):
        """Format and structure extracted text"""
        if not text:
            return ""
        
        # Split into lines and clean
        lines = text.splitlines()
        lines = [line.strip() for line in lines if line.strip()]
        
        # Detect paragraphs
        formatted_lines = []
        current_paragraph = []
        
        for line in lines:
            if not line[-1] in '.!?':
                current_paragraph.append(line)
            else:
                current_paragraph.append(line)
                formatted_lines.append(' '.join(current_paragraph))
                current_paragraph = []
        
        if current_paragraph:
            formatted_lines.append(' '.join(current_paragraph))
        
        return '\n\n'.join(formatted_lines)

    @staticmethod
    def calculate_metrics(text):
        """Calculate text metrics"""
        words = text.split()
        lines = text.splitlines()
        paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        return {
            "word_count": len(words),
            "line_count": len(lines),
            "paragraph_count": len(paragraphs),
            "char_count": len(text)
        }

class DocumentMetadataExtractor:
    """Enhanced document metadata extraction using hybrid analysis"""
    
    def __init__(self):
        self.model_manager = EnhancedModelManager()
    
    def extract_date_patterns(self, text):
        """Extract potential dates from text using multiple patterns"""
        date_patterns = [
            r'\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b',  # DD-MM-YYYY or DD/MM/YYYY
            r'\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b',  # YYYY-MM-DD or YYYY/MM/DD
            r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b',  # 01 January 2024
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b'  # January 01, 2024
        ]
        
        found_dates = []
        for pattern in date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            found_dates.extend([match.group() for match in matches])
        
        return found_dates

    def extract_title_candidates(self, text_lines):
        """Extract potential title candidates from text"""
        candidates = []
        
        for i, line in enumerate(text_lines[:5]):  # Check first 5 lines
            line = line.strip()
            if len(line) > 10 and any(word.isupper() for word in line.split()):
                candidates.append({
                    'text': line,
                    'position': i,
                    'caps_ratio': sum(1 for c in line if c.isupper()) / len(line),
                    'length': len(line)
                })
        
        # Sort by position and caps ratio
        candidates.sort(key=lambda x: (x['position'], -x['caps_ratio']))
        return candidates

    def analyze_document(self, image_file):
        """Enhanced document analysis with metadata extraction"""
        try:
            # Initial OCR with custom config
            image = Image.open(image_file)
            enhanced_image = self.model_manager.enhance_image(image)
            
            # Optimized OCR config for document structure
            custom_config = r'--oem 3 --psm 3 -l eng+ind'
            ocr_text = pytesseract.image_to_string(enhanced_image, config=custom_config)
            
            # Split text into lines for analysis
            text_lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
            
            # Extract metadata using both OCR and Gemini
            prompt = """
            Your task is to extract text for automatic document analysis and accurately generate a Description based on the first two pages. Identify and extract the Document Date, Title (as stated in capital letters), and File Name (including the file type extension) with precision.
            """
            
            gemini_response = self.model_manager.gemini_model.generate_content([
                prompt,
                image
            ])
            
            # Combine OCR and Gemini results
            title_candidates = self.extract_title_candidates(text_lines)
            dates = self.extract_date_patterns(ocr_text)
            
            # Extract metadata
            metadata = {
                'title': title_candidates[0]['text'] if title_candidates else '',
                'file_title': os.path.splitext(image_file.name)[0],
                'description': ' '.join(text_lines[1:4]) if len(text_lines) > 1 else '',
                'doc_date': dates[0] if dates else None,
                'confidence_score': None
            }
            
            # Enhance with Gemini results
            if gemini_response:
                gemini_text = gemini_response.text
                metadata.update(self._parse_gemini_response(gemini_text))
            
            # Calculate confidence score
            metadata['confidence_score'] = self._calculate_confidence(metadata)
            
            return metadata
            
        except Exception as e:
            logger.error(f"Document analysis error: {str(e)}")
            return None

    def _parse_gemini_response(self, response_text):
        """Parse structured response from Gemini"""
        parsed = {}
        try:
            lines = response_text.split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().lower()
                    value = value.strip()
                    if key == 'title' and not parsed.get('title'):
                        parsed['title'] = value
                    elif key == 'description' and not parsed.get('description'):
                        parsed['description'] = value
                    elif key == 'date' and not parsed.get('doc_date'):
                        parsed['doc_date'] = value
        except Exception as e:
            logger.error(f"Error parsing Gemini response: {str(e)}")
        return parsed

    def _calculate_confidence(self, metadata):
        """Calculate confidence score for extracted metadata"""
        score = 0
        if metadata['title'] and len(metadata['title']) > 10:
            score += 0.3
        if metadata['description'] and len(metadata['description']) > 20:
            score += 0.3
        if metadata['doc_date']:
            score += 0.2
        if metadata['file_title']:
            score += 0.2
        return min(score, 1.0)

class ImageAnalyzer:
    def __init__(self):
        self.model_manager = EnhancedModelManager()
        self.metadata_extractor = DocumentMetadataExtractor()
        self.text_processor = TextProcessor()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def analyze_hybrid(self, image_file):
        """Enhanced hybrid analysis with better error handling"""
        try:
            # Convert file to PIL Image
            image = Image.open(image_file)
            
            # Process image
            enhanced_image = self.model_manager.enhance_image(image)
            
            # Extract text with multiple methods
            ocr_text = pytesseract.image_to_string(enhanced_image, 
                                                 config='--oem 3 --psm 3 -l eng+ind')
            
            # Get AI analysis
            analysis_results = self.model_manager.analyze_with_multiple_models(
                enhanced_image, ocr_text
            )
            
            # Process and format results
            formatted_text = self.text_processor.format_text(ocr_text)
            metrics = self.text_processor.calculate_metrics(formatted_text)
            
            return {
                "text": formatted_text,
                "original_ocr": ocr_text,
                "metadata": analysis_results,
                "confidence": analysis_results['confidence'] if analysis_results else 0.0,
                "metrics": metrics
            }
            
        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            logger.error(traceback.format_exc())
            return None

def analyze_document_content(file):
    """Extract and analyze text content from various document types"""
    try:
        if file.type == 'application/pdf':
            # Handle PDF files
            pdf = fitz.open(stream=file.read(), filetype="pdf")
            text = ""
            for page in pdf:
                text += page.get_text()
            return text
        elif file.type.startswith('image/'):
            # Handle image files
            return extract_text_from_image(file)
        else:
            # Handle text files
            return file.getvalue().decode('utf-8')
    except Exception as e:
        raise Exception(f"Error analyzing document content: {str(e)}")

def extract_text_from_image(file):
    """Extract text from image using OCR"""
    try:
        # Convert uploaded file to image
        image = Image.open(io.BytesIO(file.getvalue()))
        # Extract text using pytesseract
        text = pytesseract.image_to_string(image, lang='ind')
        return text
    except Exception as e:
        raise Exception(f"Error extracting text from image: {str(e)}")

def extract_date_from_text(text):
    """Extract date from text using regex patterns"""
    # Add various date format patterns
    date_patterns = [
        r'\d{2}[-/]\d{2}[-/]\d{4}',  # DD-MM-YYYY or DD/MM/YYYY
        r'\d{4}[-/]\d{2}[-/]\d{2}',  # YYYY-MM-DD or YYYY/MM/DD
        # Add more patterns as needed
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text)
        if match:
            try:
                # Convert matched date string to datetime object
                date_str = match.group()
                return datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                continue
    
    return None

def image_analyzer_main():
       
    st.markdown("""
        ### Memperkenalkan Sistem Ekstraksi Teks Canggih Kami

        Sistem canggih ini memanfaatkan kombinasi yang kuat antara pytesseract, pustaka Python yang menyediakan antarmuka ke mesin OCR Tesseract, dan Multimodal AI dari Google Gemini 2.0 Flash, sinergi ini memungkinkan sistem kami memberikan akurasi dan presisi ekstraksi teks yang optimal.

        #### Memulai dengan Unggah Gambar

        Untuk memulai proses analisis, cukup unggah gambar yang berisi teks yang ingin Anda ekstrak. Sistem kami kemudian akan memanfaatkan kemampuan canggih dari pytesseract dan Google Gemini:

        - Mengenali teks dengan tepat: Mengidentifikasi dan mengekstrak teks secara akurat dari gambar yang diunggah, termasuk jenis huruf, tata letak, dan bahasa.

        - Meningkatkan kualitas teks: Menerapkan penyempurnaan berbasis AI untuk menyempurnakan teks yang diekstrak, mengoreksi kesalahan, dan meningkatkan keterbacaan secara keseluruhan.

        - Menghasilkan output berkualitas tinggi: Memberikan Anda output teks yang bersih, terformat, dan mudah dibaca, siap untuk pemrosesan atau analisis lebih lanjut.

        Unggah Gambar Anda Sekarang
        
        Klik tombol unggah untuk memulai proses analisis. Sistem kami akan mengekstrak teks dengan cepat dan efisien dari gambar Anda, memanfaatkan kekuatan gabungan pytesseract dan Google Gemini untuk memberikan hasil yang optimal.
              
    """)
    
    uploaded_file = st.file_uploader(
        "Upload document",
        type=['png', 'jpg', 'jpeg']
    )
    
    if uploaded_file:
        analyzer = ImageAnalyzer()
        
        with st.spinner('Analyzing document...'):
            result = analyzer.analyze_hybrid(uploaded_file)
            
            if result["text"]:
                # Display metrics
                st.subheader("Document Analysis")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Confidence Score", f"{result['confidence']:.2%}")
                    st.metric("Word Count", result['metrics']['word_count'])
                
                with col2:
                    st.metric("Paragraphs", result['metrics']['paragraph_count'])
                    st.metric("Characters", result['metrics']['char_count'])
                
                # Display enhanced text
                st.subheader("Enhanced Text")
                st.write(result["text"])
                
                # Show original OCR
                with st.expander("View Original OCR Text"):
                    st.text(result["original_ocr"])
            else:
                st.error("No text could be extracted from the image")

if __name__ == "__main__":
    image_analyzer_main()