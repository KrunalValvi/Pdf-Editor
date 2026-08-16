"""
Text Replacer Module — Span-aware text replacement preserving original formatting.

Architecture:
  find_span()         → locate the exact span containing target text
  replace_span()      → redact only that span, reinsert with same formatting
  replace_text()      → high-level single-page replacement
  replace_text_on_all_pages() → per-occurrence formatting preservation
"""
try:
    import pymupdf as fitz
except ImportError:
    import fitz
from typing import Optional, List, Tuple, Dict
from ..models.pdf_models import TextBlock


class TextReplacer:
    """Span-aware text replacement engine for PDF pages."""

    # Base-14 font short names
    BASE14 = {
        "helv", "hebo", "heit", "hebi",
        "tiro", "tibo", "tiit", "tibi",
        "cour", "cobo", "coit", "cobi",
    }

    def __init__(self):
        self.undo_stack: list = []
        self.redo_stack: list = []

    # ────────────────────────────────────────────
    # PUBLIC API
    # ────────────────────────────────────────────

    def replace_text(
        self,
        doc: fitz.Document,
        page_number: int,
        original_block: TextBlock,
        new_text: str,
        preserve_position: bool = True,
    ) -> bool:
        """
        Replace text in a single PDF page.

        The replacement is scoped to the *exact span* identified by
        original_block.bbox.  Surrounding spans are never touched.
        """
        try:
            self._save_undo_state(doc, page_number)
            page = doc[page_number - 1]
            target_rect = fitz.Rect(original_block.bbox)

            # ── Find the exact span in the PDF's internal structure ──
            span_info = self._find_span(page, original_block)
            if span_info is None:
                # Fallback: use the block bbox directly
                span_info = {
                    "text": original_block.text,
                    "font": original_block.font_name,
                    "size": original_block.font_size,
                    "flags": 0,
                    "color": self._color_to_int(original_block.color),
                    "bbox": list(original_block.bbox),
                    "origin": (original_block.bbox[0], original_block.bbox[3] - 2),
                }

            # ── Step 1: Redact ONLY the target span ──
            self._redact_span(page, span_info)

            # ── Step 2: Insert replacement with original formatting ──
            self._insert_span(page, span_info, new_text)

            return True

        except Exception as e:
            print(f"Error replacing text: {e}")
            return False

    def replace_text_on_all_pages(
        self,
        doc: fitz.Document,
        search_text: str,
        new_text: str,
        case_sensitive: bool = False,
    ) -> int:
        """
        Replace every occurrence of *search_text* across all pages.

        Each occurrence preserves its OWN formatting — the formatting of
        one occurrence is never applied to another.
        """
        replacements = 0

        for page_num in range(1, len(doc) + 1):
            page = doc[page_num - 1]
            hits = self._find_all_occurrences(page, search_text, case_sensitive)

            # Process in reverse order so earlier bboxes stay valid
            for span_info in reversed(hits):
                self._save_undo_state(doc, page_num)
                self._redact_span(page, span_info)
                self._insert_span(page, span_info, new_text)
                replacements += 1

        return replacements

    # ────────────────────────────────────────────
    # SPAN DISCOVERY
    # ────────────────────────────────────────────

    def _find_span(self, page: fitz.Page, block: TextBlock) -> Optional[Dict]:
        """
        Walk the page's block→line→span tree and return the span whose
        bbox most closely matches *block.bbox* and whose text contains
        *block.text*.
        """
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        best = None
        best_score = -1

        for b in text_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text.strip():
                        continue

                    # Must contain the target text
                    if block.text not in span_text and span_text not in block.text:
                        continue

                    # Score by bbox overlap
                    sb = span.get("bbox", [0, 0, 0, 0])
                    overlap = self._bbox_overlap(block.bbox, sb)
                    if overlap > best_score:
                        best_score = overlap
                        best = self._span_dict(span)

        return best

    def _find_all_occurrences(
        self, page: fitz.Page, search_text: str, case_sensitive: bool = False
    ) -> List[Dict]:
        """
        Find every span that contains *search_text*.

        Returns a list of span-info dicts, each with its own formatting.
        """
        results = []
        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        needle = search_text if case_sensitive else search_text.lower()

        for b in text_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if not span_text:
                        continue
                    cmp = span_text if case_sensitive else span_text.lower()
                    if needle in cmp:
                        results.append(self._span_dict(span))

        return results

    @staticmethod
    def _span_dict(span: dict) -> Dict:
        """Normalise a PyMuPDF span dict into our internal format."""
        return {
            "text": span.get("text", ""),
            "font": span.get("font", "helv"),
            "size": span.get("size", 12),
            "flags": span.get("flags", 0),
            "color": span.get("color", 0),
            "bbox": list(span.get("bbox", [0, 0, 0, 0])),
            "origin": tuple(span.get("origin", (0, 0))),
        }

    # ────────────────────────────────────────────
    # REDACTION  (targeted to one span)
    # ────────────────────────────────────────────

    @staticmethod
    def _redact_span(page: fitz.Page, span_info: Dict):
        """
        Add a redaction annotation over *only* the span's bbox and
        apply it.  This removes the original glyphs without touching
        neighbouring text.
        """
        bbox = span_info["bbox"]
        # Tiny vertical padding ensures we catch descenders/ascenders
        rect = fitz.Rect(
            bbox[0] - 0.5,
            bbox[1] - 0.5,
            bbox[2] + 0.5,
            bbox[3] + 0.5,
        )
        page.add_redact_annot(rect)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    # ────────────────────────────────────────────
    # TEXT INSERTION  (reuses span formatting)
    # ────────────────────────────────────────────

    def _insert_span(self, page: fitz.Page, span_info: Dict, new_text: str):
        """
        Insert *new_text* at the span's original origin point, using the
        span's own font, size, and colour.
        """
        font_name = span_info["font"]
        font_size = span_info["size"]
        color_int = span_info["color"]
        origin = span_info["origin"]
        flags = span_info.get("flags", 0)

        rgb = self._int_to_rgb(color_int)
        mapped = self._map_font(font_name, flags)

        # Use insert_text (point-based) to match the original baseline
        page.insert_text(
            fitz.Point(origin[0], origin[1]),
            new_text,
            fontsize=font_size,
            fontname=mapped,
            color=rgb,
        )

    # ────────────────────────────────────────────
    # FONT MAPPING
    # ────────────────────────────────────────────

    def _map_font(self, font_name: str, flags: int = 0) -> str:
        """
        Map an arbitrary PDF font name to the closest base-14 short name.
        The *flags* bitmask is used as a fallback when the name is
        ambiguous.
        """
        if not font_name:
            return self._flags_to_font(flags)

        name = font_name.lower().replace(" ", "").replace("-", "")

        # Courier family
        if "courier" in name or "consol" in name or "mono" in name:
            if "bold" in name and ("italic" in name or "oblique" in name):
                return "cobi"
            if "bold" in name:
                return "cobo"
            if "italic" in name or "oblique" in name:
                return "coit"
            return "cour"

        # Times family
        if "times" in name or "tiro" in name or "serif" in name:
            if "bold" in name and ("italic" in name or "oblique" in name):
                return "tibi"
            if "bold" in name:
                return "tibo"
            if "italic" in name or "oblique" in name:
                return "tiit"
            return "tiro"

        # Helvetica family (default)
        if "bold" in name and ("italic" in name or "oblique" in name):
            return "hebi"
        if "bold" in name:
            return "hebo"
        if "italic" in name or "oblique" in name:
            return "heit"

        return self._flags_to_font(flags)

    def _flags_to_font(self, flags: int) -> str:
        """Resolve font from flags bitmask when name mapping fails."""
        is_bold = "bold" in ""  # handled by name
        # flags: bit 1 = superscript, bit 2 = italic, bit 4 = serifed, bit 8 = monospaced
        is_mono = bool(flags & (1 << 3))
        if is_mono:
            return "cour"
        return "helv"

    # ────────────────────────────────────────────
    # HELPERS
    # ────────────────────────────────────────────

    @staticmethod
    def _color_to_int(rgb: tuple) -> int:
        """Convert (r,g,b) float tuple → 24-bit int."""
        r = int(rgb[0] * 255) if rgb[0] <= 1 else int(rgb[0])
        g = int(rgb[1] * 255) if rgb[1] <= 1 else int(rgb[1])
        b = int(rgb[2] * 255) if rgb[2] <= 1 else int(rgb[2])
        return (r << 16) | (g << 8) | b

    @staticmethod
    def _int_to_rgb(color_int: int) -> tuple:
        """Convert 24-bit int → (r,g,b) float tuple."""
        r = ((color_int >> 16) & 0xFF) / 255.0
        g = ((color_int >> 8) & 0xFF) / 255.0
        b = (color_int & 0xFF) / 255.0
        return (r, g, b)

    @staticmethod
    def _bbox_overlap(a: list, b: list) -> float:
        """Return the area of intersection of two bboxes (or 0)."""
        x0 = max(a[0], b[0])
        y0 = max(a[1], b[1])
        x1 = min(a[2], b[2])
        y1 = min(a[3], b[3])
        if x1 > x0 and y1 > y0:
            return (x1 - x0) * (y1 - y0)
        return 0.0

    # ────────────────────────────────────────────
    # UNDO / REDO
    # ────────────────────────────────────────────

    def _save_undo_state(self, doc: fitz.Document, page_number: int):
        page = doc[page_number - 1]
        self.undo_stack.append({
            "page_number": page_number,
            "xref": page.xref,  # lightweight reference
        })
        self.redo_stack.clear()

    def undo(self, doc: fitz.Document) -> bool:
        if not self.undo_stack:
            return False
        state = self.undo_stack.pop()
        self.redo_stack.append(state)
        return True

    def redo(self, doc: fitz.Document) -> bool:
        if not self.redo_stack:
            return False
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        return True
