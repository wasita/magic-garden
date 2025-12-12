import cv2
import numpy as np
import pyautogui
import pytesseract
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

    def find_text(self, screen: np.ndarray, search_text: str, debug: bool = False) -> Optional[Tuple[int, int, int, int]]:
        """Find text on screen using OCR.

        Args:
            screen: Screenshot as numpy array in BGR format
            search_text: Text to search for (case-insensitive)
            debug: If True, print all detected text

        Returns:
            Tuple of (x, y, width, height) for the text bounding box, or None if not found
        """
        # Convert to grayscale for better OCR
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)

        # Apply threshold to improve text detection
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        # Get OCR data with bounding boxes
        data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)

        search_lower = search_text.lower()
        search_words = search_lower.split()
        num_search_words = len(search_words)
        n_boxes = len(data['text'])

        if debug:
            all_text = [t.strip() for t in data['text'] if t.strip()]
            print(f"[DEBUG OCR] All detected text: {all_text}")

        # Single word search
        for i in range(n_boxes):
            text = data['text'][i].strip().lower()
            if search_lower in text:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                return (x, y, w, h)

        # Multi-word search - check sliding window of consecutive words
        for window_size in range(2, min(num_search_words + 2, n_boxes + 1)):
            for i in range(n_boxes - window_size + 1):
                words = [data['text'][i + j].strip() for j in range(window_size)]
                combined = " ".join(words).lower()
                if search_lower in combined:
                    x = data['left'][i]
                    y = min(data['top'][i + j] for j in range(window_size))
                    w = (data['left'][i + window_size - 1] + data['width'][i + window_size - 1]) - x
                    h = max(data['height'][i + j] for j in range(window_size))
                    return (x, y, w, h)

        return None

    def find_all_text(self, screen: np.ndarray, search_text: str) -> List[Tuple[int, int, int, int]]:
        """Find all occurrences of text on screen.

        Returns:
            List of (x, y, width, height) tuples for each match
        """
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

        data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)

        search_lower = search_text.lower()
        matches = []
        n_boxes = len(data['text'])

        for i in range(n_boxes):
            text = data['text'][i].strip().lower()
            if search_lower in text:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                matches.append((x, y, w, h))

        # Check consecutive words
        for i in range(n_boxes - 1):
            combined = f"{data['text'][i]} {data['text'][i+1]}".strip().lower()
            if search_lower in combined:
                x = data['left'][i]
                y = min(data['top'][i], data['top'][i+1])
                w = (data['left'][i+1] + data['width'][i+1]) - x
                h = max(data['height'][i], data['height'][i+1])
                matches.append((x, y, w, h))

        return matches

    def text_exists(self, screen: np.ndarray, search_text: str) -> bool:
        """Check if text exists on screen.

        Args:
            screen: Screenshot as numpy array
            search_text: Text to search for (case-insensitive)

        Returns:
            True if text is found, False otherwise
        """
        return self.find_text(screen, search_text) is not None

    def get_text_center(self, screen: np.ndarray, search_text: str) -> Optional[Tuple[int, int]]:
        """Find text and return center coordinates.

        Returns:
            Tuple of (center_x, center_y) or None if not found
        """
        result = self.find_text(screen, search_text)
        if result:
            x, y, w, h = result
            return (x + w // 2, y + h // 2)
        return None
