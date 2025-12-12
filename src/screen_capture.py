import cv2
import numpy as np
import pyautogui
from pathlib import Path
from typing import Optional, Tuple, List
from PIL import Image

class ScreenCapture:
    def __init__(self, confidence_threshold: float = 0.8):
        self.confidence = confidence_threshold
        self.templates = {}

    def load_template(self, name: str, path: str) -> bool:
        """Load a template image for matching."""
        template_path = Path(path)
        if not template_path.exists():
            print(f"Warning: Template not found: {path}")
            return False

        template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
        if template is None:
            print(f"Warning: Could not load template: {path}")
            return False

        self.templates[name] = template
        return True

    def capture_screen(self, region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """Capture the screen or a specific region.

        Args:
            region: Optional (x, y, width, height) tuple

        Returns:
            Screenshot as numpy array in BGR format
        """
        screenshot = pyautogui.screenshot(region=region)
        frame = np.array(screenshot)
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    def find_template(self, screen: np.ndarray, template_name: str) -> Optional[Tuple[int, int, float]]:
        """Find a template in the screen capture.

        Returns:
            Tuple of (x, y, confidence) for center of match, or None if not found
        """
        if template_name not in self.templates:
            return None

        template = self.templates[template_name]
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= self.confidence:
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)

        return None

    def find_all_matches(self, screen: np.ndarray, template_name: str) -> List[Tuple[int, int, float]]:
        """Find all instances of a template in the screen capture.

        Returns:
            List of (x, y, confidence) tuples for each match
        """
        if template_name not in self.templates:
            return []

        template = self.templates[template_name]
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= self.confidence)

        matches = []
        h, w = template.shape[:2]

        for pt in zip(*locations[::-1]):
            center_x = pt[0] + w // 2
            center_y = pt[1] + h // 2
            conf = result[pt[1], pt[0]]
            matches.append((center_x, center_y, conf))

        # Remove duplicate/overlapping matches
        return self._remove_duplicates(matches, min_distance=20)

    def _remove_duplicates(self, matches: List[Tuple[int, int, float]], min_distance: int = 20) -> List[Tuple[int, int, float]]:
        """Remove duplicate matches that are too close together."""
        if not matches:
            return []

        # Sort by confidence (highest first)
        sorted_matches = sorted(matches, key=lambda x: x[2], reverse=True)
        filtered = []

        for match in sorted_matches:
            is_duplicate = False
            for existing in filtered:
                dist = ((match[0] - existing[0])**2 + (match[1] - existing[1])**2)**0.5
                if dist < min_distance:
                    is_duplicate = True
                    break
            if not is_duplicate:
                filtered.append(match)

        return filtered

    @staticmethod
    def save_screenshot(path: str, region: Optional[Tuple[int, int, int, int]] = None):
        """Save a screenshot for creating templates."""
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save(path)
        print(f"Screenshot saved to: {path}")
