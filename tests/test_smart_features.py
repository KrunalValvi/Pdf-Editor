"""
Test new features: Smart Footer Detection, Page Numbers, Image Insert.
"""
try:
    import pymupdf as fitz
except ImportError:
    import fitz
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend.app.pdf.smart_features import SmartFooterManager, PageNumberManager, ImageManager

TEST_PDF = os.path.join(os.path.dirname(__file__), "test_mixed_format.pdf")
PASS = 0
FAIL = 0


def check(condition, label):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [OK] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def test_smart_footer_detection():
    """Test Smart Footer Detection on the test PDF."""
    print("\nTest: Smart Footer Detection")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)

    doc = fitz.open(dst)
    mgr = SmartFooterManager()

    # Detect on page 1
    elements = mgr.detect_footers_on_page(doc, 1)
    check(len(elements) > 0, f"Detected {len(elements)} footer element(s) on page 1")

    # The footer "Page 1 | Company Name" should be detected
    footer_texts = [e.text.strip() for e in elements]
    check("Page 1 | Company Name" in footer_texts, "Footer 'Page 1 | Company Name' detected")

    # Detect across pages
    grouped = mgr.detect_footers_across_pages(doc)
    check(len(grouped) > 0, f"Grouped {len(grouped)} footer element group(s) across pages")

    # The student ID should be detected (it's in the bottom 15%)
    all_texts = [g["text"].strip() for g in grouped]
    has_student_id = any("92510103004" in t for t in all_texts)
    check(has_student_id, "Student ID detected as footer element")

    # The page numbers should be detected
    has_page_num = any("19" in t and len(t.strip()) <= 3 for t in all_texts)
    check(has_page_num, "Page number '19' detected")

    doc.close()
    shutil.rmtree(tmpdir)


def test_smart_footer_replace():
    """Test Smart Footer Replace."""
    print("\nTest: Smart Footer Replace")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)

    doc = fitz.open(dst)
    mgr = SmartFooterManager()

    grouped = mgr.detect_footers_across_pages(doc)
    check(len(grouped) > 0, f"Detected {len(grouped)} footer groups")

    # Find the student ID element
    student_id_el = None
    for g in grouped:
        if "92510103004" in g["text"]:
            student_id_el = g
            break
    check(student_id_el is not None, "Found student ID element")

    if student_id_el:
        count = mgr.replace_footer_element(doc, student_id_el, "92510103032")
        check(count > 0, f"Replaced {count} student ID instances")

        # Verify replacement on page 1
        page1 = doc[0]
        text = page1.get_text("text")
        check("92510103032" in text, "Replacement visible in page 1 text")
        check("92510103004" not in text, "Original student ID removed from page 1")

        # Verify page 2 was also replaced (if it was in the element's pages)
        page2 = doc[1]
        text2 = page2.get_text("text")
        if student_id_el.get("page_count", 0) > 1:
            check("92510103032" in text2, "Replacement also applied to page 2")

    doc.close()
    shutil.rmtree(tmpdir)


def test_page_number_detection():
    """Test Page Number Detection."""
    print("\nTest: Page Number Detection")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)

    doc = fitz.open(dst)
    mgr = PageNumberManager()

    existing = mgr.detect_existing_page_numbers(doc)
    check(len(existing) > 0, f"Detected {len(existing)} existing page number(s)")

    # Should detect "19" on page 1 and "20" on page 2
    page_nums = {e["page_number"]: e["text"] for e in existing}
    check(1 in page_nums, "Page 1 has a page number")
    check(2 in page_nums, "Page 2 has a page number")

    doc.close()
    shutil.rmtree(tmpdir)


def test_page_number_add():
    """Test Page Number Addition."""
    print("\nTest: Page Number Addition")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)

    doc = fitz.open(dst)
    mgr = PageNumberManager()

    count = mgr.add_page_numbers(
        doc, format_str="Page {page} of {pages}",
        position="bottom-center", start_at=1,
    )
    check(count == 2, f"Added page numbers to {count} pages")

    # Check page 1
    page1_text = doc[0].get_text("text")
    check("Page 1 of 2" in page1_text, "Page 1 has 'Page 1 of 2'")

    # Check page 2
    page2_text = doc[1].get_text("text")
    check("Page 2 of 2" in page2_text, "Page 2 has 'Page 2 of 2'")

    doc.close()
    shutil.rmtree(tmpdir)


def test_page_number_skip():
    """Test Page Number with Skip Pages."""
    print("\nTest: Page Number Skip Pages")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)

    doc = fitz.open(dst)
    mgr = PageNumberManager()

    count = mgr.add_page_numbers(
        doc, format_str="{page}",
        position="bottom-right", start_at=1, skip_pages=[1],
    )
    check(count == 1, f"Added page numbers to {count} pages (skipped page 1)")

    # Page 1 should NOT have the new number at bottom right
    # Page 2 should have "2" at bottom right
    page2_text = doc[1].get_text("text")
    check("2" in page2_text, "Page 2 has number '2'")

    doc.close()
    shutil.rmtree(tmpdir)


def test_footer_template():
    """Test Footer Template."""
    print("\nTest: Footer Template")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)

    doc = fitz.open(dst)
    mgr = SmartFooterManager()

    template = {
        "left": "Student ID",
        "right": "Page {page} of {pages}",
    }
    custom_vars = {"student_id": "92510103032"}

    count = mgr.apply_footer_template(doc, template, custom_vars)
    check(count > 0, f"Applied template to {count} locations")

    # Check page 1
    page1_text = doc[0].get_text("text")
    check("Student ID" in page1_text, "Template 'left' text present on page 1")
    check("Page 1 of 2" in page1_text, "Template 'right' with variable resolved on page 1")

    # Check page 2
    page2_text = doc[1].get_text("text")
    check("Page 2 of 2" in page2_text, "Template 'right' resolved correctly for page 2")

    doc.close()
    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    print("=" * 60)
    print("SMART FOOTER / PAGE NUMBER / IMAGE TESTS")
    print("=" * 60)

    test_smart_footer_detection()
    test_smart_footer_replace()
    test_page_number_detection()
    test_page_number_add()
    test_page_number_skip()
    test_footer_template()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    sys.exit(1 if FAIL > 0 else 0)
