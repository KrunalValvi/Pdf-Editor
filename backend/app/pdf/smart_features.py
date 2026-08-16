"""
Smart Footer Manager - Detect, edit, template, and apply footers.
"""
try:
    import pymupdf as fitz
except ImportError:
    import fitz
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from ..models.pdf_models import TextBlock


class FooterElement:
    """A single detected footer element with its formatting."""

    def __init__(self, text, bbox, font_name, font_size, color, flags=0, page_number=1, origin=None):
        self.text = text
        self.bbox = list(bbox)
        self.font_name = font_name
        self.font_size = font_size
        self.color = color
        self.flags = flags
        self.page_number = page_number
        self.origin = origin or (bbox[0], bbox[3] - 2)

    def to_dict(self):
        return {
            "text": self.text,
            "bbox": self.bbox,
            "font_name": self.font_name,
            "font_size": self.font_size,
            "color": self.color,
            "flags": self.flags,
            "page_number": self.page_number,
            "origin": list(self.origin),
        }


class SmartFooterManager:
    """Detect, edit, template, and apply footers across pages."""

    def __init__(self, detection_zone_percent=15.0):
        self.detection_zone_percent = detection_zone_percent

    def detect_footers_on_page(self, doc, page_number):
        """Detect footer elements on a single page."""
        page = doc[page_number - 1]
        page_height = page.rect.height
        zone_top = page_height * (1 - self.detection_zone_percent / 100)

        text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        elements = []

        for b in text_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "").strip()
                    if not span_text:
                        continue
                    bbox = span.get("bbox", [0, 0, 0, 0])
                    vcenter = (bbox[1] + bbox[3]) / 2

                    if vcenter >= zone_top:
                        block_height = bbox[3] - bbox[1]
                        if block_height < page_height * 0.1:
                            origin = span.get("origin", (bbox[0], bbox[3] - 2))
                            color = span.get("color", 0)
                            r = ((color >> 16) & 0xFF) / 255.0
                            g = ((color >> 8) & 0xFF) / 255.0
                            b_val = (color & 0xFF) / 255.0

                            elements.append(FooterElement(
                                text=span.get("text", ""),
                                bbox=bbox,
                                font_name=span.get("font", "helv"),
                                font_size=span.get("size", 10),
                                color=(r, g, b_val),
                                flags=span.get("flags", 0),
                                page_number=page_number,
                                origin=origin,
                            ))

        elements.sort(key=lambda e: (e.bbox[1], e.bbox[0]))
        return elements

    def detect_footers_across_pages(self, doc, page_numbers=None):
        """Detect footer elements across multiple pages and group similar ones."""
        if page_numbers is None:
            page_numbers = list(range(1, len(doc) + 1))

        all_elements = []
        for pn in page_numbers:
            if 1 <= pn <= len(doc):
                els = self.detect_footers_on_page(doc, pn)
                all_elements.extend(els)

        grouped = self._group_footer_elements(all_elements)
        return grouped

    def _group_footer_elements(self, elements):
        """Group footer elements that appear across pages at similar positions."""
        if not elements:
            return []

        groups = []

        for el in elements:
            matched = False
            for group in groups:
                ref = group[0]
                y_close = abs(el.bbox[1] - ref.bbox[1]) < 8
                x_close = abs(el.bbox[0] - ref.bbox[0]) < 30
                font_match = el.font_name == ref.font_name
                size_match = abs(el.font_size - ref.font_size) < 1

                if y_close and x_close and font_match and size_match:
                    group.append(el)
                    matched = True
                    break

            if not matched:
                groups.append([el])

        result = []
        for i, group in enumerate(groups):
            ref = group[0]
            pages = sorted(set(e.page_number for e in group))
            result.append({
                "element_id": i,
                "text": ref.text,
                "font_name": ref.font_name,
                "font_size": ref.font_size,
                "color": ref.color,
                "flags": ref.flags,
                "bbox": ref.bbox,
                "origin": list(ref.origin),
                "page_count": len(pages),
                "pages": pages,
                "sample_count": len(group),
            })

        result.sort(key=lambda r: (r["bbox"][1], r["bbox"][0]))
        return result

    def replace_footer_element(self, doc, element_info, new_text, pages=None):
        """Replace a specific footer element across specified pages."""
        if pages is None:
            pages = element_info.get("pages", [])

        replacements = 0
        bbox = element_info["bbox"]

        for pn in pages:
            if pn < 1 or pn > len(doc):
                continue
            page = doc[pn - 1]

            rect = fitz.Rect(bbox[0] - 0.5, bbox[1] - 0.5, bbox[2] + 0.5, bbox[3] + 0.5)
            page.add_redact_annot(rect)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            origin = tuple(element_info.get("origin", (bbox[0], bbox[3] - 2)))
            color = element_info.get("color", (0, 0, 0))
            font_name = element_info.get("font_name", "helv")
            font_size = element_info.get("font_size", 10)

            from .text_replacer import TextReplacer
            replacer = TextReplacer()
            mapped = replacer._map_font(font_name, element_info.get("flags", 0))

            page.insert_text(
                fitz.Point(origin[0], origin[1]),
                new_text,
                fontsize=font_size,
                fontname=mapped,
                color=color,
            )
            replacements += 1

        return replacements

    def apply_footer_template(self, doc, template, custom_vars=None, pages=None):
        """Apply a footer template to pages.

        template: dict with keys 'left', 'center', 'right' (each optional string)
        custom_vars: dict of variable_name -> value
        pages: list of page numbers, or None for all
        """
        if pages is None:
            pages = list(range(1, len(doc) + 1))

        total_pages = len(doc)
        now = datetime.now()
        default_vars = {
            "page": None,
            "pages": str(total_pages),
            "filename": "",
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M"),
        }
        if custom_vars:
            default_vars.update(custom_vars)

        replacements = 0

        for pn in pages:
            if pn < 1 or pn > len(doc):
                continue
            page = doc[pn - 1]
            page_height = page.rect.height
            page_width = page.rect.width

            variables = dict(default_vars)
            variables["page"] = str(pn)

            margin_bottom = 40
            y_bottom = page_height - margin_bottom
            y_center = page_height - margin_bottom + 10
            y_top = page_height - margin_bottom + 20

            for position, text_template in template.items():
                if not text_template:
                    continue

                resolved = self._resolve_variables(text_template, variables)

                if position == "left":
                    x = 72
                    align = fitz.TEXT_ALIGN_LEFT
                    y = y_bottom
                elif position == "center":
                    x = page_width / 2
                    align = fitz.TEXT_ALIGN_CENTER
                    y = y_bottom
                elif position == "right":
                    x = page_width - 72
                    align = fitz.TEXT_ALIGN_RIGHT
                    y = y_bottom
                else:
                    continue

                rect_right = min(x + 200, page_width - 10)
                rect = fitz.Rect(x - 5, y - 12, rect_right, y + 4)
                page.insert_textbox(
                    rect,
                    resolved,
                    fontsize=10,
                    fontname="helv",
                    color=(0, 0, 0),
                    align=align,
                )
                replacements += 1

        return replacements

    def _resolve_variables(self, text, variables):
        """Replace {variable} placeholders in text."""
        def replacer(match):
            key = match.group(1).lower()
            return variables.get(key, match.group(0))
        return re.sub(r'\{(\w+)\}', replacer, text)


