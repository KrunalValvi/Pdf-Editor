"""
PDF Reader Module - Handles opening, analyzing, and extracting information from PDFs.
"""
try:
    import pymupdf as fitz
except ImportError:
    import fitz
import os
import tempfile
import shutil
from typing import Dict, List, Optional, Tuple
from ..models.pdf_models import PDFInfo, PageInfo, TextBlock


class PDFReader:
    """Handles PDF file operations and text extraction."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.temp_dir = tempfile.mkdtemp(prefix="pdf_editor_")
        self.temp_file = os.path.join(self.temp_dir, os.path.basename(file_path))
        shutil.copy2(file_path, self.temp_file)
        self.doc = None
        
    def open(self, password: Optional[str] = None) -> bool:
        """Open the PDF file."""
        try:
            self.doc = fitz.open(self.temp_file)
            if self.doc.is_encrypted:
                if password:
                    result = self.doc.authenticate(password)
                    if not result:
                        return False
                else:
                    return False
            return True
        except Exception as e:
            raise Exception(f"Failed to open PDF: {str(e)}")
    
    def get_info(self) -> PDFInfo:
        """Get PDF metadata and page information."""
        if not self.doc:
            raise Exception("PDF not opened")
        
        metadata = self.doc.metadata or {}
        pages = []
        
        for i in range(len(self.doc)):
            page = self.doc[i]
            pages.append(PageInfo(
                page_number=i + 1,
                width=page.rect.width,
                height=page.rect.height,
                rotation=page.rotation
            ))
        
        return PDFInfo(
            filename=os.path.basename(self.file_path),
            page_count=len(self.doc),
            metadata=metadata,
            pages=pages,
            is_encrypted=self.doc.is_encrypted,
            file_size=os.path.getsize(self.file_path)
        )
    
    def get_page_text_blocks(self, page_number: int) -> List[TextBlock]:
        """Extract all text blocks from a specific page."""
        if not self.doc:
            raise Exception("PDF not opened")
        
        if page_number < 1 or page_number > len(self.doc):
            raise Exception(f"Invalid page number: {page_number}")
        
        page = self.doc[page_number - 1]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        
        text_blocks = []
        
        for block in blocks.get("blocks", []):
            if block["type"] == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if text:
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            font_info = span.get("font", "")
                            size = span.get("size", 12)
                            color = span.get("color", 0)
                            
                            # Convert color from integer to RGB tuple
                            r = ((color >> 16) & 255) / 255.0
                            g = ((color >> 8) & 255) / 255.0
                            b = (color & 255) / 255.0
                            
                            text_blocks.append(TextBlock(
                                text=text,
                                bbox=list(bbox),
                                font_name=font_info,
                                font_size=size,
                                color=(r, g, b),
                                page_number=page_number
                            ))
        
        return text_blocks
    
    def get_page_image(self, page_number: int, zoom: float = 1.0) -> bytes:
        """Render a page as an image."""
        if not self.doc:
            raise Exception("PDF not opened")
        
        if page_number < 1 or page_number > len(self.doc):
            raise Exception(f"Invalid page number: {page_number}")
        
        page = self.doc[page_number - 1]
        
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        return pix.tobytes("png")
    
    def get_page_text(self, page_number: int) -> str:
        """Get all text from a page as a string."""
        if not self.doc:
            raise Exception("PDF not opened")
        
        if page_number < 1 or page_number > len(self.doc):
            raise Exception(f"Invalid page number: {page_number}")
        
        page = self.doc[page_number - 1]
        return page.get_text("text")
    
    def close(self):
        """Close the PDF and cleanup."""
        if self.doc:
            self.doc.close()
            self.doc = None
        
        # Cleanup temp directory
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except:
            pass
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
