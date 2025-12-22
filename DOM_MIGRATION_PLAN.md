# Migration Plan: OCR Detection to DOM-Based Detection

## Executive Summary

This plan outlines the migration from OCR-based screen capture detection to DOM-based element selection for the Magic Garden auto-buyer. The new approach will be more reliable, faster, and easier to maintain.

## Current Architecture (OCR-Based)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  PyAutoGUI      │───▶│  Screenshot      │───▶│  Pytesseract/   │
│  Screenshot     │    │  (numpy array)   │    │  EasyOCR        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Fuzzy Text     │
                                               │  Matching       │
                                               └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Coordinate     │
                                               │  Click          │
                                               └─────────────────┘
```

**Problems:**
- OCR is slow (~500ms per scan)
- Fuzzy matching produces false positives/negatives
- Color-based button detection is unreliable
- Requires careful region calibration
- Breaks when game UI changes fonts/colors

## Target Architecture (DOM-Based)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Discord        │───▶│  Chrome DevTools │───▶│  Playwright/    │
│  (Electron App) │    │  Protocol (CDP)  │    │  Selenium       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  DOM Queries    │
                                               │  (CSS Selectors)│
                                               └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Element.click()│
                                               └─────────────────┘
```

**Benefits:**
- Instant element detection (no OCR processing)
- 100% accurate element identification
- No coordinate calculation needed
- Resilient to visual changes
- Can detect element states (enabled, disabled, hidden)

---

## Phase 1: Discord DevTools Setup

### 1.1 Enable DevTools in Discord

Discord is an Electron app, which means it runs Chromium under the hood. To access DevTools:

**Option A: Launch Flag (Recommended)**
```bash
# macOS
/Applications/Discord.app/Contents/MacOS/Discord --remote-debugging-port=9222

# Windows
"C:\Users\<username>\AppData\Local\Discord\app-<version>\Discord.exe" --remote-debugging-port=9222

# Linux
discord --remote-debugging-port=9222
```

**Option B: Environment Variable**
```bash
ELECTRON_ENABLE_LOGGING=1 discord
```

### 1.2 Connect to DevTools

Once Discord is running with remote debugging:
1. Open Chrome and navigate to `chrome://inspect`
2. Click "Configure" and add `localhost:9222`
3. Discord windows will appear under "Remote Target"
4. Click "Inspect" to open DevTools for the game

### 1.3 Identify DOM Elements

Use DevTools to identify CSS selectors for:
- Shop items (seed names, egg names)
- Stock indicators
- Buy buttons
- Close/dismiss buttons
- Navigation elements

---

## Phase 2: New Configuration Schema

### 2.1 Updated config.json Structure

```json
{
  "detection_mode": "dom",
  "scan_interval": 0.5,
  "click_delay": 0.2,

  "discord": {
    "remote_debugging_port": 9222,
    "game_frame_selector": "iframe[src*='magic-garden']"
  },

  "dom_selectors": {
    "shop": {
      "container": ".shop-container",
      "item_row": ".shop-item-row",
      "item_name": ".item-name",
      "stock_indicator": ".stock-count",
      "no_stock_class": "out-of-stock"
    },
    "buttons": {
      "buy": ".buy-button:not(:disabled)",
      "close": ".close-button, .modal-close, [aria-label='Close']",
      "open_seed_shop": "[data-action='open-seed-shop']",
      "open_egg_shop": "[data-action='open-egg-shop']"
    },
    "navigation": {
      "shop_teleport": "[data-action='teleport-shop']"
    }
  },

  "purchase_targets": [
    {
      "name": "Mythical Egg",
      "selector": ".shop-item[data-item='mythical-egg']",
      "enabled": true
    },
    {
      "name": "Bamboo Seed",
      "selector": ".shop-item[data-item='bamboo-seed']",
      "enabled": true
    },
    {
      "name": "Sunflower Seed",
      "selector": ".shop-item[data-item='sunflower-seed']",
      "enabled": true
    }
  ],

  "fallback": {
    "use_ocr_if_dom_fails": true,
    "ocr_targets": ["Mythical Egg", "Bamboo Seed"]
  }
}
```

### 2.2 Configuration Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `detection_mode` | string | "dom" or "ocr" - which detection method to use |
| `discord.remote_debugging_port` | int | CDP port for connecting to Discord |
| `discord.game_frame_selector` | string | Selector for the game iframe within Discord |
| `dom_selectors.shop.*` | string | CSS selectors for shop elements |
| `dom_selectors.buttons.*` | string | CSS selectors for interactive buttons |
| `purchase_targets` | array | Items to purchase with their DOM selectors |
| `fallback.use_ocr_if_dom_fails` | bool | Whether to fall back to OCR |

---

## Phase 3: Implementation

### 3.1 New Module: `src/dom_capture.py`

```python
"""
DOM-based element detection using Chrome DevTools Protocol.
Replaces OCR-based screen capture for more reliable detection.
"""

from playwright.sync_api import sync_playwright, Page, Browser
from typing import Optional, List, Dict, Tuple
import time


class DOMCapture:
    """DOM-based element detection for Discord games."""

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.game_frame = None

    def connect(self, game_frame_selector: str = None) -> bool:
        """Connect to Discord via CDP."""
        pass

    def find_elements(self, selector: str) -> List[dict]:
        """Find elements matching CSS selector."""
        pass

    def find_shop_items_with_stock(self, targets: List[dict]) -> List[dict]:
        """Find shop items that have stock available."""
        pass

    def click_element(self, selector: str) -> bool:
        """Click an element by selector."""
        pass

    def element_exists(self, selector: str) -> bool:
        """Check if element exists and is visible."""
        pass

    def get_element_text(self, selector: str) -> Optional[str]:
        """Get text content of an element."""
        pass

    def wait_for_element(self, selector: str, timeout: float = 5.0) -> bool:
        """Wait for element to appear."""
        pass

    def disconnect(self):
        """Disconnect from browser."""
        pass
```

