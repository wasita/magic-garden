import time
import threading
import pyautogui
from typing import Optional, Callable, Tuple
from .screen_capture import ScreenCapture
from .config import Config

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
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("Auto-buyer started")

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
        """Main scanning loop."""
        scan_interval = self.config.get("scan_interval", 0.5)
        region = self.config.get("monitor_region")

        while self.running:
            if self.paused:
                time.sleep(0.1)
                continue

            try:
                self._scan_and_buy(region)
            except Exception as e:
                self._log(f"Error during scan: {e}")

            time.sleep(scan_interval)

    def _scan_and_buy(self, region: Optional[Tuple[int, int, int, int]]):
        """Scan screen and attempt to buy if items found."""
        screen = self.screen.capture_screen(region)

        # Check for mythical egg
        egg_match = self.screen.find_template(screen, "mythical_egg")
        if egg_match:
            self._handle_detection("mythical_egg", egg_match, region)

        # Check for mythical seed
        seed_match = self.screen.find_template(screen, "mythical_seed")
        if seed_match:
            self._handle_detection("mythical_seed", seed_match, region)

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
