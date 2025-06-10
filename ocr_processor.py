import pytesseract
from PIL import Image
import io
import logging

logger = logging.getLogger(__name__)

class OCRProcessor:
    def __init__(self):
        self.supported_langs = ['eng', 'ind']  # English and Indonesian
        
    def process_image(self, image_bytes, lang='eng'):
        """Process image bytes and return extracted text"""
        try:
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip()
        except Exception as e:
            logger.error(f"OCR processing error: {str(e)}")
            return None
            
    def process_pdf_page(self, page_image, lang='eng'):
        """Process a PDF page image and return extracted text"""
        try:
            text = pytesseract.image_to_string(page_image, lang=lang)
            return text.strip()
        except Exception as e:
            logger.error(f"PDF OCR processing error: {str(e)}")
            return None
