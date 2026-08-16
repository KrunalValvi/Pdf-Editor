"""
Text Detector Module - Detects and analyzes text blocks in PDFs.
"""
from typing import List, Tuple
from ..models.pdf_models import TextBlock


class TextDetector:
    """Detects and analyzes text blocks in PDF pages."""
    
    @staticmethod
    def find_text_near_position(
        text_blocks: List[TextBlock],
        x: float,
        y: float,
        tolerance: float = 10.0
    ) -> TextBlock | None:
        """Find the closest text block to a given position."""
        closest_block = None
        min_distance = float('inf')
        
        for block in text_blocks:
            bbox = block.bbox
            # Calculate distance from point to bounding box
            dx = max(bbox[0] - x, 0, x - bbox[2])
            dy = max(bbox[1] - y, 0, y - bbox[3])
            distance = (dx ** 2 + dy ** 2) ** 0.5
            
            if distance < min_distance and distance <= tolerance:
                min_distance = distance
                closest_block = block
        
        return closest_block
    
    @staticmethod
    def find_text_by_content(
        text_blocks: List[TextBlock],
        search_text: str,
        case_sensitive: bool = False
    ) -> List[TextBlock]:
        """Find text blocks containing specific content."""
        results = []
        
        for block in text_blocks:
            text = block.text
            if not case_sensitive:
                text = text.lower()
                search = search_text.lower()
            else:
                search = search_text
            
            if search in text:
                results.append(block)
        
        return results
    
    @staticmethod
    def get_text_alignment(text_block: TextBlock) -> str:
        """Determine text alignment based on position."""
        bbox = text_block.bbox
        
        # Simple heuristic based on x position relative to page width
        # This is a basic implementation
        x_center = (bbox[0] + bbox[2]) / 2
        
        # Without page width, we'll use relative positioning
        # This should be enhanced with page width information
        return "left"  # Default
    
    @staticmethod
    def calculate_text_width(text: str, font_size: float) -> float:
        """Estimate text width based on font size and character count."""
        # Average character width is approximately 0.6 * font_size
        avg_char_width = font_size * 0.6
        return len(text) * avg_char_width
    
    @staticmethod
    def can_fit_text(
        text: str,
        original_block: TextBlock,
        max_width_ratio: float = 1.2
    ) -> Tuple[bool, float]:
        """Check if replacement text can fit in the original bounding box."""
        original_width = original_block.bbox[2] - original_block.bbox[0]
        new_width = TextDetector.calculate_text_width(text, original_block.font_size)
        
        if new_width <= original_width * max_width_ratio:
            return True, original_block.font_size
        
        # Try to reduce font size
        if new_width > 0:
            required_size = original_block.font_size * (original_width / new_width)
            if required_size >= 6:  # Minimum readable size
                return True, required_size
        
        return False, original_block.font_size
    
    @staticmethod
    def merge_text_blocks(blocks: List[TextBlock]) -> TextBlock | None:
        """Merge multiple text blocks into a single block."""
        if not blocks:
            return None
        
        # Sort by position (top to bottom, left to right)
        sorted_blocks = sorted(blocks, key=lambda b: (b.bbox[1], b.bbox[0]))
        
        # Calculate merged bounding box
        min_x = min(b.bbox[0] for b in sorted_blocks)
        min_y = min(b.bbox[1] for b in sorted_blocks)
        max_x = max(b.bbox[2] for b in sorted_blocks)
        max_y = max(b.bbox[3] for b in sorted_blocks)
        
        # Merge text
        merged_text = " ".join(b.text for b in sorted_blocks)
        
        # Use properties from first block
        first = sorted_blocks[0]
        
        return TextBlock(
            text=merged_text,
            bbox=[min_x, min_y, max_x, max_y],
            font_name=first.font_name,
            font_size=first.font_size,
            color=first.color,
            page_number=first.page_number
        )
