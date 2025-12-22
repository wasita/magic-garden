"""
DOM-based element detection using Chrome DevTools Protocol.
Replaces OCR-based screen capture for more reliable detection.

Requires Discord to be launched with remote debugging enabled:
    discord --remote-debugging-port=9222

Or on macOS:
    /Applications/Discord.app/Contents/MacOS/Discord --remote-debugging-port=9222
"""

import time
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass


@dataclass
class DOMElement:
    """Represents a DOM element with its properties."""
    selector: str
    text: str
    visible: bool
    enabled: bool
    bounding_box: Optional[Dict[str, float]] = None
    attributes: Optional[Dict[str, str]] = None


class DOMCapture:
    """DOM-based element detection for Discord games via CDP."""

    def __init__(self, cdp_port: int = 9222):
        """Initialize DOM capture.

        Args:
            cdp_port: Chrome DevTools Protocol port (default 9222)
        """
        self.cdp_port = cdp_port
        self.cdp_url = f"http://localhost:{cdp_port}"
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.game_frame = None
        self._connected = False

    def connect(self, game_frame_selector: str = "iframe") -> bool:
        """Connect to Discord via CDP and find the game frame.

        Args:
            game_frame_selector: CSS selector for the game iframe

        Returns:
            True if connection successful, False otherwise
        """
        try:
            from playwright.sync_api import sync_playwright

            self.playwright = sync_playwright().start()

            # Connect to existing Discord browser via CDP
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_url)

            # Get the default context (Discord's window)
            contexts = self.browser.contexts
            if not contexts:
                print("[DOM] No browser contexts found")
                return False

            self.context = contexts[0]

            # Find the page with the game
            pages = self.context.pages
            if not pages:
                print("[DOM] No pages found in context")
                return False

            # Look for the page containing the game
            self.page = None
            for page in pages:
                try:
                    # Check if this page has the game frame
                    frame = page.frame_locator(game_frame_selector).first
                    if frame:
                        self.page = page
                        self.game_frame = frame
                        print(f"[DOM] Found game frame in page: {page.url[:50]}...")
                        break
                except Exception:
                    continue

            if not self.page:
                # Use first page if no game frame found
                self.page = pages[0]
                print(f"[DOM] Using first page: {self.page.url[:50]}...")
                print("[DOM] Warning: Game frame not found, will search in main page")

            self._connected = True
            print(f"[DOM] Connected to Discord via CDP on port {self.cdp_port}")
            return True

        except Exception as e:
            print(f"[DOM] Failed to connect: {e}")
            print("[DOM] Make sure Discord is running with --remote-debugging-port=9222")
            self._connected = False
            return False

    def disconnect(self):
        """Disconnect from the browser."""
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"[DOM] Error during disconnect: {e}")
        finally:
            self.browser = None
            self.playwright = None
            self.page = None
            self.game_frame = None
            self._connected = False
            print("[DOM] Disconnected")

    def is_connected(self) -> bool:
        """Check if connected to Discord."""
        return self._connected and self.page is not None

    def _get_context(self):
        """Get the appropriate context (game frame or page)."""
        if self.game_frame:
            return self.game_frame
        return self.page

    def find_element(self, selector: str, timeout: float = 1.0) -> Optional[DOMElement]:
        """Find a single element by CSS selector.

        Args:
            selector: CSS selector
            timeout: Max time to wait for element (seconds)

        Returns:
            DOMElement if found, None otherwise
        """
        if not self.is_connected():
            return None

        try:
            ctx = self._get_context()
            locator = ctx.locator(selector).first

            # Wait briefly for element
            try:
                locator.wait_for(timeout=timeout * 1000, state="attached")
            except Exception:
                return None

            # Get element properties
            visible = locator.is_visible()
            enabled = locator.is_enabled()
            text = ""
            try:
                text = locator.text_content() or ""
            except Exception:
                pass

            bbox = None
            try:
                bbox = locator.bounding_box()
            except Exception:
                pass

            return DOMElement(
                selector=selector,
                text=text.strip(),
                visible=visible,
                enabled=enabled,
                bounding_box=bbox
            )

        except Exception as e:
            print(f"[DOM] Error finding element '{selector}': {e}")
            return None

    def find_elements(self, selector: str) -> List[DOMElement]:
        """Find all elements matching a CSS selector.

        Args:
            selector: CSS selector

        Returns:
            List of DOMElement objects
        """
        if not self.is_connected():
            return []

        try:
            ctx = self._get_context()
            locator = ctx.locator(selector)
            count = locator.count()

            elements = []
            for i in range(count):
                item = locator.nth(i)
                try:
                    visible = item.is_visible()
                    enabled = item.is_enabled()
                    text = item.text_content() or ""
                    bbox = None
                    try:
                        bbox = item.bounding_box()
                    except Exception:
                        pass

                    elements.append(DOMElement(
                        selector=f"{selector}:nth-child({i + 1})",
                        text=text.strip(),
                        visible=visible,
                        enabled=enabled,
                        bounding_box=bbox
                    ))
                except Exception:
                    continue

            return elements

        except Exception as e:
            print(f"[DOM] Error finding elements '{selector}': {e}")
            return []

    def element_exists(self, selector: str, visible_only: bool = True) -> bool:
        """Check if an element exists.

        Args:
            selector: CSS selector
            visible_only: Only return True if element is visible

        Returns:
            True if element exists (and is visible if visible_only=True)
        """
        element = self.find_element(selector, timeout=0.5)
        if element is None:
            return False
        if visible_only:
            return element.visible
        return True

    def get_element_text(self, selector: str) -> Optional[str]:
        """Get text content of an element.

        Args:
            selector: CSS selector

        Returns:
            Text content or None if element not found
        """
        element = self.find_element(selector)
        return element.text if element else None

    def click_element(self, selector: str, timeout: float = 2.0) -> bool:
        """Click an element by selector.

        Args:
            selector: CSS selector
            timeout: Max time to wait for element

        Returns:
            True if clicked successfully, False otherwise
        """
        if not self.is_connected():
            return False

        try:
            ctx = self._get_context()
            locator = ctx.locator(selector).first

            # Wait for element to be clickable
            locator.wait_for(timeout=timeout * 1000, state="visible")
            locator.click()
            return True

        except Exception as e:
            print(f"[DOM] Error clicking '{selector}': {e}")
            return False

    def has_class(self, selector: str, class_name: str) -> bool:
        """Check if an element has a specific class.

        Args:
            selector: CSS selector
            class_name: Class name to check for

        Returns:
            True if element has the class
        """
        if not self.is_connected():
            return False

        try:
            ctx = self._get_context()
            locator = ctx.locator(selector).first

            classes = locator.get_attribute("class") or ""
            return class_name in classes.split()

        except Exception:
            return False

    def wait_for_element(self, selector: str, timeout: float = 5.0, state: str = "visible") -> bool:
        """Wait for an element to appear.

        Args:
            selector: CSS selector
            timeout: Max time to wait (seconds)
            state: State to wait for ("attached", "visible", "hidden", "detached")

        Returns:
            True if element appeared, False if timeout
        """
        if not self.is_connected():
            return False

        try:
            ctx = self._get_context()
            locator = ctx.locator(selector).first
            locator.wait_for(timeout=timeout * 1000, state=state)
            return True

        except Exception:
            return False

    def scroll_to_element(self, selector: str) -> bool:
        """Scroll an element into view.

        Args:
            selector: CSS selector

        Returns:
            True if scrolled successfully
        """
        if not self.is_connected():
            return False

        try:
            ctx = self._get_context()
            locator = ctx.locator(selector).first
            locator.scroll_into_view_if_needed()
            return True

        except Exception as e:
            print(f"[DOM] Error scrolling to '{selector}': {e}")
            return False

    def find_shop_items_with_stock(
        self,
        targets: List[Dict[str, Any]],
        item_row_selector: str,
        stock_indicator_selector: str,
        no_stock_class: str,
        debug: bool = False
    ) -> List[Tuple[str, str, DOMElement]]:
        """Find shop items that have stock available.

        Args:
            targets: List of target configs with 'name' and 'selector' keys
            item_row_selector: Selector for item rows
            stock_indicator_selector: Selector for stock indicator within item
            no_stock_class: Class that indicates no stock

        Returns:
            List of (target_name, selector, element) tuples for items with stock
        """
        if not self.is_connected():
            return []

        found_items = []

        for target in targets:
            if not target.get("enabled", True):
                continue

            name = target.get("name", "Unknown")
            selector = target.get("selector", "")

            if not selector:
                continue

            try:
                element = self.find_element(selector, timeout=0.3)
                if not element or not element.visible:
                    if debug:
                        print(f"[DOM] {name}: not visible")
                    continue

                # Check if out of stock
                if self.has_class(selector, no_stock_class):
                    if debug:
                        print(f"[DOM] {name}: out of stock (has class '{no_stock_class}')")
                    continue

                # Check stock indicator text
                stock_sel = f"{selector} {stock_indicator_selector}"
                stock_text = self.get_element_text(stock_sel)
                if stock_text and ("0" in stock_text or "no stock" in stock_text.lower()):
                    if debug:
                        print(f"[DOM] {name}: no stock (stock text: '{stock_text}')")
                    continue

                # Item is available
                found_items.append((name, selector, element))
                if debug:
                    print(f"[DOM] {name}: AVAILABLE")

            except Exception as e:
                if debug:
                    print(f"[DOM] Error checking {name}: {e}")
                continue

        return found_items

    def get_all_text_on_page(self) -> str:
        """Get all visible text on the page (for debugging).

        Returns:
            All visible text content
        """
        if not self.is_connected():
            return ""

        try:
            ctx = self._get_context()
            if hasattr(ctx, 'text_content'):
                return ctx.text_content() or ""
            return self.page.content() if self.page else ""
        except Exception as e:
            print(f"[DOM] Error getting page text: {e}")
            return ""

    def evaluate_js(self, script: str) -> Any:
        """Execute JavaScript in the page context.

        Args:
            script: JavaScript code to execute

        Returns:
            Result of the script execution
        """
        if not self.is_connected():
            return None

        try:
            if self.game_frame:
                # For frame, we need to use the frame's page
                return self.page.evaluate(script)
            return self.page.evaluate(script)
        except Exception as e:
            print(f"[DOM] Error executing JS: {e}")
            return None

    def take_screenshot(self, path: str = "screenshot.png") -> bool:
        """Take a screenshot of the page.

        Args:
            path: Path to save screenshot

        Returns:
            True if successful
        """
        if not self.is_connected():
            return False

        try:
            self.page.screenshot(path=path)
            print(f"[DOM] Screenshot saved to {path}")
            return True
        except Exception as e:
            print(f"[DOM] Error taking screenshot: {e}")
            return False