### 3.2 Updated `src/auto_buyer.py`

Key changes:
1. Add `DOMCapture` as alternative to `ScreenCapture`
2. New method `_buy_until_no_stock_dom()` using DOM queries
3. Detection mode switch based on config
4. Fallback to OCR if DOM fails

```python
class AutoBuyer:
    def __init__(self, config: Config):
        self.config = config
        self.detection_mode = config.get("detection_mode", "ocr")

        if self.detection_mode == "dom":
            from .dom_capture import DOMCapture
            self.dom = DOMCapture(
                f"http://localhost:{config.get('discord.remote_debugging_port', 9222)}"
            )
        else:
            self.screen = ScreenCapture(config.get("confidence_threshold", 0.8))

        # ... rest of init

    def _buy_all_items_dom(self, shop_type: str):
        """Buy all items using DOM detection."""
        targets = self.config.get("purchase_targets", [])

        for target in targets:
            if not target.get("enabled", True):
                continue

            selector = target.get("selector")
            if not selector:
                continue

            # Check if item has stock
            item_elem = self.dom.find_element(selector)
            if not item_elem:
                continue

            # Check stock status
            stock_sel = f"{selector} {self.config.get('dom_selectors.shop.stock_indicator')}"
            if self.dom.has_class(selector, self.config.get('dom_selectors.shop.no_stock_class')):
                self._log(f"{target['name']}: NO STOCK")
                continue

            # Click item to expand
            self.dom.click_element(selector)
            time.sleep(0.3)

            # Find and click buy button
            buy_selector = self.config.get('dom_selectors.buttons.buy')
            while self.dom.element_exists(buy_selector):
                self.dom.click_element(buy_selector)
                self.items_purchased += 1
                self._log(f"Purchased {target['name']}!")
                time.sleep(self.config.get("click_delay", 0.2))
```

### 3.3 File Structure After Migration

```
magic-garden/
├── src/
│   ├── __init__.py
│   ├── auto_buyer.py      # Updated with DOM support
│   ├── config.py          # Updated schema validation
│   ├── dom_capture.py     # NEW: DOM-based detection
│   ├── screen_capture.py  # Kept for OCR fallback
│   └── gui.py             # Updated for mode selection
├── config.json            # New schema with DOM selectors
├── main.py                # Updated CLI args
└── requirements.txt       # Add playwright
```

---

## Phase 4: Implementation Steps

### Step 1: Add Playwright Dependency
```bash
pip install playwright
playwright install chromium
```

Update `requirements.txt`:
```
playwright>=1.40.0
```

### Step 2: Create `dom_capture.py` Module
- Implement CDP connection
- Element finding methods
- Click handling
- Stock detection

### Step 3: Update Config Schema
- Add new fields for DOM selectors
- Maintain backward compatibility
- Add validation

### Step 4: Update AutoBuyer
- Add detection mode switch
- Implement DOM-based buying flow
- Add fallback logic

### Step 5: Document DOM Selectors
- Create guide for finding selectors
- Document common game elements
- Provide selector discovery tools

---

## Phase 5: Selector Discovery Guide

### How to Find Selectors in Discord

1. **Launch Discord with DevTools:**
   ```bash
   discord --remote-debugging-port=9222
   ```

2. **Connect Chrome DevTools:**
   - Open `chrome://inspect` in Chrome
   - Configure `localhost:9222`
   - Click "Inspect" on Discord target

3. **Navigate to Game:**
   - Open Magic Garden in Discord
   - The game runs in an iframe

4. **Find Game Frame:**
   ```javascript
   // In DevTools Console
   document.querySelectorAll('iframe')
   ```

5. **Inspect Elements:**
   - Use Elements panel to inspect shop items
   - Right-click element → Copy → Copy selector
   - Test selector in Console:
   ```javascript
   document.querySelector('.your-selector')
   ```

6. **Document Selectors:**
   - Item rows: Look for repeating patterns
   - Buttons: Look for data-* attributes or specific classes
   - Stock: Look for text/number elements near items

### Example Selector Patterns

```javascript
// Common patterns in game UIs
'.shop-item'                    // Item container
'.shop-item .name'              // Item name
'.shop-item .stock'             // Stock count
'.shop-item .buy-btn'           // Buy button
'.shop-item.out-of-stock'       // No stock indicator
'[data-item-id="bamboo"]'       // Data attribute selector
'button:contains("Buy")'        // Button by text (jQuery)
```

---

## Phase 6: Migration Checklist

- [ ] Add Playwright to requirements
- [ ] Create `src/dom_capture.py` module
- [ ] Update `config.json` schema
- [ ] Add `--dom-mode` CLI flag
- [ ] Update `AutoBuyer` with detection mode
- [ ] Implement `_buy_all_items_dom()`
- [ ] Add fallback to OCR
- [ ] Test with Discord DevTools
- [ ] Document all discovered selectors
- [ ] Update GUI for mode selection
- [ ] Create selector discovery helper tool

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Discord updates break selectors | Use robust selectors (data-* attrs), maintain OCR fallback |
| CDP connection fails | Retry logic, clear error messages, fallback to OCR |
| Game runs in sandboxed iframe | Document cross-origin handling, test iframe access |
| Performance issues with Playwright | Use lightweight CDP calls, avoid full page loads |

---

## Timeline

This migration can be completed incrementally:

1. **Foundation** - Create dom_capture.py, add Playwright
2. **Integration** - Update AutoBuyer with DOM mode
3. **Discovery** - Document all game selectors
4. **Polish** - GUI updates, error handling, tests
