"""
PDF Data Models - Pydantic models for PDF operations.
"""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class TextBlock(BaseModel):
    """Represents a text block in a PDF."""
    text: str
    bbox: List[float]  # [x0, y0, x1, y1]
    font_name: str
    font_size: float
    color: tuple  # RGB tuple (r, g, b) with values 0-1
    page_number: int


class PageInfo(BaseModel):
    """Information about a PDF page."""
    page_number: int
    width: float
    height: float
    rotation: int


class PDFInfo(BaseModel):
    """Information about a PDF document."""
    filename: str
    page_count: int
    metadata: Dict[str, Any]
    pages: List[PageInfo]
    is_encrypted: bool
    file_size: int


class TextReplaceRequest(BaseModel):
    """Request to replace text in a PDF."""
    page_number: int
    original_text: str
    new_text: str
    bbox: Optional[List[float]] = None
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    color: Optional[tuple] = None


class FooterReplaceRequest(BaseModel):
    """Request to replace footer text."""
    search_text: str
    new_text: str
    pages: Optional[List[int]] = None  # None means all pages
    case_sensitive: bool = False


class BatchFooterRequest(BaseModel):
    """Batch footer replacement request."""
    replacements: List[FooterReplaceRequest]
    file_ids: List[str]


class TextBlockResponse(BaseModel):
    """Response containing text blocks."""
    blocks: List[TextBlock]
    page_number: int


class ExportRequest(BaseModel):
    """Export request."""
    filename: Optional[str] = None
    output_dir: Optional[str] = None


class FindAcrossPagesRequest(BaseModel):
    """Request to find text across all pages."""
    search_text: str
    case_sensitive: bool = False


class TextOccurrence(BaseModel):
    """A single text occurrence found."""
    text: str
    bbox: List[float]
    page_number: int
    font_name: str
    font_size: float


class FindAcrossPagesResponse(BaseModel):
    """Response with all occurrences found."""
    search_text: str
    occurrences: List[TextOccurrence]
    total_count: int


class SmartFooterDetectResponse(BaseModel):
    """Detected footer elements."""
    elements: List[Dict[str, Any]]
    page_count: int


class SmartFooterReplaceRequest(BaseModel):
    """Replace a detected footer element."""
    element: Dict[str, Any]
    new_text: str
    pages: Optional[List[int]] = None


class FooterTemplateRequest(BaseModel):
    """Apply a footer template."""
    left: Optional[str] = None
    center: Optional[str] = None
    right: Optional[str] = None
    custom_vars: Optional[Dict[str, str]] = None
    pages: Optional[List[int]] = None


class PageNumberRequest(BaseModel):
    """Add or replace page numbers."""
    format_str: str = "Page {page} of {pages}"
    position: str = "bottom-center"
    start_at: int = 1
    skip_pages: Optional[List[int]] = None
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    font_color: Optional[tuple] = None
    bold: bool = False
    italic: bool = False
    pages: Optional[List[int]] = None


class ImageInsertRequest(BaseModel):
    """Insert an image."""
    page_number: int = 1
    x: float = 100
    y: float = 100
    width: Optional[float] = None
    height: Optional[float] = None
    apply_to_all: bool = False


class ImageInfoResponse(BaseModel):
    """Image info response."""
    width: float
    height: float