def discover_selectors(cdp_port: int = 9222):
    """Interactive tool to discover DOM selectors in Discord.

    This function helps you find the correct CSS selectors for game elements.
    """
    print("=" * 60)
    print("DOM Selector Discovery Tool")
    print("=" * 60)
    print()
    print("Make sure Discord is running with:")
    print(f"  discord --remote-debugging-port={cdp_port}")
    print()

    dom = DOMCapture(cdp_port)

    if not dom.connect():
        print("Failed to connect to Discord. Is it running with remote debugging?")
        return

    print("Connected! Now you can explore the DOM.")
    print()
    print("Commands:")
    print("  find <selector>  - Find elements matching selector")
    print("  text <selector>  - Get text content of element")
    print("  click <selector> - Click an element")
    print("  all              - Show all visible text")
    print("  screenshot       - Take a screenshot")
    print("  quit             - Exit")
    print()

    try:
        while True:
            cmd = input(">>> ").strip()
            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if action == "quit" or action == "q":
                break
            elif action == "find":
                elements = dom.find_elements(arg)
                print(f"Found {len(elements)} elements:")
                for i, el in enumerate(elements):
                    print(f"  [{i}] visible={el.visible} text='{el.text[:50]}...' " if len(el.text) > 50 else f"  [{i}] visible={el.visible} text='{el.text}'")
            elif action == "text":
                text = dom.get_element_text(arg)
                print(f"Text: {text}")
            elif action == "click":
                success = dom.click_element(arg)
                print(f"Click: {'success' if success else 'failed'}")
            elif action == "all":
                text = dom.get_all_text_on_page()
                print(text[:2000] + "..." if len(text) > 2000 else text)
            elif action == "screenshot":
                dom.take_screenshot()
            else:
                print(f"Unknown command: {action}")

    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        dom.disconnect()


if __name__ == "__main__":
    # Run the discovery tool when executed directly
    discover_selectors()
