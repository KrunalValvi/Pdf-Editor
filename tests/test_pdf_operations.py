"""
Test suite for PDF Footer Editor
"""
import os
import sys
try:
    import pymupdf as fitz
except ImportError:
    import fitz
import tempfile
import shutil
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.pdf.reader import PDFReader
from app.pdf.text_detector import TextDetector
from app.pdf.footer_detector import FooterDetector
from app.pdf.text_replacer import TextReplacer
from app.pdf.renderer import PDFRenderer
from app.pdf.exporter import PDFExporter


class TestPDFGenerator:
    """Generate test PDFs for testing."""
    
    @staticmethod
    def create_simple_pdf(output_path: str, footer_text: str = "Page 1 | Company Name"):
        """Create a simple PDF with footer text."""
        doc = fitz.open()
        
        # Create a page
        page = doc.new_page(width=595, height=842)  # A4
        
        # Add some content
        page.insert_text(
            fitz.Point(100, 100),
            "This is a test document",
            fontsize=16,
            fontname="helv"
        )
        
        # Add footer text at the bottom
        page.insert_text(
            fitz.Point(100, 800),
            footer_text,
            fontsize=10,
            fontname="helv"
        )
        
        doc.save(output_path)
        doc.close()
    
    @staticmethod
    def create_multi_page_pdf(output_path: str, page_count: int = 5):
        """Create a multi-page PDF with consistent footer."""
        doc = fitz.open()
        
        for i in range(page_count):
            page = doc.new_page(width=595, height=842)
            
            # Add page content
            page.insert_text(
                fitz.Point(100, 100),
                f"Page {i + 1} Content",
                fontsize=16,
                fontname="helv"
            )
            
            # Add footer
            page.insert_text(
                fitz.Point(100, 800),
                f"Document ABC-123 | Page {i + 1} of {page_count}",
                fontsize=10,
                fontname="helv"
            )
        
        doc.save(output_path)
        doc.close()
    
    @staticmethod
    def create_pdf_with_images(output_path: str):
        """Create a PDF with images and text."""
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)
        
        # Add text
        page.insert_text(
            fitz.Point(100, 100),
            "Document with images",
            fontsize=16,
            fontname="helv"
        )
        
        # Add a simple rectangle as "image placeholder"
        shape = page.new_shape()
        shape.draw_rect(fitz.Rect(100, 200, 300, 400))
        shape.finish(color=(0.5, 0.5, 0.5))
        shape.commit()
        
        # Add footer
        page.insert_text(
            fitz.Point(100, 800),
            "Confidential | 2026",
            fontsize=10,
            fontname="helv"
        )
        
        doc.save(output_path)
        doc.close()


