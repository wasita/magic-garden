import cv2
import numpy as np
import pyautogui
import pytesseract
import warnings
from pathlib import Path
from typing import Optional, Tuple, List
from PIL import Image

# Suppress torch warnings
warnings.filterwarnings("ignore", message=".*pin_memory.*")

# Lazy load easyocr (it's slow to import)
_easyocr_reader = None

def get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        import torch

        # Check if MPS (M1/M2 GPU) is available
        use_gpu = torch.backends.mps.is_available()
        if use_gpu:
            print("[EasyOCR] Using M1/M2 GPU (MPS)")
        else:
            print("[EasyOCR] Using CPU")

        _easyocr_reader = easyocr.Reader(['en'], gpu=use_gpu, verbose=False)
    return _easyocr_reader

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

    def find_template(self, screen: np.ndarray, template_name: str, debug: bool = False) -> Optional[Tuple[int, int, float]]:
        """Find a template in the screen capture using grayscale matching.

        Returns:
            Tuple of (x, y, confidence) for center of match, or None if not found
        """
        if template_name not in self.templates:
            if debug:
                print(f"[DEBUG] Template '{template_name}' not loaded")
            return None

        template = self.templates[template_name]

        # Convert both to grayscale for more robust matching
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if debug:
            print(f"[DEBUG] {template_name}: best_conf={max_val:.3f} threshold={self.confidence} at {max_loc}")

        if max_val >= self.confidence:
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            return (center_x, center_y, max_val)

        return None

    def find_all_matches(self, screen: np.ndarray, template_name: str, min_conf: float = None) -> List[Tuple[int, int, float]]:
        """Find all instances of a template in the screen capture.

        Returns:
            List of (x, y, confidence) tuples for each match
        """
        if template_name not in self.templates:
            return []

        template = self.templates[template_name]

        # Convert to grayscale for better matching
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        threshold = min_conf if min_conf is not None else self.confidence
        locations = np.where(result >= threshold)

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

    def find_text(self, screen: np.ndarray, search_text: str, debug: bool = False, fuzzy: bool = True) -> Optional[Tuple[int, int, int, int]]:
        """Find text on screen using OCR.

        Args:
            screen: Screenshot as numpy array in BGR format
            search_text: Text to search for (case-insensitive)
            debug: If True, print all detected text
            fuzzy: If True, accept partial matches (e.g., "awberry" matches "Strawberry")

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
        n_boxes = len(data['text'])

        if debug:
            all_text = [t.strip() for t in data['text'] if t.strip()]
            print(f"[DEBUG OCR] All detected text: {all_text}")

        # Build list of partial matches to accept (for fuzzy matching)
        # e.g., "Strawberry Seed" -> ["strawberry", "trawberry", "rawberry", "awberry", "seed"]
        fuzzy_patterns = []
        if fuzzy:
            for word in search_words:
                if len(word) >= 4:
                    fuzzy_patterns.append(word)  # Full word
                    # Add substrings (dropping first 1-3 chars)
                    for start in range(1, min(4, len(word) - 2)):
                        substring = word[start:]
                        if len(substring) >= 4:
                            fuzzy_patterns.append(substring)

        # Single word search
        for i in range(n_boxes):
            text = data['text'][i].strip().lower()
            if not text or len(text) < 3:
                continue

            # Check exact match first
            if search_lower in text or text in search_lower:
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                return (x, y, w, h)

            # Check fuzzy patterns (both directions)
            if fuzzy:
                for pattern in fuzzy_patterns:
                    # pattern in text: we're looking for "awberry", text is "awberry Seed"
                    # text in pattern: text is "awberry", pattern is "strawberry"
                    if (len(pattern) >= 4 and pattern in text) or (len(text) >= 4 and text in pattern):
                        x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                        return (x, y, w, h)

        # Multi-word search - check sliding window of consecutive words
        for window_size in range(2, min(len(search_words) + 2, n_boxes + 1)):
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

    def find_shop_items_with_stock(self, screen: np.ndarray, targets: list, debug: bool = False) -> List[Tuple[str, int, int]]:
        """Find shop items that have STOCK visible on the same line.

        Returns:
            List of (item_name, center_x, center_y) for items with STOCK nearby
        """
        gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
        data = pytesseract.image_to_data(thresh, output_type=pytesseract.Output.DICT)

        n_boxes = len(data['text'])
        found_items = []

        # First, find all STOCK positions
        stock_positions = []
        for i in range(n_boxes):
            text = data['text'][i].strip().lower()
            if 'stock' in text or 'stoc' in text:
                y = data['top'][i] + data['height'][i] // 2
                stock_positions.append(y)

        if debug:
            all_text = [t.strip() for t in data['text'] if t.strip()]
            print(f"[DEBUG] All text: {all_text}")
            print(f"[DEBUG] STOCK Y positions: {stock_positions}")

        # Build fuzzy patterns for each target
        # Require at least 4 chars to catch words like "fava", "bean"
        # but avoid very short words like "pod" (3 chars)
        # Exclude common category words that would match everything
        common_words = {"seed", "seeds", "pod", "pods", "bean", "beans", "egg", "eggs"}
        target_patterns = {}
        for target in targets:
            patterns = []
            for word in target.lower().split():
                if len(word) >= 4 and word not in common_words:
                    patterns.append(word)
                    # Add substrings (dropping first 1-2 chars) that are still 4+ chars
                    for start in range(1, min(3, len(word) - 3)):
                        substring = word[start:]
                        if len(substring) >= 4 and substring not in common_words:
                            patterns.append(substring)
            target_patterns[target] = patterns

        if debug:
            print(f"[DEBUG] Fuzzy patterns: {target_patterns}")

        # Find items that have STOCK on the same line (within 60px Y)
        for i in range(n_boxes):
            text = data['text'][i].strip().lower()
            if not text or len(text) < 4:
                continue

            item_y = data['top'][i] + data['height'][i] // 2
            item_x = data['left'][i] + data['width'][i] // 2

            # Check if there's a STOCK on the same line
            has_stock_on_line = any(abs(stock_y - item_y) < 60 for stock_y in stock_positions)
            if not has_stock_on_line:
                continue

            # Check if this text matches any target
            for target, patterns in target_patterns.items():
                matched = False
                # Exact match - require the distinguishing word (not just "seed" or "pod")
                # Check if text matches the first word of target (e.g., "carrot" for "Carrot Seed")
                target_words = target.lower().split()
                first_word = target_words[0] if target_words else ""
                # For short words (4 chars), require exact match or text equals first word
                if len(first_word) == 4:
                    if text == first_word:
                        matched = True
                # For longer words (5+ chars), allow substring matching
                elif len(text) >= 5 and len(first_word) >= 5 and (first_word in text or text in first_word):
                    matched = True
                # Fuzzy match - only for 5+ char patterns
                if not matched:
                    for pattern in patterns:
                        if len(pattern) >= 5 and (pattern in text or (len(text) >= 5 and text in pattern)):
                            matched = True
                            break
                        # Exact match for 4-char patterns
                        elif len(pattern) == 4 and text == pattern:
                            matched = True
                            break

                if matched:
                    found_items.append((target, item_x, item_y))
                    if debug:
                        print(f"[DEBUG] Matched '{text}' to '{target}'")
                    break  # Don't match same text to multiple targets

        return found_items

    def find_text_easyocr(self, screen: np.ndarray, search_text: str, debug: bool = False) -> Optional[Tuple[int, int, int, int]]:
        """Find text on screen using EasyOCR (better for game fonts).

        Returns:
            Tuple of (x, y, width, height) for the text bounding box, or None
        """
        reader = get_easyocr_reader()

        # Convert BGR to RGB for easyocr
        rgb = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)

        # Run OCR
        results = reader.readtext(rgb)

        if debug:
            all_text = [text for (_, text, _) in results]
            print(f"[DEBUG EasyOCR] All detected: {all_text}")

        search_lower = search_text.lower()

        for (bbox, text, conf) in results:
            if search_lower in text.lower():
                # bbox is [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                x1 = int(min(p[0] for p in bbox))
                y1 = int(min(p[1] for p in bbox))
                x2 = int(max(p[0] for p in bbox))
                y2 = int(max(p[1] for p in bbox))
                return (x1, y1, x2 - x1, y2 - y1)

        return None

    def get_text_center_easyocr(self, screen: np.ndarray, search_text: str, debug: bool = False) -> Optional[Tuple[int, int]]:
        """Find text using EasyOCR and return center coordinates."""
        result = self.find_text_easyocr(screen, search_text, debug=debug)
        if result:
            x, y, w, h = result
            return (x + w // 2, y + h // 2)
        return None

    def find_green_buttons(self, screen: np.ndarray, debug: bool = False) -> List[Tuple[int, int]]:
        """Find green buy buttons by color detection.

        Returns:
            List of (center_x, center_y) for each green button found
        """
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)

        # Try multiple green ranges to catch different shades
        # Range 1: Yellow-green to green (original range, widened)
        lower_green1 = np.array([35, 50, 80])
        upper_green1 = np.array([85, 255, 255])

        # Range 2: Brighter/more saturated greens
        lower_green2 = np.array([40, 100, 100])
        upper_green2 = np.array([80, 255, 255])

        # Create masks and combine them
        mask1 = cv2.inRange(hsv, lower_green1, upper_green1)
        mask2 = cv2.inRange(hsv, lower_green2, upper_green2)
        mask = cv2.bitwise_or(mask1, mask2)

        # Find contours (connected green regions)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Scale area thresholds based on screen size (Mac baseline: 645x534)
        screen_h, screen_w = screen.shape[:2]
        scale = (screen_w * screen_h) / (645 * 534)
        min_area = int(200 * scale)   # Lowered from 500
        max_area = int(20000 * scale)  # Increased from 10000

        if debug:
            print(f"[DEBUG] Screen {screen_w}x{screen_h}, scale={scale:.2f}, area range={min_area}-{max_area}")
            # Save debug images to project directory
            try:
                import os
                debug_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                mask_path = os.path.join(debug_dir, "debug_green_mask.png")
                screen_path = os.path.join(debug_dir, "debug_screenshot.png")
                cv2.imwrite(mask_path, mask)
                cv2.imwrite(screen_path, screen)
                print(f"[DEBUG] Saved debug images to {debug_dir}")
            except Exception as e:
                print(f"[DEBUG] Failed to save debug images: {e}")

        # For annotated debug image
        annotated = screen.copy() if debug else None

        buttons = []
        for contour in contours:
            area = cv2.contourArea(contour)
            # Filter by size - scaled for screen resolution
            if area > min_area and area < max_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Buy button must be WIDE rectangle (width > height * 1.8)
                # This filters out square-ish seed icons (cactus, bamboo, etc.)
                aspect_ratio = w / h if h > 0 else 0
                min_width = int(40 * (screen_w / 645))  # Minimum width scaled

                if aspect_ratio > 1.8 and aspect_ratio < 6.0 and w > min_width:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    buttons.append((center_x, center_y, area))
                    if debug:
                        print(f"[DEBUG] Green BUY BUTTON at ({center_x},{center_y}) size={w}x{h} area={area} ratio={aspect_ratio:.2f}")
                        # Draw rectangle and center point on annotated image
                        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.circle(annotated, (center_x, center_y), 5, (0, 0, 255), -1)
                        cv2.putText(annotated, f"BTN ({center_x},{center_y})", (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                elif debug:
                    print(f"[DEBUG] Rejected (seed icon?): size={w}x{h} ratio={aspect_ratio:.2f} (need ratio>1.8, w>{min_width})")
            elif debug and area > 50:
                print(f"[DEBUG] Rejected contour: area={area} (need {min_area}-{max_area})")

        # Sort by area (largest first) and return centers only
        buttons.sort(key=lambda b: b[2], reverse=True)

        # Save annotated image showing detected buttons
        if debug and annotated is not None:
            try:
                import os
                debug_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                annotated_path = os.path.join(debug_dir, "debug_buttons_annotated.png")
                cv2.imwrite(annotated_path, annotated)
                print(f"[DEBUG] Saved annotated image to {annotated_path}")
            except Exception as e:
                print(f"[DEBUG] Failed to save annotated image: {e}")

        return [(x, y) for x, y, _ in buttons]

    def find_close_button(self, screen: np.ndarray, debug: bool = False) -> Optional[Tuple[int, int]]:
        """Find white X close button for dismissing pop-ups.

        Returns:
            (center_x, center_y) of the close button, or None if not found
        """
        # Convert to HSV for color detection
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)

        # White/light gray X button (low saturation, high value)
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])

        # Create mask for white pixels
        mask = cv2.inRange(hsv, lower_white, upper_white)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Scale area thresholds based on screen size (Mac baseline: 645x534)
        screen_h, screen_w = screen.shape[:2]
        scale = (screen_w * screen_h) / (645 * 534)
        # X button is typically small and square-ish
        min_area = int(100 * scale)
        max_area = int(2000 * scale)

        if debug:
            print(f"[DEBUG] Looking for close button, scale={scale:.2f}, area range={min_area}-{max_area}")

        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area and area < max_area:
                x, y, w, h = cv2.boundingRect(contour)
                # X button should be roughly square
                aspect_ratio = w / h if h > 0 else 0
                if 0.5 < aspect_ratio < 2.0:
                    # Prefer buttons in top-right area of screen (common for close buttons)
                    center_x = x + w // 2
                    center_y = y + h // 2
                    # Score: prefer top-right
                    score = center_x - center_y  # Higher x, lower y = higher score
                    candidates.append((center_x, center_y, score))
                    if debug:
                        print(f"[DEBUG] Close button candidate at ({center_x},{center_y}) size={w}x{h} area={area}")

        if candidates:
            # Return the most likely close button (top-right preference)
            candidates.sort(key=lambda c: c[2], reverse=True)
            return (candidates[0][0], candidates[0][1])

        return None