class PageNumberManager:
    """Add, replace, or modify page numbering."""

    POSITION_MAP = {
        "top-left": ("left", "top"),
        "top-center": ("center", "top"),
        "top-right": ("right", "top"),
        "bottom-left": ("left", "bottom"),
        "bottom-center": ("center", "bottom"),
        "bottom-right": ("right", "bottom"),
    }

    def __init__(self):
        pass

    def detect_existing_page_numbers(self, doc):
        """Scan all pages for text that looks like page numbers."""
        results = []

        for page_num in range(1, len(doc) + 1):
            page = doc[page_num - 1]
            page_height = page.rect.height
            page_width = page.rect.width

            text_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

            for b in text_dict.get("blocks", []):
                if b.get("type") != 0:
                    continue
                for line in b.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        if not text:
                            continue
                        bbox = span.get("bbox", [0, 0, 0, 0])
                        vcenter = (bbox[1] + bbox[3]) / 2

                        is_top = vcenter < page_height * 0.08
                        is_bottom = vcenter > page_height * 0.92
                        is_number = bool(re.match(r'^\d{1,4}$', text))
                        is_page_text = bool(re.match(r'^(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?$', text, re.IGNORECASE))

                        if (is_top or is_bottom) and (is_number or is_page_text):
                            color = span.get("color", 0)
                            r = ((color >> 16) & 0xFF) / 255.0
                            g = ((color >> 8) & 0xFF) / 255.0
                            b_val = (color & 0xFF) / 255.0

                            position = "top" if is_top else "bottom"
                            halign = "left" if bbox[0] < page_width * 0.33 else (
                                "right" if bbox[0] > page_width * 0.66 else "center"
                            )

                            results.append({
                                "page_number": page_num,
                                "text": span.get("text", ""),
                                "bbox": list(bbox),
                                "font_name": span.get("font", "helv"),
                                "font_size": span.get("size", 10),
                                "color": (r, g, b_val),
                                "flags": span.get("flags", 0),
                                "origin": list(span.get("origin", (bbox[0], bbox[3] - 2))),
                                "position": f"{position}-{halign}",
                                "is_number": is_number,
                            })

        return results

    def add_page_numbers(self, doc, format_str="Page {page} of {pages}",
                         position="bottom-center", start_at=1, skip_pages=None,
                         font_name="helv", font_size=10, font_color=(0, 0, 0),
                         bold=False, italic=False, pages=None):
        """Add page numbers to the PDF."""
        if skip_pages is None:
            skip_pages = []
        if pages is None:
            pages = list(range(1, len(doc) + 1))

        total_pages = len(doc)
        count = 0

        for pn in pages:
            if pn < 1 or pn > len(doc) or pn in skip_pages:
                continue

            page = doc[pn - 1]
            page_height = page.rect.height
            page_width = page.rect.width

            display_num = start_at + pn - 1
            resolved = format_str
            resolved = resolved.replace("{page}", str(display_num))
            resolved = resolved.replace("{pages}", str(total_pages))

            pos_key = position if position in self.POSITION_MAP else "bottom-center"
            halign, valign = self.POSITION_MAP[pos_key]

            margin = 40
            if valign == "top":
                y = margin
            else:
                y = page_height - margin

            if halign == "left":
                x = 72
                align = fitz.TEXT_ALIGN_LEFT
            elif halign == "right":
                x = page_width - 72
                align = fitz.TEXT_ALIGN_RIGHT
            else:
                x = page_width / 2
                align = fitz.TEXT_ALIGN_CENTER

            mapped = self._map_font_name(font_name, bold, italic)

            rect = fitz.Rect(x - 100 if halign == "right" else x - 5,
                             y - 12,
                             x + 100 if halign == "right" else x + 200,
                             y + 4)

            page.insert_textbox(
                rect,
                resolved,
                fontsize=font_size,
                fontname=mapped,
                color=font_color,
                align=align,
            )
            count += 1

        return count

    def replace_existing_page_numbers(self, doc, format_str="Page {page} of {pages}",
                                      start_at=1, skip_pages=None,
                                      font_name=None, font_size=None, font_color=None,
                                      pages=None):
        """Replace detected page numbers with new format."""
        existing = self.detect_existing_page_numbers(doc)
        if not existing:
            return 0

        if pages is None:
            pages = list(range(1, len(doc) + 1))
        if skip_pages is None:
            skip_pages = []

        total_pages = len(doc)
        count = 0

        for entry in existing:
            pn = entry["page_number"]
            if pn not in pages or pn in skip_pages:
                continue

            page = doc[pn - 1]
            bbox = entry["bbox"]

            rect = fitz.Rect(bbox[0] - 0.5, bbox[1] - 0.5, bbox[2] + 0.5, bbox[3] + 0.5)
            page.add_redact_annot(rect)
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

            display_num = start_at + pn - 1
            resolved = format_str
            resolved = resolved.replace("{page}", str(display_num))
            resolved = resolved.replace("{pages}", str(total_pages))

            use_font = font_name or entry["font_name"]
            use_size = font_size or entry["font_size"]
            use_color = font_color or entry["color"]
            use_bold = "bold" in (use_font or "").lower()

            origin = tuple(entry.get("origin", (bbox[0], bbox[3] - 2)))

            from .text_replacer import TextReplacer
            replacer = TextReplacer()
            mapped = replacer._map_font(use_font, entry.get("flags", 0))

            page.insert_text(
                fitz.Point(origin[0], origin[1]),
                resolved,
                fontsize=use_size,
                fontname=mapped,
                color=use_color,
            )
            count += 1

        return count

    def _map_font_name(self, font_name, bold=False, italic=False):
        if not font_name:
            font_name = "helv"

        name = font_name.lower().replace(" ", "").replace("-", "")

        if "courier" in name or "mono" in name:
            if bold and italic: return "cobi"
            if bold: return "cobo"
            if italic: return "coit"
            return "cour"
        if "times" in name or "serif" in name:
            if bold and italic: return "tibi"
            if bold: return "tibo"
            if italic: return "tiit"
            return "tiro"

        if bold and italic: return "hebi"
        if bold: return "hebo"
        if italic: return "heit"
        return "helv"


