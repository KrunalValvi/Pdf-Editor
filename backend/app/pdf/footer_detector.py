"""
Footer Detector Module - Detects footer text in PDF pages.
"""
from typing import List, Tuple
from ..models.pdf_models import TextBlock


class FooterDetector:
    """Detects footer text blocks in PDF pages."""
    
    def __init__(self, detection_zone_percent: float = 15.0):
        """
        Initialize footer detector.
        
        Args:
            detection_zone_percent: Percentage of page height to consider as footer zone
        """
        self.detection_zone_percent = detection_zone_percent
    
    def detect_footers(
        self,
        text_blocks: List[TextBlock],
        page_height: float
    ) -> List[TextBlock]:
        """
        Detect footer text blocks on a page.
        
        Args:
            text_blocks: All text blocks on the page
            page_height: Height of the page in points
            
        Returns:
            List of text blocks that appear to be footers
        """
        footer_zone_top = page_height * (1 - self.detection_zone_percent / 100)
        
        footer_candidates = []
        
        for block in text_blocks:
            bbox = block.bbox
            # Block is in footer zone if its vertical center is in the zone
            vertical_center = (bbox[1] + bbox[3]) / 2
            
            if vertical_center >= footer_zone_top:
                # Additional heuristics for footer detection
                block_height = bbox[3] - bbox[1]
                block_width = bbox[2] - bbox[0]
                
                # Footer should not be too tall (likely not a paragraph)
                if block_height < page_height * 0.1:
                    # Footer should have some width (not a single character)
                    if block_width > 10:
                        footer_candidates.append(block)
        
        # Sort by vertical position (bottom-most first)
        footer_candidates.sort(key=lambda b: -b.bbox[1])
        
        return footer_candidates
    
    def find_footer_by_content(
        self,
        text_blocks: List[TextBlock],
        page_height: float,
        search_text: str,
        case_sensitive: bool = False
    ) -> List[TextBlock]:
        """Find footer blocks containing specific text."""
        all_footers = self.detect_footers(text_blocks, page_height)
        
        results = []
        for footer in all_footers:
            text = footer.text
            if not case_sensitive:
                text = text.lower()
                search = search_text.lower()
            else:
                search = search_text
            
            if search in text:
                results.append(footer)
        
        return results
    
    def get_footer_zone(self, page_height: float) -> Tuple[float, float]:
        """Get the y-coordinates of the footer detection zone."""
        zone_top = page_height * (1 - self.detection_zone_percent / 100)
        return zone_top, page_height
    
    def set_detection_zone(self, percent: float):
        """Update the footer detection zone percentage."""
        self.detection_zone_percent = max(1.0, min(50.0, percent))
