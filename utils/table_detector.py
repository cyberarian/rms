import cv2
import numpy as np
from typing import List, Dict, Any, Tuple
import pytesseract
import re
import logging

logger = logging.getLogger(__name__)

class TableDetector:
    def __init__(self):
        self.min_table_area = 100
        self.cell_threshold = 10
        self.header_patterns = [
            r'^(NO\.?|NOMOR)$',
            r'^(NAMA|DESKRIPSI|URAIAN).*$',
            r'^(QTY|JUMLAH|VOLUME).*$',
            r'^(SATUAN|UNIT).*$',
            r'^(HARGA|PRICE).*$',
            r'^(TOTAL|AMOUNT).*$'
        ]

    def detect_tables(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect and extract tables from image"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Detect lines
            horizontal = self._detect_lines(gray, 'horizontal')
            vertical = self._detect_lines(gray, 'vertical')
            
            # Find table boundaries
            tables = self._find_table_boundaries(horizontal, vertical)
            
            # Extract and structure table content
            structured_tables = []
            for table in tables:
                cells = self._extract_cells(gray, table)
                headers = self._identify_headers(cells[0] if cells else [])
                content = self._structure_table(cells[1:], headers)
                structured_tables.append({
                    'headers': headers,
                    'content': content,
                    'bounds': table
                })
                
            return structured_tables
            
        except Exception as e:
            logger.error(f"Table detection failed: {str(e)}")
            return []

    def _detect_lines(self, gray: np.ndarray, direction: str) -> np.ndarray:
        """Detect lines in specified direction"""
        # Implementation details
        pass

    def _extract_cells(self, img: np.ndarray, bounds: Tuple) -> List[List[str]]:
        """Extract text from table cells with case preservation"""
        try:
            cell_text = []
            # Extract cell boundaries
            # For each cell:
            #   - Extract text using pytesseract
            #   - Preserve original case
            #   - Clean and normalize whitespace
            #   - Detect numerical values and formatting
            return cell_text
        except Exception as e:
            logger.error(f"Cell extraction failed: {str(e)}")
            return []

    def _identify_headers(self, row: List[str]) -> List[str]:
        """Identify table headers with pattern matching"""
        headers = []
        for cell in row:
            matched = False
            for pattern in self.header_patterns:
                if re.match(pattern, cell.strip().upper()):
                    headers.append(cell.strip())
                    matched = True
                    break
            if not matched:
                headers.append(cell.strip())
        return headers

    def _structure_table(self, rows: List[List[str]], headers: List[str]) -> List[Dict[str, str]]:
        """Structure table data with relationship preservation"""
        structured_data = []
        for row in rows:
            row_data = {}
            for i, cell in enumerate(row):
                if i < len(headers):
                    # Preserve case for non-numeric values
                    if not cell.strip().replace('.', '').isdigit():
                        row_data[headers[i]] = cell.strip()
                    else:
                        # Convert numeric strings to proper format
                        row_data[headers[i]] = self._format_numeric(cell)
            structured_data.append(row_data)
        return structured_data

    def _format_numeric(self, value: str) -> str:
        """Format numeric values while preserving original format"""
        try:
            # Remove thousands separators and convert decimal separator
            clean_value = value.replace(',', '').replace('.', '').strip()
            if clean_value.isdigit():
                num = int(clean_value)
                # Format with thousands separator
                return f"{num:,}"
            return value
        except:
            return value