class ImageManager:
    """Insert, move, resize, and delete images on PDF pages."""

    def __init__(self):
        self.inserted_images = []

    def insert_image(self, doc, page_number, image_path, x, y, width=None, height=None,
                     opacity=1.0):
        """Insert an image at the specified position on a page."""
        if page_number < 1 or page_number > len(doc):
            raise ValueError(f"Invalid page number: {page_number}")

        page = doc[page_number - 1]

        img_doc = fitz.open(image_path)
        img_page = img_doc[0]
        img_rect = img_page.rect

        if width and height:
            pass
        elif width:
            ratio = width / img_rect.width
            height = img_rect.height * ratio
        elif height:
            ratio = height / img_rect.height
            width = img_rect.width * ratio
        else:
            width = img_rect.width
            height = img_rect.height

        rect = fitz.Rect(x, y, x + width, y + height)

        page.insert_image(rect, filename=image_path, overlay=True)

        img_info = {
            "page_number": page_number,
            "x": x,
            "y": y,
            "width": width,
            "height": height,
            "original_width": img_rect.width,
            "original_height": img_rect.height,
            "image_path": image_path,
            "opacity": opacity,
        }
        self.inserted_images.append(img_info)

        img_doc.close()
        return img_info

    def insert_image_all_pages(self, doc, image_path, x, y, width=None, height=None,
                               opacity=1.0):
        """Insert the same image on all pages."""
        results = []
        for pn in range(1, len(doc) + 1):
            info = self.insert_image(doc, pn, image_path, x, y, width, height, opacity)
            results.append(info)
        return results

    def get_image_info(self, image_path):
        """Get image dimensions without inserting."""
        img_doc = fitz.open(image_path)
        img_page = img_doc[0]
        rect = img_page.rect
        info = {"width": rect.width, "height": rect.height}
        img_doc.close()
        return info
