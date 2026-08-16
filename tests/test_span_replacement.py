"""
Span-aware text replacement tests.

Tests that editing one span preserves the formatting of all surrounding spans.
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
from backend.app.pdf.reader import PDFReader
from backend.app.pdf.text_replacer import TextReplacer
from backend.app.pdf.renderer import PDFRenderer
from backend.app.models.pdf_models import TextBlock

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


def get_spans(doc, page_num):
    """Extract all spans from a page with formatting info."""
    page = doc[page_num - 1]
    result = []
    td = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
    for b in td.get("blocks", []):
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if text.strip():
                    result.append({
                        "text": text,
                        "font": span.get("font", ""),
                        "size": span.get("size", 0),
                        "flags": span.get("flags", 0),
                        "color": span.get("color", 0),
                        "bbox": list(span.get("bbox", [])),
                    })
    return result


def spans_to_str(spans):
    lines = []
    for s in spans:
        flags = s["flags"]
        styles = []
        if flags & (1 << 1): styles.append("ITALIC")
        if "bold" in s["font"].lower(): styles.append("BOLD")
        if flags & (1 << 3): styles.append("MONO")
        if not styles: styles.append("NORMAL")
        lines.append(f"    \"{s['text']}\"  {s['font']}  {s['size']}  {','.join(styles)}")
    return "\n".join(lines)


def make_block(text, bbox, font_name, font_size, color, page_number):
    """Helper to create a TextBlock for the replacer."""
    return TextBlock(
        text=text,
        bbox=bbox,
        font_name=font_name,
        font_size=font_size,
        color=color,
        page_number=page_number,
    )


def test_a_replace_normal_preserves_bold():
    """
    Test A: Replace plt.figure(figsize=(9,5)) — normal courier text.
    Expected: bold 'Code:' and heading remain bold, code stays normal.
    """
    print("\nTest A: Replace normal code line, verify surrounding bold preserved")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    # Get original spans
    orig = get_spans(doc, 1)

    # Find the plt.figure span
    target = None
    for s in orig:
        if "plt.figure" in s["text"]:
            target = s
            break
    check(target is not None, "Found plt.figure span")

    block = make_block(
        target["text"], target["bbox"], target["font"],
        target["size"], reader.doc[0].color if hasattr(reader.doc[0], 'color') else (0.1, 0.1, 0.1),
        1
    )

    # Replace
    ok = replacer.replace_text(doc, 1, block, "plt.figure(figsize=(10,6))")
    check(ok, "Replacement returned True")

    # Get updated spans
    after = get_spans(doc, 1)

    # Check Code: is still bold
    code_span = [s for s in after if s["text"] == "Code:"]
    check(len(code_span) == 1, "Code: span still exists")
    if code_span:
        check("bold" in code_span[0]["font"].lower(), f"Code: still bold ({code_span[0]['font']})")

    # Check heading is still bold
    heading_span = [s for s in after if "Creating" in s["text"]]
    check(len(heading_span) == 1, "Heading span still exists")
    if heading_span:
        check("bold" in heading_span[0]["font"].lower(), f"Heading still bold ({heading_span[0]['font']})")

    # Check plt.figure was replaced
    fig_span = [s for s in after if "plt.figure" in s["text"]]
    check(len(fig_span) == 1, "plt.figure span still exists after replace")
    if fig_span:
        check("10,6" in fig_span[0]["text"], f"Text updated: \"{fig_span[0]['text']}\"")

    # Check plt.plot is untouched
    plot_span = [s for s in after if "plt.plot" in s["text"]]
    check(len(plot_span) == 1, "plt.plot span untouched")

    # Check normal text untouched
    normal_span = [s for s in after if "normal text" in s["text"]]
    check(len(normal_span) == 1, "Normal text span untouched")
    if normal_span:
        check(normal_span[0]["font"] == "Helvetica", f"Normal text still Helvetica ({normal_span[0]['font']})")

    # Check italic text untouched
    italic_span = [s for s in after if "italic text" in s["text"]]
    check(len(italic_span) == 1, "Italic text span untouched")
    if italic_span:
        check("Oblique" in italic_span[0]["font"] or "Italic" in italic_span[0]["font"],
              f"Italic text still italic ({italic_span[0]['font']})")

    # Check bold text untouched
    bold_span = [s for s in after if "bold text" in s["text"]]
    check(len(bold_span) == 1, "Bold text span untouched")
    if bold_span:
        check("bold" in bold_span[0]["font"].lower(), f"Bold text still bold ({bold_span[0]['font']})")

    # Verify total span count unchanged
    check(len(after) == len(orig), f"Span count preserved ({len(orig)} -> {len(after)})")

    reader.close()
    shutil.rmtree(tmpdir)


def test_b_replace_bold_preserves_normal():
    """
    Test B: Replace bold heading text.
    Expected: replacement stays bold, surrounding normal text untouched.
    """
    print("\nTest B: Replace bold heading, verify replacement stays bold")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    orig = get_spans(doc, 1)

    # Find the heading span
    target = None
    for s in orig:
        if "Creating" in s["text"]:
            target = s
            break
    check(target is not None, "Found heading span")
    check("bold" in target["font"].lower(), f"Original heading is bold ({target['font']})")

    block = make_block(
        target["text"], target["bbox"], target["font"],
        target["size"], (0, 0, 0), 1
    )

    ok = replacer.replace_text(doc, 1, block, "#Creating a Bar Chart")
    check(ok, "Replacement returned True")

    after = get_spans(doc, 1)

    # Check heading was replaced
    heading = [s for s in after if "Bar Chart" in s["text"]]
    check(len(heading) == 1, "New heading text found")
    if heading:
        check("bold" in heading[0]["font"].lower(),
              f"Replacement is bold ({heading[0]['font']})")
        check(heading[0]["size"] == target["size"],
              f"Font size preserved ({heading[0]['size']} == {target['size']})")

    # Check plt.figure is still Courier (normal code)
    fig_span = [s for s in after if "plt.figure" in s["text"]]
    check(len(fig_span) == 1, "plt.figure untouched")
    if fig_span:
        check("courier" in fig_span[0]["font"].lower(),
              f"plt.figure still Courier ({fig_span[0]['font']})")

    reader.close()
    shutil.rmtree(tmpdir)


def test_c_replace_with_longer_text():
    """
    Test C: Replace normal text with longer text.
    Expected: original formatting preserved, text inserted at same origin.
    """
    print("\nTest C: Replace with longer text")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    orig = get_spans(doc, 1)

    target = None
    for s in orig:
        if "normal text" in s["text"]:
            target = s
            break
    check(target is not None, "Found normal text span")

    block = make_block(
        target["text"], target["bbox"], target["font"],
        target["size"], (0, 0, 0), 1
    )

    long_text = "This is a much longer replacement text that extends beyond the original."
    ok = replacer.replace_text(doc, 1, block, long_text)
    check(ok, "Longer text replacement returned True")

    after = get_spans(doc, 1)

    found = [s for s in after if "much longer" in s["text"]]
    check(len(found) == 1, "Longer replacement text found")
    if found:
        check(found[0]["font"] == "Helvetica", f"Font preserved ({found[0]['font']})")
        check(found[0]["size"] == target["size"], f"Size preserved ({found[0]['size']})")

    reader.close()
    shutil.rmtree(tmpdir)


def test_d_replace_with_shorter_text():
    """
    Test D: Replace with shorter text.
    Expected: formatting preserved, position correct.
    """
    print("\nTest D: Replace with shorter text")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    orig = get_spans(doc, 1)

    target = None
    for s in orig:
        if "plt.plot" in s["text"]:
            target = s
            break
    check(target is not None, "Found plt.plot span")

    block = make_block(
        target["text"], target["bbox"], target["font"],
        target["size"], (0.1, 0.1, 0.1), 1
    )

    ok = replacer.replace_text(doc, 1, block, "plt.show()")
    check(ok, "Shorter text replacement returned True")

    after = get_spans(doc, 1)

    found = [s for s in after if "plt.show" in s["text"]]
    check(len(found) == 1, "Shorter replacement text found")
    if found:
        check("courier" in found[0]["font"].lower(),
              f"Courier font preserved ({found[0]['font']})")
        check(found[0]["size"] == target["size"], f"Size preserved ({found[0]['size']})")

    reader.close()
    shutil.rmtree(tmpdir)


def test_e_replace_all_preserves_per_occurrence_formatting():
    """
    Test E: Replace-all should preserve each occurrence's own formatting.
    Page 1: '92510103004' is Helvetica NORMAL
    Page 2: '92510103004' is Helvetica NORMAL
    Both should stay NORMAL after replacement.
    """
    print("\nTest E: Replace-all preserves per-occurrence formatting")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    # Check original: page 1 student ID
    p1 = get_spans(doc, 1)
    sid_p1 = [s for s in p1 if "92510103004" in s["text"]]
    check(len(sid_p1) == 1, "Page 1 has student ID span")
    if sid_p1:
        check(sid_p1[0]["font"] == "Helvetica",
              f"Page 1 student ID is Helvetica NORMAL ({sid_p1[0]['font']})")

    # Check original: page 2 student ID
    p2 = get_spans(doc, 2)
    sid_p2 = [s for s in p2 if "92510103004" in s["text"]]
    check(len(sid_p2) == 1, "Page 2 has student ID span")
    if sid_p2:
        check(sid_p2[0]["font"] == "Helvetica",
              f"Page 2 student ID is Helvetica NORMAL ({sid_p2[0]['font']})")

    # Replace all
    count = replacer.replace_text_on_all_pages(doc, "92510103004", "92510103032", case_sensitive=True)
    check(count == 2, f"Two replacements made ({count})")

    # Verify page 1
    p1_after = get_spans(doc, 1)
    new_sid_p1 = [s for s in p1_after if "92510103032" in s["text"]]
    check(len(new_sid_p1) == 1, "Page 1: new student ID found")
    if new_sid_p1:
        check(new_sid_p1[0]["font"] == "Helvetica",
              f"Page 1 replacement is Helvetica NORMAL ({new_sid_p1[0]['font']})")

    # Verify page 2
    p2_after = get_spans(doc, 2)
    new_sid_p2 = [s for s in p2_after if "92510103032" in s["text"]]
    check(len(new_sid_p2) == 1, "Page 2: new student ID found")
    if new_sid_p2:
        check(new_sid_p2[0]["font"] == "Helvetica",
              f"Page 2 replacement is Helvetica NORMAL ({new_sid_p2[0]['font']})")

    # Verify surrounding spans on page 1
    bold_p1 = [s for s in p1_after if s["text"] == "Student ID"]
    check(len(bold_p1) == 1, "Page 1: 'Student ID' label untouched")
    if bold_p1:
        check("bold" in bold_p1[0]["font"].lower(),
              f"Page 1: 'Student ID' still bold ({bold_p1[0]['font']})")

    page_num_label = [s for s in p1_after if s["text"] == "Page Number"]
    check(len(page_num_label) == 1, "Page 1: 'Page Number' label untouched")
    if page_num_label:
        check("bold" in page_num_label[0]["font"].lower(),
              f"Page 1: 'Page Number' still bold ({page_num_label[0]['font']})")

    reader.close()
    shutil.rmtree(tmpdir)


def test_f_multi_line_code_block():
    """
    Test F: Replace one code line in a multi-line code block.
    Other code lines must remain Courier/normal.
    """
    print("\nTest F: Multi-line code block — replace one line")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    orig = get_spans(doc, 1)
    code_lines = [s for s in orig if "courier" in s["font"].lower()]
    check(len(code_lines) >= 2, f"Found {len(code_lines)} code spans on page 1")

    # Replace just plt.figure
    target = [s for s in orig if "plt.figure" in s["text"]][0]
    block = make_block(target["text"], target["bbox"], target["font"],
                       target["size"], (0.1, 0.1, 0.1), 1)

    ok = replacer.replace_text(doc, 1, block, "plt.figure(figsize=(12,8))")
    check(ok, "Code line replacement succeeded")

    after = get_spans(doc, 1)
    after_code = [s for s in after if "courier" in s["font"].lower()]

    # Check plt.figure was updated
    fig = [s for s in after if "plt.figure" in s["text"]]
    check(len(fig) == 1, "plt.figure still exists")
    if fig:
        check("12,8" in fig[0]["text"], f"Updated to figsize=(12,8): \"{fig[0]['text']}\"")
        check("courier" in fig[0]["font"].lower(),
              f"Still Courier ({fig[0]['font']})")

    # Check plt.plot is untouched
    plot = [s for s in after if "plt.plot" in s["text"]]
    check(len(plot) == 1, "plt.plot untouched")
    if plot:
        check("courier" in plot[0]["font"].lower(),
              f"plt.plot still Courier ({plot[0]['font']})")

    # Total code span count unchanged
    check(len(after_code) == len(code_lines),
          f"Code span count unchanged ({len(code_lines)} -> {len(after_code)})")

    reader.close()
    shutil.rmtree(tmpdir)


def test_g_case_insensitive_replace_all():
    """
    Test G: Case-insensitive replace-all.
    """
    print("\nTest G: Case-insensitive replace-all")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    count = replacer.replace_text_on_all_pages(
        doc, "This is normal text in Helvetica.",
        "Replaced normal text.",
        case_sensitive=False,
    )
    check(count == 2, f"Two replacements made ({count})")

    for pn in [1, 2]:
        spans = get_spans(doc, pn)
        found = [s for s in spans if "Replaced" in s["text"]]
        check(len(found) == 1, f"Page {pn}: replacement found")

    reader.close()
    shutil.rmtree(tmpdir)


def test_h_footer_line_preserved():
    """
    Test H: Footer text on both pages stays untouched after other edits.
    """
    print("\nTest H: Footer lines untouched after edits")

    tmpdir = tempfile.mkdtemp()
    dst = os.path.join(tmpdir, "test.pdf")
    shutil.copy2(TEST_PDF, dst)
    reader = PDFReader(dst)
    reader.open()
    replacer = TextReplacer()
    doc = reader.doc

    orig_p1 = [s for s in get_spans(doc, 1) if "Company Name" in s["text"]]
    orig_p2 = [s for s in get_spans(doc, 2) if "Company Name" in s["text"]]
    check(len(orig_p1) == 1, "Page 1 has footer")
    check(len(orig_p2) == 1, "Page 2 has footer")

    # Replace something on page 1
    target = [s for s in get_spans(doc, 1) if "bold text" in s["text"]][0]
    block = make_block(target["text"], target["bbox"], target["font"],
                       target["size"], (0, 0, 0), 1)
    replacer.replace_text(doc, 1, block, "extra bold text")

    # Check footers untouched
    after_p1 = [s for s in get_spans(doc, 1) if "Company Name" in s["text"]]
    after_p2 = [s for s in get_spans(doc, 2) if "Company Name" in s["text"]]
    check(len(after_p1) == 1, "Page 1 footer still exists")
    check(len(after_p2) == 1, "Page 2 footer still exists")
    if after_p1:
        check("Company Name" in after_p1[0]["text"],
              f"Page 1 footer text preserved: \"{after_p1[0]['text']}\"")

    reader.close()
    shutil.rmtree(tmpdir)


if __name__ == "__main__":
    print("=" * 60)
    print("SPAN-AWARE TEXT REPLACEMENT TESTS")
    print("=" * 60)

    test_a_replace_normal_preserves_bold()
    test_b_replace_bold_preserves_normal()
    test_c_replace_with_longer_text()
    test_d_replace_with_shorter_text()
    test_e_replace_all_preserves_per_occurrence_formatting()
    test_f_multi_line_code_block()
    test_g_case_insensitive_replace_all()
    test_h_footer_line_preserved()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    sys.exit(1 if FAIL > 0 else 0)