def test_pdf_reader():
    """Test PDF reading functionality."""
    print("Testing PDF Reader...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        TestPDFGenerator.create_simple_pdf(pdf_path)
        
        reader = PDFReader(pdf_path)
        assert reader.open(), "Failed to open PDF"
        
        info = reader.get_info()
        assert info.page_count == 1, f"Expected 1 page, got {info.page_count}"
        assert not info.is_encrypted, "PDF should not be encrypted"
        
        blocks = reader.get_page_text_blocks(1)
        assert len(blocks) > 0, "No text blocks found"
        
        print(f"  Found {len(blocks)} text blocks")
        for block in blocks:
            print(f"    - '{block.text}' at {block.bbox}")
        
        reader.close()
        print("  [OK] PDF Reader test passed")


def test_text_detector():
    """Test text detection functionality."""
    print("Testing Text Detector...")
    
    detector = TextDetector()
    
    from app.models.pdf_models import TextBlock
    
    # Create test blocks
    blocks = [
        TextBlock(
            text="Header text",
            bbox=[100, 50, 200, 70],
            font_name="helv",
            font_size=14,
            color=(0, 0, 0),
            page_number=1
        ),
        TextBlock(
            text="Footer text | Page 1",
            bbox=[100, 780, 250, 800],
            font_name="helv",
            font_size=10,
            color=(0, 0, 0),
            page_number=1
        )
    ]
    
    # Test finding text near position
    found = detector.find_text_near_position(blocks, 150, 790)
    assert found is not None, "Should find footer block"
    assert found.text == "Footer text | Page 1", "Wrong block found"
    
    # Test finding text by content
    results = detector.find_text_by_content(blocks, "Footer")
    assert len(results) == 1, "Should find one footer block"
    
    print("  [OK] Text Detector test passed")


def test_footer_detector():
    """Test footer detection functionality."""
    print("Testing Footer Detector...")
    
    detector = FooterDetector(detection_zone_percent=15.0)
    
    from app.models.pdf_models import TextBlock
    
    blocks = [
        TextBlock(
            text="Main content",
            bbox=[100, 100, 400, 120],
            font_name="helv",
            font_size=12,
            color=(0, 0, 0),
            page_number=1
        ),
        TextBlock(
            text="Footer | Page 1",
            bbox=[100, 790, 250, 810],
            font_name="helv",
            font_size=10,
            color=(0, 0, 0),
            page_number=1
        )
    ]
    
    footers = detector.detect_footers(blocks, page_height=842)
    assert len(footers) > 0, "Should detect footer"
    assert footers[0].text == "Footer | Page 1", "Wrong footer detected"
    
    print("  [OK] Footer Detector test passed")


def test_text_replacer():
    """Test text replacement functionality."""
    print("Testing Text Replacer...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        output_path = os.path.join(tmpdir, "test_edited.pdf")
        
        TestPDFGenerator.create_simple_pdf(pdf_path)
        
        reader = PDFReader(pdf_path)
        assert reader.open(), "Failed to open PDF"
        
        replacer = TextReplacer()
        
        # Get text blocks
        blocks = reader.get_page_text_blocks(1)
        assert len(blocks) > 0, "No text blocks"
        
        # Find footer block
        footer = None
        for block in blocks:
            if "Company" in block.text:
                footer = block
                break
        
        assert footer is not None, "Footer block not found"
        
        # Replace text
        success = replacer.replace_text(
            reader.doc,
            page_number=1,
            original_block=footer,
            new_text="New Company Name | 2026"
        )
        
        assert success, "Text replacement failed"
        
        # Save result
        reader.doc.save(output_path)
        reader.close()
        
        # Verify result
        reader2 = PDFReader(output_path)
        assert reader2.open(), "Failed to open edited PDF"
        
        blocks2 = reader2.get_page_text_blocks(1)
        found_new = any("New Company" in b.text for b in blocks2)
        assert found_new, "New text not found in edited PDF"
        
        reader2.close()
        print("  [OK] Text Replacer test passed")


def test_renderer():
    """Test PDF rendering functionality."""
    print("Testing PDF Renderer...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        TestPDFGenerator.create_simple_pdf(pdf_path)
        
        reader = PDFReader(pdf_path)
        assert reader.open(), "Failed to open PDF"
        
        renderer = PDFRenderer(reader.doc)
        
        # Test page rendering
        image_bytes = renderer.render_page(1, zoom=1.0)
        assert len(image_bytes) > 0, "Rendered image is empty"
        
        # Test thumbnail rendering
        thumb_bytes = renderer.render_page_thumbnail(1)
        assert len(thumb_bytes) > 0, "Thumbnail is empty"
        
        reader.close()
        print("  [OK] Renderer test passed")


def test_exporter():
    """Test PDF export functionality."""
    print("Testing PDF Exporter...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "test.pdf")
        TestPDFGenerator.create_simple_pdf(pdf_path)
        
        reader = PDFReader(pdf_path)
        assert reader.open(), "Failed to open PDF"
        
        exporter = PDFExporter(reader.doc, pdf_path)
        
        output_path = exporter.export_safe(
            output_dir=tmpdir,
            filename="custom_name.pdf"
        )
        
        assert os.path.exists(output_path), "Exported file not found"
        
        reader.close()
        print("  [OK] Exporter test passed")


def test_multi_page_pdf():
    """Test multi-page PDF handling."""
    print("Testing Multi-page PDF...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "multi.pdf")
        output_path = os.path.join(tmpdir, "multi_edited.pdf")
        
        TestPDFGenerator.create_multi_page_pdf(pdf_path, page_count=5)
        
        reader = PDFReader(pdf_path)
        assert reader.open(), "Failed to open PDF"
        
        info = reader.get_info()
        assert info.page_count == 5, f"Expected 5 pages, got {info.page_count}"
        
        replacer = TextReplacer()
        
        # Replace footer on all pages
        replacements = replacer.replace_text_on_all_pages(
            reader.doc,
            search_text="ABC-123",
            new_text="XYZ-789"
        )
        
        assert replacements > 0, "No replacements made"
        
        # Save and verify
        reader.doc.save(output_path)
        reader.close()
        
        reader2 = PDFReader(output_path)
        assert reader2.open(), "Failed to open edited PDF"
        
        # Check each page has the new text
        for page_num in range(1, 6):
            text = reader2.get_page_text(page_num)
            assert "XYZ-789" in text, f"Page {page_num} missing new text"
        
        reader2.close()
        print(f"  [OK] Multi-page test passed ({replacements} replacements)")


def run_all_tests():
    """Run all tests."""
    print("=" * 50)
    print("PDF Footer Editor - Test Suite")
    print("=" * 50)
    print()
    
    tests = [
        test_pdf_reader,
        test_text_detector,
        test_footer_detector,
        test_text_replacer,
        test_renderer,
        test_exporter,
        test_multi_page_pdf,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__} failed: {e}")
            failed += 1
    
    print()
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
