"""
PDF Exporter Module - Handles saving and exporting edited PDFs.
"""
try:
    import pymupdf as fitz
except ImportError:
    import fitz
import os
import shutil
from typing import Optional


class PDFExporter:
    """Handles PDF export and save operations."""
    
    def __init__(self, doc: fitz.Document, original_path: str):
        """
        Initialize exporter.
        
        Args:
            doc: PyMuPDF document
            original_path: Original PDF file path
        """
        self.doc = doc
        self.original_path = original_path
    
    def export(
        self,
        output_path: Optional[str] = None,
        preserve_metadata: bool = True
    ) -> str:
        """
        Export the edited PDF.
        
        Args:
            output_path: Output file path. If None, generates _edited suffix
            preserve_metadata: Whether to preserve original metadata
            
        Returns:
            Path to exported file
        """
        if output_path is None:
            # Generate output path with _edited suffix
            base, ext = os.path.splitext(self.original_path)
            output_path = f"{base}_edited{ext}"
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Save the document
        self.doc.save(output_path)
        
        return output_path
    
    def export_safe(
        self,
        output_dir: str,
        filename: Optional[str] = None,
        preserve_metadata: bool = True
    ) -> str:
        """
        Export PDF with safe filename handling.
        
        Args:
            output_dir: Output directory
            filename: Custom filename. If None, uses original with _edited suffix
            preserve_metadata: Whether to preserve original metadata
            
        Returns:
            Path to exported file
        """
        if filename is None:
            base = os.path.splitext(os.path.basename(self.original_path))[0]
            filename = f"{base}_edited.pdf"
        
        # Ensure filename is safe
        filename = self._sanitize_filename(filename)
        
        output_path = os.path.join(output_dir, filename)
        
        # Handle existing file
        if os.path.exists(output_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(output_path):
                output_path = os.path.join(output_dir, f"{base}_{counter}{ext}")
                counter += 1
        
        return self.export(output_path, preserve_metadata)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to remove invalid characters."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Remove leading/trailing spaces and dots
        filename = filename.strip('. ')
        
        return filename
    
    def create_backup(self) -> str:
        """Create a backup of the original file."""
        backup_dir = os.path.join(os.path.dirname(self.original_path), "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(
            backup_dir,
            f"backup_{os.path.basename(self.original_path)}"
        )
        
        shutil.copy2(self.original_path, backup_path)
        return backup_path
