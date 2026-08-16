"""
PDF Renderer Module - Renders PDF pages as images for preview.
"""
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from io import BytesIO
from typing import Tuple


class PDFRenderer:
    """Renders PDF pages as images for preview and display."""
    
    def __init__(self, doc: fitz.Document):
        self.doc = doc
    
    def render_page(
        self,
        page_number: int,
        zoom: float = 1.0,
        max_width: int = 1200,
        max_height: int = 1600
    ) -> bytes:
        """
        Render a page as PNG image.
        
        Args:
            page_number: Page number (1-indexed)
            zoom: Zoom level (1.0 = 100%)
            max_width: Maximum output width
            max_height: Maximum output height
            
        Returns:
            PNG image bytes
        """
        if page_number < 1 or page_number > len(self.doc):
            raise ValueError(f"Invalid page number: {page_number}")
        
        page = self.doc[page_number - 1]
        
        # Calculate zoom to fit within max dimensions
        page_width = page.rect.width
        page_height = page.rect.height
        
        zoom_x = max_width / page_width
        zoom_y = max_height / page_height
        effective_zoom = min(zoom_x, zoom_y, zoom)
        
        # Create transformation matrix
        mat = fitz.Matrix(effective_zoom, effective_zoom)
        
        # Render page
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PNG
        return pix.tobytes("png")
    
    def render_page_region(
        self,
        page_number: int,
        region: Tuple[float, float, float, float],
        zoom: float = 1.0
    ) -> bytes:
        """
        Render a specific region of a page.
        
        Args:
            page_number: Page number (1-indexed)
            region: (x0, y0, x1, y1) region coordinates
            zoom: Zoom level
            
        Returns:
            PNG image bytes
        """
        if page_number < 1 or page_number > len(self.doc):
            raise ValueError(f"Invalid page number: {page_number}")
        
        page = self.doc[page_number - 1]
        
        # Create clip rectangle
        clip = fitz.Rect(region)
        
        # Create transformation matrix
        mat = fitz.Matrix(zoom, zoom)
        
        # Render clipped region
        pix = page.get_pixmap(matrix=mat, clip=clip)
        
        return pix.tobytes("png")
    
    def render_page_thumbnail(
        self,
        page_number: int,
        max_size: int = 200
    ) -> bytes:
        """
        Render a page thumbnail.
        
        Args:
            page_number: Page number (1-indexed)
            max_size: Maximum thumbnail dimension
            
        Returns:
            PNG image bytes
        """
        return self.render_page(
            page_number,
            zoom=1.0,
            max_width=max_size,
            max_height=max_size
        )
    
    def render_page_with_annotations(
        self,
        page_number: int,
        annotations: list,
        zoom: float = 1.0
    ) -> bytes:
        """
        Render a page with annotations highlighted.
        
        Args:
            page_number: Page number (1-indexed)
            annotations: List of bounding boxes to highlight
            zoom: Zoom level
            
        Returns:
            PNG image bytes
        """
        if page_number < 1 or page_number > len(self.doc):
            raise ValueError(f"Invalid page number: {page_number}")
        
        page = self.doc[page_number - 1]
        
        # Create transformation matrix
        mat = fitz.Matrix(zoom, zoom)
        
        # Render page
        pix = page.get_pixmap(matrix=mat)
        
        return pix.tobytes("png")
