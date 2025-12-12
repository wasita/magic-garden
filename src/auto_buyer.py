import time
import threading
import platform
import pyautogui
from typing import Optional, Callable, Tuple, List
from .screen_capture import ScreenCapture
from .config import Config

# For active window detection on macOS
try:
    from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False

# For DirectInput on Windows (games ignore pyautogui virtual keys)
IS_WINDOWS = platform.system() == "Windows"
if IS_WINDOWS:
    try:
        import pydirectinput
        pydirectinput.PAUSE = 0.1
        HAS_DIRECTINPUT = True
    except ImportError:
        HAS_DIRECTINPUT = False
        print("Warning: pydirectinput not installed. Key presses may not work in games.")
        print("Install with: pip install pydirectinput")
else:
    HAS_DIRECTINPUT = False

# Safety settings for pyautogui
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.1


def _press_key(key: str):
    """Press a key using DirectInput on Windows, pyautogui otherwise."""
    if IS_WINDOWS and HAS_DIRECTINPUT:
        pydirectinput.press(key)
    else:
        pyautogui.press(key)


def _hotkey(*keys):
    """Press a hotkey combo using DirectInput on Windows, pyautogui otherwise."""
    if IS_WINDOWS and HAS_DIRECTINPUT:
        # pydirectinput doesn't have hotkey(), so we do it manually
        for key in keys:
            pydirectinput.keyDown(key)
        for key in reversed(keys):
            pydirectinput.keyUp(key)
    else:
        pyautogui.hotkey(*keys)


