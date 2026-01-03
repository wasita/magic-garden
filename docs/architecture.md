# Bot Architecture

This document explains how the Magic Garden auto-buyer works and why certain design decisions were made.

## Current Architecture

### 1. OCR + Stock Filter (Fast Detection)

The bot uses a single OCR pass per page via `find_shop_items_with_stock()`:

```python
# Single pytesseract call scans the entire visible page
data = pytesseract.image_to_data(screen)

# Only considers items with "STOCK" text on the same line (within 60px Y)
has_stock_on_line = any(abs(stock_y - item_y) < 60 for stock_y in stock_positions)
```

- One OCR call scans the entire visible page
- Only considers items with "STOCK" text on the same line
- Fuzzy matching handles OCR errors ("amboo" → "Bamboo")

**Why it's fast:** Single OCR call vs. searching for each target individually.

### 2. Buy Until Grey (Smart Purchasing)

Instead of a fixed number of attempts, the bot clicks until the button turns grey:

```python
# Move cursor once, then click repeatedly
pyautogui.moveTo(buy_abs_x, buy_abs_y)

while True:
    pyautogui.click()  # Click at current position

    # Check if button still green
    green_buttons = find_green_buttons(screen)
    if not green_buttons:
        break  # Sold out!
```

- Cursor moves to buy button **once**, then clicks repeatedly
- Checks HSV color after each click to detect grey (sold out)

**Why it's fast:** No cursor repositioning, no arbitrary limits.

### 3. Re-scan After Purchase (Handles Layout Shifts)

After buying an item, the page layout shifts (accordion closes, items move up). The bot re-scans to get fresh positions:

```python
while items_bought_on_page:
    # Fresh scan each iteration
    shop_items = find_shop_items_with_stock(screen, targets)

    if shop_items:
        # Buy first item found
        target, rel_x, rel_y = shop_items[0]
        buy_item(target, rel_x, rel_y)
        items_bought_on_page = True  # Will re-scan
    else:
        items_bought_on_page = False  # Done with this page
```

**Why it's reliable:** Never clicks stale positions after layout changes.

### 4. Green Button Color Detection (Robust)

The bot finds buy buttons using HSV color detection with wide ranges:

```python
# Wide HSV range catches different green shades
lower_green1 = np.array([35, 50, 80])
upper_green1 = np.array([85, 255, 255])

# Multiple ranges combined for reliability
mask = cv2.bitwise_or(mask1, mask2)

# Aspect ratio > 1.3 filters out square seed icons
if aspect_ratio > 1.3 and aspect_ratio < 8.0:
    buttons.append((center_x, center_y))
```

- Multiple HSV ranges combined to catch button variations
- Aspect ratio filtering prevents clicking green seed icons (which are square)

**Why it's reliable:** Doesn't depend on exact pixel matching like templates.

## Previous Solutions (What Failed)

| Problem | Old Approach | New Approach |
|---------|--------------|--------------|
| **Stale positions** | Detected all items, then bought in order (positions became invalid after first purchase) | Re-scan page after each purchase |
| **Max attempts limit** | `for _ in range(20)` - stopped early or kept clicking grey buttons | Buy until button turns grey |
| **Cursor reset** | `pyautogui.click(x, y)` each time - slow, sometimes missed | `moveTo()` once, then `click()` repeatedly |
| **Narrow color range** | Missed buttons that were slightly different shade | Wide HSV range + multiple ranges combined |
| **Template matching** | Required exact image match, broke with UI changes | OCR reads text regardless of styling |
| **Config ignored** | Platform default overwrote config.json region | Fixed `_load()` to respect config values |
| **Seed icons clicked** | Green cactus/bamboo icons matched as "buttons" | Aspect ratio filter (buttons are wide rectangles) |

## Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Shop Cycle                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Teleport to shop (Shift+1)                              │
│  2. Open seed shop (Space)                                   │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                  Page Loop                              │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │                                                         │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │              Buy Loop (per page)                  │  │ │
│  │  ├──────────────────────────────────────────────────┤  │ │
│  │  │  1. OCR scan for items with STOCK               │  │ │
│  │  │  2. If found: click item → open accordion       │  │ │
│  │  │  3. Find green buy button (color detection)     │  │ │
│  │  │  4. Click until button turns grey               │  │ │
│  │  │  5. Re-scan page (positions shifted)            │  │ │
│  │  │  6. Repeat until no items with stock            │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                                                         │ │
│  │  Scroll down                                            │ │
│  │  Check for end marker (Moonbinder)                     │ │
│  │  If end: break. Else: continue page loop               │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  3. Restart shop cycle                                       │
└─────────────────────────────────────────────────────────────┘
```

## Key Files

| File | Purpose |
|------|---------|
| `src/auto_buyer.py` | Main bot logic, shop navigation, buy loops |
| `src/screen_capture.py` | OCR detection, color detection, template matching |
| `src/config.py` | Configuration loading and saving |
| `src/gui.py` | Tkinter GUI interface |
| `config.json` | User settings (region, targets, delays) |

## Debug Output

When debug mode is enabled, images are saved to `debug/`:

- `debug/screenshot.png` - Current screen capture
- `debug/green_mask.png` - HSV color mask showing detected green regions
- `debug/buttons_annotated.png` - Screenshot with detected buttons highlighted

These help diagnose issues with button detection or region setup.
