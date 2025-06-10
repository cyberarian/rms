import pytesseract
import cv2
import numpy as np
from PIL import Image
import pandas as pd
import io
import fitz
from typing import Dict, List, Tuple, Any

class StructuredOCR:
    def __init__(self):
        self.config = '--oem 3 --psm 6'
        
    def detect_tables(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect table boundaries in image"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Threshold
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        
        # Detect horizontal lines
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
        horizontal_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, horizontal_kernel)
        
        # Detect vertical lines
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40))
        vertical_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, vertical_kernel)
        
        # Combine lines
        table_mask = cv2.add(horizontal_lines, vertical_lines)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        return [cv2.boundingRect(c) for c in contours]

    def extract_table_data(self, image: np.ndarray, table_bounds: Tuple[int, int, int, int]) -> pd.DataFrame:
        """Extract structured data from detected table"""
        x, y, w, h = table_bounds
        table_roi = image[y:y+h, x:x+w]
        
        # OCR with table structure preservation
        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
        table_text = pytesseract.image_to_data(table_roi, config=custom_config, output_type=pytesseract.Output.DATAFRAME)
        
        # Process into structured format
        structured_data = []
        current_row = []
        last_row = -1
        
        for _, row in table_text.iterrows():
            if row['conf'] > 0:  # Filter valid text
                if row['block_num'] > 0:
                    if row['line_num'] != last_row:
                        if current_row:
                            structured_data.append(current_row)
                        current_row = []
                        last_row = row['line_num']
                    current_row.append(row['text'])
        
        if current_row:
            structured_data.append(current_row)
            
        return pd.DataFrame(structured_data)

    def process_document(self, file_bytes: bytes, file_type: str) -> Dict[str, Any]:
        """Process document with structure preservation"""
        if file_type == 'application/pdf':
            doc = fitz.open(stream=file_bytes, filetype="pdf")
            text_data = []
            tables = []
            
            for page in doc:
                # Extract text with formatting
                text_dict = page.get_text("dict")
                text_data.append(text_dict)
                
                # Convert page to image for table detection
                pix = page.get_pixmap()
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img_np = np.array(img)
                
                # Detect and extract tables
                table_regions = self.detect_tables(img_np)
                for bounds in table_regions:
                    table_data = self.extract_table_data(img_np, bounds)
                    tables.append({
                        'page': page.number + 1,
                        'bounds': bounds,
                        'data': table_data
                    })
            
            return {
                'text_blocks': text_data,
                'tables': tables,
                'structure_preserved': True
            }
            
        elif file_type.startswith('image/'):
            image = Image.open(io.BytesIO(file_bytes))
            img_np = np.array(image)
            
            # Extract text with layout
            text_data = pytesseract.image_to_data(img_np, config=self.config, output_type=pytesseract.Output.DICT)
            
            # Detect and extract tables
            table_regions = self.detect_tables(img_np)
            tables = []
            for bounds in table_regions:
                table_data = self.extract_table_data(img_np, bounds)
                tables.append({
                    'bounds': bounds,
                    'data': table_data
                })
                
            return {
                'text_blocks': text_data,
                'tables': tables,
                'structure_preserved': True
            }
        
        return {
            'error': 'Unsupported file type',
            'structure_preserved': False
        }