class AutoBuyer:
    def __init__(self, config: Config):
        self.config = config
        self.screen = ScreenCapture(config.get("confidence_threshold", 0.8))
        self.running = False
        self.paused = False
        self._thread: Optional[threading.Thread] = None

        # Stats
        self.items_detected = 0
        self.items_purchased = 0
        self.last_detection_time: Optional[float] = None

        # Navigation state
        self.in_shop = False
        self.game_region: Optional[Tuple[int, int, int, int]] = None

        # Callbacks
        self.on_detection: Optional[Callable[[str, Tuple[int, int]], None]] = None
        self.on_purchase: Optional[Callable[[str], None]] = None
        self.on_status_change: Optional[Callable[[str], None]] = None

    def load_templates(self) -> bool:
        """Load all template images from config."""
        templates = self.config.get("templates", {})
        success = True

        for name, path in templates.items():
            if not self.screen.load_template(name, path):
                success = False
                self._log(f"Failed to load template: {name}")
            else:
                self._log(f"Loaded template: {name}")

        return success

    def start(self):
        """Start the auto-buyer loop in a separate thread."""
        if self.running:
            return

        self.running = True
        self.paused = False

        # Use monitor_region from config
        self.game_region = self.config.get("monitor_region")
        if self.game_region:
            self._log(f"Using config region: {self.game_region}")
        else:
            self._log("No region configured - using full screen")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Startup delay to let user focus the game window
        startup_delay = self.config.get("startup_delay", 3)
        if startup_delay > 0:
            self._log(f"Starting in {startup_delay}s - focus the game window!")
            time.sleep(startup_delay)

        self._log("Auto-buyer started")

    def _wait_for_two_click_region(self, timeout: float = 30.0) -> Optional[Tuple[int, int, int, int]]:
        """Wait for user to position mouse with countdown."""
        import pyautogui

        # First corner
        self._log("Press ENTER, then move mouse to TOP-LEFT corner (3 sec countdown)...")
        input()
        for i in range(3, 0, -1):
            self._log(f"  {i}...")
            time.sleep(1)
        pos1 = pyautogui.position()
        x1, y1 = int(pos1.x), int(pos1.y)
        self._log(f"Got top-left: ({x1}, {y1})")

        # Second corner
        self._log("Press ENTER, then move mouse to BOTTOM-RIGHT corner (3 sec countdown)...")
        input()
        for i in range(3, 0, -1):
            self._log(f"  {i}...")
            time.sleep(1)
        pos2 = pyautogui.position()
        x2, y2 = int(pos2.x), int(pos2.y)
        self._log(f"Got bottom-right: ({x2}, {y2})")

        # Ensure top-left and bottom-right are correct
        left = min(x1, x2)
        top = min(y1, y2)
        right = max(x1, x2)
        bottom = max(y1, y2)

        width = right - left
        height = bottom - top

        self._log(f"Region defined: ({left}, {top}) to ({right}, {bottom}) = {width}x{height}")
        return (left, top, width, height)

    def stop(self):
        """Stop the auto-buyer."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._log("Auto-buyer stopped")

    def toggle_pause(self):
        """Toggle pause state."""
        self.paused = not self.paused
        status = "paused" if self.paused else "resumed"
        self._log(f"Auto-buyer {status}")

    def _run_loop(self):
        """Main loop: navigate shop and buy items."""
        scan_interval = self.config.get("scan_interval", 0.5)
        region = self.config.get("monitor_region")

        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue

            try:
                self._shop_cycle(region)
            except Exception as e:
                self._log(f"Error during shop cycle: {e}")

            time.sleep(scan_interval)

    def _shop_cycle(self, region: Optional[Tuple[int, int, int, int]]):
        """Complete one shop cycle: open shop, buy seeds, buy eggs."""
        self._log("=== Starting new shop cycle ===")
        click_delay = self.config.get("click_delay", 0.1)
        shop_mode = self.config.get("shop_mode", "both")  # "seed", "egg", or "both"

        # Use the region captured from user click at startup
        region = self.game_region
        if region:
            self._log(f"Using region: {region}")

        # Focus the game window by clicking in the center of the region
        if region:
            center_x = region[0] + region[2] // 2
            center_y = region[1] + region[3] // 2
            pyautogui.click(center_x, center_y)
            self._log(f"Clicked center ({center_x}, {center_y}) to focus game")
            time.sleep(0.5)

        # Step 1: Teleport to shop using Shift+1
        _hotkey('shift', '1')
        self._log("Pressed Shift+1 to teleport to shop")
        time.sleep(1.0)  # Wait for teleport

        # Step 2: Press space to open Seed Shop panel
        _press_key('space')
        self._log("Pressed space to open Seed Shop")
        time.sleep(1.5)  # Wait for shop to open

        # Step 3: Buy seeds if enabled
        if shop_mode in ("seed", "both"):
            self._log("Scanning seed shop...")
            self._buy_all_items_in_shop_with_scroll(region, shop_type="seed")

        # Step 4: Buy eggs if enabled
        if shop_mode in ("egg", "both"):
            # Scroll up to find "Open Egg Shop" button
            max_scroll_attempts = 10
            for _ in range(max_scroll_attempts):
                screen = self.screen.capture_screen(region)
                if self.screen.find_template(screen, "open_egg_shop"):
                    break
                _press_key('up')
                time.sleep(click_delay * 2)

            # Open Egg Shop and buy eggs
            screen = self.screen.capture_screen(region)
            if self.screen.find_template(screen, "open_egg_shop"):
                _press_key('space')
                self._log("Pressed space to open Egg Shop")
                time.sleep(1.5)  # Wait for shop to open
                self._buy_all_items_in_shop_with_scroll(region, shop_type="egg")

        self._log("=== Shop cycle complete, restarting... ===")

    def _click_text(self, text: str, region: Optional[Tuple[int, int, int, int]] = None) -> bool:
        """Find and click on text. Returns True if found and clicked."""
        screen = self.screen.capture_screen(region)
        pos = self.screen.get_text_center(screen, text)

        if pos:
            x, y = pos
            if region:
                x += region[0]
                y += region[1]
            pyautogui.click(x, y)
            self._log(f"Clicked '{text}' at ({x}, {y})")
            return True
        else:
            self._log(f"Could not find '{text}'")
            return False

    def _buy_all_items_in_shop(self, region: Optional[Tuple[int, int, int, int]], shop_type: str):
        """Buy all available items in the current shop until NO STOCK."""
        click_delay = self.config.get("click_delay", 0.1)
        ocr_targets = self.config.get("ocr_targets", [])

        # Filter targets based on shop type
        if shop_type == "seed":
            targets = [t for t in ocr_targets if "Seed" in t or "Pod" in t]
        else:  # egg
            targets = [t for t in ocr_targets if "Egg" in t]

        for target in targets:
            if not self.running or self.paused:
                return

            # Keep buying this item until NO STOCK
            self._buy_until_no_stock(target, region)

    def _buy_all_items_in_shop_with_scroll(self, region: Optional[Tuple[int, int, int, int]], shop_type: str):
        """Buy all available items in the shop, scrolling down to see all items."""
        click_delay = self.config.get("click_delay", 0.1)
        max_scroll_pages = 25  # Scroll through all pages

        # Use OCR targets from config
        ocr_targets = self.config.get("ocr_targets", [])
        if shop_type == "seed":
            targets = [t for t in ocr_targets if "Seed" in t or "Pod" in t]
        else:  # egg
            targets = [t for t in ocr_targets if "Egg" in t]

        self._log(f"Looking for {shop_type} items: {targets}")

        # Scroll through the shop and buy items on each page
        for page in range(max_scroll_pages):
            if not self.running or self.paused:
                return

            self._log(f"Scanning shop page {page + 1}")

            # Scan current page for items
            screen = self.screen.capture_screen(region)

            # Find items with STOCK on the same line (single OCR pass - fast!)
            shop_items = self.screen.find_shop_items_with_stock(screen, targets, debug=(page == 0))

            if shop_items:
                self._log(f"Found {len(shop_items)} items on page {page + 1}")

            for target, rel_x, rel_y in shop_items:
                if not self.running or self.paused:
                    return

                self._log(f"Buying '{target}' at ({rel_x},{rel_y})")
                # Pass position directly - don't re-search with OCR
                self._buy_until_no_stock_ocr(target, region, item_pos=(rel_x, rel_y))
                # Re-capture screen after buying in case layout changed
                screen = self.screen.capture_screen(region)

            # Scroll down to see more items (use mouse scroll, not arrow keys)
            if region:
                # Move mouse to center of region before scrolling
                scroll_x = region[0] + region[2] // 2
                scroll_y = region[1] + region[3] // 2
                self._log(f"Moving mouse to center: ({scroll_x}, {scroll_y}) from region {region}")
                pyautogui.moveTo(scroll_x, scroll_y)
            else:
                self._log("WARNING: No region set, cannot center mouse for scroll")
            pyautogui.scroll(-5)  # Negative = scroll down (larger value = faster scroll)
            self._log("Scrolled down")
            time.sleep(0.3)

    def _buy_until_no_stock(self, target: str, region: Optional[Tuple[int, int, int, int]]):
        """Keep buying a specific item until NO STOCK appears (OCR version)."""
        click_delay = self.config.get("click_delay", 0.1)
        max_attempts = self.config.get("max_buy_attempts", 50)  # Safety limit

        for _ in range(max_attempts):
            if not self.running or self.paused:
                return

            screen = self.screen.capture_screen(region)

            # Check if NO STOCK is visible
            if self.screen.text_exists(screen, "NO STOCK"):
                self._log(f"{target}: NO STOCK")
                return

            # Find and click the item
            pos = self.screen.get_text_center(screen, target)
            if not pos:
                return  # Item not found on this screen

            rel_x, rel_y = pos
            # Add region offset to convert from image coords to screen coords
            if region:
                abs_x = rel_x + region[0]
                abs_y = rel_y + region[1]
            else:
                abs_x, abs_y = rel_x, rel_y

            self._log(f"Clicking {target}: relative=({rel_x},{rel_y}) + region offset=({region[0] if region else 0},{region[1] if region else 0}) = absolute=({abs_x},{abs_y})")

            # Click item to expand accordion
            pyautogui.click(abs_x, abs_y)
            self.items_detected += 1
            self.last_detection_time = time.time()

            # Wait for accordion to pop up with buy button
            time.sleep(0.8)

            if self.on_detection:
                item_type = target.lower().replace(" ", "_")
                self.on_detection(item_type, (abs_x, abs_y))

            # Look for buy button (with coin icon) that appeared in accordion
            screen = self.screen.capture_screen(region)

            # Check again for NO STOCK after clicking item
            if self.screen.text_exists(screen, "NO STOCK"):
                self._log(f"{target}: NO STOCK")
                return

            # Try to find buy button via template or look for price text
            buy_match = self.screen.find_template(screen, "buy_button")
            if buy_match:
                buy_rel_x, buy_rel_y, conf = buy_match
                if region:
                    buy_abs_x = buy_rel_x + region[0]
                    buy_abs_y = buy_rel_y + region[1]
                else:
                    buy_abs_x, buy_abs_y = buy_rel_x, buy_rel_y
                self._log(f"Found buy button: relative=({buy_rel_x},{buy_rel_y}) conf={conf:.2f} -> absolute=({buy_abs_x},{buy_abs_y})")
                pyautogui.click(buy_abs_x, buy_abs_y)
                self.items_purchased += 1
                self._log(f"Purchased {target}!")

                if self.on_purchase:
                    item_type = target.lower().replace(" ", "_")
                    self.on_purchase(item_type)

                time.sleep(click_delay)
            else:
                self._log(f"Could not find buy button for {target}")
                return

    def _buy_until_no_stock_ocr(self, target: str, region: Optional[Tuple[int, int, int, int]], item_pos: Optional[Tuple[int, int]] = None):
        """Keep buying a specific item until NO STOCK appears (easyocr version)."""
        click_delay = self.config.get("click_delay", 0.1)
        max_attempts = self.config.get("max_buy_attempts", 50)

        # Use provided position or search with EasyOCR
        if item_pos:
            rel_x, rel_y = item_pos
        else:
            screen = self.screen.capture_screen(region)
            pos = self.screen.get_text_center_easyocr(screen, target)
            if not pos:
                self._log(f"Could not find {target}")
                return
            rel_x, rel_y = pos
        if region:
            abs_x = rel_x + region[0]
            abs_y = rel_y + region[1]
        else:
            abs_x, abs_y = rel_x, rel_y

        self._log(f"Clicking {target}: ({rel_x},{rel_y}) -> ({abs_x},{abs_y})")
        pyautogui.click(abs_x, abs_y)
        self.items_detected += 1
        self.last_detection_time = time.time()
        time.sleep(0.5)  # Wait for accordion to open

        if self.on_detection:
            self.on_detection(target, (abs_x, abs_y))

        # Now keep clicking the buy button until it disappears (sold out)
        for attempt in range(max_attempts):
            if not self.running or self.paused:
                return

            screen = self.screen.capture_screen(region)

            # Find green buy buttons by color detection (fast!)
            green_buttons = self.screen.find_green_buttons(screen, debug=True)

            if green_buttons:
                # Filter: button should be BELOW the item and within range horizontally
                # Scale thresholds based on region size (Mac baseline: 534 height)
                scale = region[3] / 534 if region else 1.0
                max_y_dist = int(150 * scale)  # How far below item to look
                max_x_dist = int(200 * scale)  # Horizontal tolerance

                self._log(f"Item at ({rel_x},{rel_y}), looking for button within y:[{rel_y}..{rel_y + max_y_dist}], x:[{rel_x - max_x_dist}..{rel_x + max_x_dist}]")
                self._log(f"All green buttons found: {green_buttons}")

                valid_buttons = [(x, y) for x, y in green_buttons
                                if y > rel_y and y < rel_y + max_y_dist
                                and abs(x - rel_x) < max_x_dist]

                self._log(f"Valid buttons after filter: {valid_buttons} (scale={scale:.2f})")

                if valid_buttons:
                    best_button = min(valid_buttons, key=lambda b: abs(b[1] - rel_y))
                    buy_rel_x, buy_rel_y = best_button

                    if region:
                        buy_abs_x = buy_rel_x + region[0]
                        buy_abs_y = buy_rel_y + region[1]
                    else:
                        buy_abs_x, buy_abs_y = buy_rel_x, buy_rel_y

                    self._log(f"Clicking buy button at ({buy_abs_x},{buy_abs_y})")
                    pyautogui.click(buy_abs_x, buy_abs_y)
                    self.items_purchased += 1
                    self._log(f"Purchased {target}! (attempt {attempt + 1})")

                    if self.on_purchase:
                        self.on_purchase(target)

                    time.sleep(click_delay + 0.1)  # Small delay between purchases
                else:
                    # No valid green button near the item - might be sold out
                    self._log(f"{target}: No buy button found (sold out or closed)")
                    return
            else:
                # No green buttons at all - sold out
                self._log(f"{target}: No green buttons - sold out")
                return

        self._log(f"{target}: Reached max attempts ({max_attempts})")

    def _buy_until_no_stock_template(self, template_name: str, region: Optional[Tuple[int, int, int, int]]):
        """Keep buying a specific item until NO STOCK appears (template matching version)."""
        click_delay = self.config.get("click_delay", 0.1)
        max_attempts = self.config.get("max_buy_attempts", 50)  # Safety limit

        for _ in range(max_attempts):
            if not self.running or self.paused:
                return

            screen = self.screen.capture_screen(region)

            # Check if NO STOCK is visible (still use OCR for this text)
            if self.screen.text_exists(screen, "NO STOCK"):
                self._log(f"{template_name}: NO STOCK")
                return

            # Find item using template matching
            match = self.screen.find_template(screen, template_name)
            if not match:
                return  # Item not found on this screen

            rel_x, rel_y, conf = match
            # Add region offset to convert from image coords to screen coords
            if region:
                abs_x = rel_x + region[0]
                abs_y = rel_y + region[1]
            else:
                abs_x, abs_y = rel_x, rel_y

            self._log(f"Clicking {template_name}: relative=({rel_x},{rel_y}) conf={conf:.2f} -> absolute=({abs_x},{abs_y})")

            # Click item to expand accordion
            pyautogui.click(abs_x, abs_y)
            self.items_detected += 1
            self.last_detection_time = time.time()

            # Wait for accordion to pop up with buy button
            time.sleep(0.8)

            if self.on_detection:
                self.on_detection(template_name, (abs_x, abs_y))

            # Look for buy button (with coin icon) that appeared in accordion
            screen = self.screen.capture_screen(region)

            # Check again for NO STOCK after clicking item
            if self.screen.text_exists(screen, "NO STOCK"):
                self._log(f"{template_name}: NO STOCK")
                return

            # Try to find buy button via template
            buy_match = self.screen.find_template(screen, "buy_button")
            if buy_match:
                buy_rel_x, buy_rel_y, buy_conf = buy_match
                if region:
                    buy_abs_x = buy_rel_x + region[0]
                    buy_abs_y = buy_rel_y + region[1]
                else:
                    buy_abs_x, buy_abs_y = buy_rel_x, buy_rel_y
                self._log(f"Found buy button: relative=({buy_rel_x},{buy_rel_y}) conf={buy_conf:.2f} -> absolute=({buy_abs_x},{buy_abs_y})")
                pyautogui.click(buy_abs_x, buy_abs_y)
                self.items_purchased += 1
                self._log(f"Purchased {template_name}!")

                if self.on_purchase:
                    self.on_purchase(template_name)

                time.sleep(click_delay)
            else:
                self._log(f"Could not find buy button for {template_name}")
                return

    def _scan_and_buy(self, region: Optional[Tuple[int, int, int, int]]):
        """Legacy method - scan screen and attempt to buy if items found."""
        screen = self.screen.capture_screen(region)
        use_ocr = self.config.get("use_ocr", True)

        # Check for skip text (e.g., "NO STOCK") - skip scan if found
        skip_texts = self.config.get("skip_text", ["NO STOCK"])
        if use_ocr:
            for skip in skip_texts:
                if self.screen.text_exists(screen, skip):
                    return

        if use_ocr:
            # Try OCR detection for configured targets
            ocr_targets = self.config.get("ocr_targets", ["Mythical Egg", "Sunflower Seed", "Bamboo Seed",
                                                          "Dawnbinder Pod", "Moonbinder Pod", "Cactus Seed",
                                                          "Starweaver Pod"])
            for target in ocr_targets:
                pos = self.screen.get_text_center(screen, target)
                if pos:
                    x, y = pos
                    # Adjust for region offset
                    if region:
                        x += region[0]
                        y += region[1]
                    # Convert target name to item_type (e.g., "Mythical Egg" -> "mythical_egg")
                    item_type = target.lower().replace(" ", "_")
                    self._handle_ocr_detection(item_type, (x, y), region)
        else:
            # Fall back to template matching
            egg_match = self.screen.find_template(screen, "mythical_egg")
            if egg_match:
                self._handle_detection("mythical_egg", egg_match, region)

            seed_match = self.screen.find_template(screen, "mythical_seed")
            if seed_match:
                self._handle_detection("mythical_seed", seed_match, region)

    def _handle_ocr_detection(self, item_type: str, position: Tuple[int, int], region: Optional[Tuple[int, int, int, int]]):
        """Handle item detected via OCR."""
        x, y = position

        self.items_detected += 1
        self.last_detection_time = time.time()

        self._log(f"Detected {item_type} at ({x}, {y}) via OCR")

        if self.on_detection:
            self.on_detection(item_type, (x, y))

        # Auto-buy if enabled
        if self.config.get("auto_buy", True):
            self._attempt_purchase(item_type, x, y)

    def _handle_detection(self, item_type: str, match: Tuple[int, int, float], region: Optional[Tuple[int, int, int, int]]):
        """Handle detected item."""
        x, y, confidence = match

        # Adjust coordinates if using a region
        if region:
            x += region[0]
            y += region[1]

        self.items_detected += 1
        self.last_detection_time = time.time()

        self._log(f"Detected {item_type} at ({x}, {y}) with confidence {confidence:.2f}")

        if self.on_detection:
            self.on_detection(item_type, (x, y))

        # Auto-buy if enabled
        if self.config.get("auto_buy", True):
            self._attempt_purchase(item_type, x, y)

    def _attempt_purchase(self, item_type: str, x: int, y: int):
        """Attempt to purchase the detected item."""
        click_delay = self.config.get("click_delay", 0.1)

        # Click on the item
        pyautogui.click(x, y)
        time.sleep(click_delay)

        # Look for and click buy button
        screen = self.screen.capture_screen()
        buy_match = self.screen.find_template(screen, "buy_button")

        if buy_match:
            buy_x, buy_y, _ = buy_match
            pyautogui.click(buy_x, buy_y)
            self.items_purchased += 1
            self._log(f"Purchased {item_type}!")

            if self.on_purchase:
                self.on_purchase(item_type)
        else:
            self._log(f"Could not find buy button for {item_type}")

    def _log(self, message: str):
        """Log a message and notify callback."""
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        print(full_message)

        if self.on_status_change:
            self.on_status_change(full_message)

    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            "items_detected": self.items_detected,
            "items_purchased": self.items_purchased,
            "last_detection": self.last_detection_time,
            "running": self.running,
            "paused": self.paused
        }

    def _get_active_window_region(self) -> Optional[Tuple[int, int, int, int]]:
        """Get the region (x, y, width, height) of the frontmost window on macOS."""
        if not HAS_QUARTZ:
            self._log("Quartz not available - using config region")
            return None

        try:
            # Get list of all on-screen windows
            window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)

            for window in window_list:
                # Layer 0 is typically the frontmost app window
                if window.get('kCGWindowLayer', 0) == 0:
                    bounds = window.get('kCGWindowBounds', {})
                    if bounds:
                        x = int(bounds.get('X', 0))
                        y = int(bounds.get('Y', 0))
                        w = int(bounds.get('Width', 0))
                        h = int(bounds.get('Height', 0))
                        if w > 100 and h > 100:  # Filter out tiny windows
                            return (x, y, w, h)
        except Exception as e:
            self._log(f"Error getting active window: {e}")

        return None
