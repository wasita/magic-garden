import time
import threading
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

# Safety settings for pyautogui
pyautogui.FAILSAFE = True  # Move mouse to corner to abort
pyautogui.PAUSE = 0.1

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

        # Capture game window region from user click
        self._log("Click on your game window within 3 seconds...")
        self.game_region = self._wait_for_click_region(timeout=3.0)
        if self.game_region:
            self._log(f"Game region set: {self.game_region}")
        else:
            self._log("Using config region as fallback")
            self.game_region = self.config.get("monitor_region")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        # Startup delay to let user focus the game window
        startup_delay = self.config.get("startup_delay", 3)
        if startup_delay > 0:
            self._log(f"Starting in {startup_delay}s - focus the game window!")
            time.sleep(startup_delay)

        self._log("Auto-buyer started")

    def _wait_for_click_region(self, timeout: float = 10.0) -> Optional[Tuple[int, int, int, int]]:
        """Wait for user to click and create a region around that point."""
        import time
        from pynput import mouse

        click_pos = None

        def on_click(x, y, button, pressed):
            nonlocal click_pos
            if pressed:
                click_pos = (x, y)
                return False  # Stop listener

        # Listen for mouse click
        listener = mouse.Listener(on_click=on_click)
        listener.start()

        start_time = time.time()
        while click_pos is None and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        listener.stop()

        if click_pos:
            # Create region centered around click point
            # Default window size (can be configured)
            window_width = self.config.get("window_width", 500)
            window_height = self.config.get("window_height", 900)

            # Convert to integers (pynput returns floats on macOS)
            click_x = int(click_pos[0])
            x = click_x - window_width // 2
            y = 0  # Start from top of screen

            # Make sure x doesn't go negative
            x = max(0, x)

            return (x, y, window_width, window_height)

        return None

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
        click_delay = self.config.get("click_delay", 0.1)
        nav = self.config.get("navigation", {})

        shop_btn = nav.get("shop_button", "Shop")
        seed_shop_btn = nav.get("seed_shop_button", "Open Seed Shop")
        egg_shop_btn = nav.get("egg_shop_button", "Open Egg Shop")

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
        pyautogui.hotkey('shift', '1')
        self._log("Pressed Shift+1 to teleport to shop")
        time.sleep(1.0)  # Wait for teleport

        # Step 2: Press space to open Seed Shop panel
        pyautogui.press('space')
        self._log("Pressed space to open Seed Shop")
        time.sleep(1.5)  # Wait for shop to open

        # Step 3: Buy seeds from the open shop (scrolling down to see all items)
        self._buy_all_items_in_shop_with_scroll(region, shop_type="seed")

        # Step 4: Press up arrow until "Open Egg Shop" is visible (template matching)
        max_scroll_attempts = 10
        for _ in range(max_scroll_attempts):
            screen = self.screen.capture_screen(region)
            if self.screen.find_template(screen, "open_egg_shop"):
                break
            pyautogui.press('up')
            time.sleep(click_delay * 2)

        # Step 5: Open Egg Shop and buy eggs (press space to open)
        screen = self.screen.capture_screen(region)
        if self.screen.find_template(screen, "open_egg_shop"):
            pyautogui.press('space')
            self._log("Pressed space to open Egg Shop")
            time.sleep(1.5)  # Wait for shop to open
            self._buy_all_items_in_shop_with_scroll(region, shop_type="egg")

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
        ocr_targets = self.config.get("ocr_targets", [])
        max_scroll_pages = 5  # Maximum number of times to scroll down

        # Filter targets based on shop type
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

            # Try to buy each target on the current page
            found_any = False
            for target in targets:
                if not self.running or self.paused:
                    return

                screen = self.screen.capture_screen(region)
                pos = self.screen.get_text_center(screen, target)
                if pos:
                    found_any = True
                    self._log(f"Found {target} on page {page + 1}")
                    self._buy_until_no_stock(target, region)

            # Scroll down to see more items (use mouse scroll, not arrow keys)
            if region:
                # Move mouse to center of region before scrolling
                scroll_x = region[0] + region[2] // 2
                scroll_y = region[1] + region[3] // 2
                pyautogui.moveTo(scroll_x, scroll_y)
            pyautogui.scroll(-3)  # Negative = scroll down
            self._log("Scrolled down")
            time.sleep(0.5)

    def _buy_until_no_stock(self, target: str, region: Optional[Tuple[int, int, int, int]]):
        """Keep buying a specific item until NO STOCK appears."""
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
