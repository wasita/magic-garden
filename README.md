# Magic Garden Auto-Buyer Bot

Automatically monitors and purchases seeds and eggs in the Magic Garden Discord game.

## Features

- **OCR-based detection** - Finds items by reading text (no fragile image templates)
- **Smart shop navigation** - Teleports to shop, scrolls through all pages, loops continuously
- **Green button detection** - Uses color detection to find buy buttons reliably
- **Fuzzy text matching** - Handles OCR errors like "arrot" → "Carrot"
- **Stock verification** - Only clicks items that show "STOCK" (ignores popups)
- **Configurable targets** - Choose which seeds/eggs to buy
- **Shop mode selection** - Scan seed shop, egg shop, or both
- **Cross-platform** - Works on macOS and Windows
- **GUI and headless modes** - Run with interface or AFK in terminal

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (recommended) or Python 3.10+
- Magic Garden game (Discord activity)
- **Windows only:** Tesseract OCR (see below)
- **Windows only:** pydirectinput (for game input - installed automatically)

### macOS Installation

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and setup
git clone <your-repo-url>
cd magic-garden
uv sync
```

### Windows Installation

#### Step 1: Install Tesseract OCR

1. Download the installer from: https://github.com/UB-Mannheim/tesseract/wiki
   - Get the latest 64-bit version (e.g., `tesseract-ocr-w64-setup-5.3.3.exe`)

2. Run the installer:
   - Install to default path: `C:\Program Files\Tesseract-OCR`
   - **Important:** Check "Add to PATH" during installation

3. Verify installation:
   ```cmd
   tesseract --version
   ```

4. If Tesseract is not in PATH, you'll need to set it manually. Add this to the top of `main.py`:
   ```python
   import pytesseract
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

#### Step 2: Install Python Dependencies

**Using uv (recommended):**
```powershell
# Install uv
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Clone and setup
git clone <your-repo-url>
cd magic-garden
uv sync
```

**Using pip:**
```cmd
cd magic-garden
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-windows.txt
```

## Configuration

Before running, set up your game region and preferences in `config.json`:

### Setting the Game Region

Run the region capture tool:
```bash
uv run python main.py --set-region
```

Follow the prompts to click the top-left and bottom-right corners of your game window.

### Config Options

Edit `config.json`:

```json
{
    "scan_interval": 1.0,
    "click_delay": 0.3,
    "confidence_threshold": 0.6,
    "shop_mode": "seed",
    "monitor_region": [799, 479, 882, 766],
    "ocr_targets": [
        "Mythical Egg",
        "Bamboo Seed",
        "Sunflower Seed",
        "Starweaver Pod",
        "Dawnbinder Pod",
        "Moonbinder Pod"
    ],
    "use_ocr": true,
    "startup_delay": 3
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `scan_interval` | Seconds between shop cycles | 1.0 |
| `click_delay` | Delay after each buy click (seconds) | 0.3 |
| `confidence_threshold` | Template match sensitivity (0-1) | 0.6 |
| `shop_mode` | Which shops to scan: `"seed"`, `"egg"`, or `"both"` | `"seed"` |
| `monitor_region` | Game window region `[x, y, width, height]` | - |
| `ocr_targets` | List of item names to buy | - |
| `use_ocr` | Use OCR text detection (recommended) | true |
| `startup_delay` | Seconds to wait before starting (focus game) | 3 |

## Usage

### Headless Mode (Recommended for AFK)

```bash
uv run python main.py --headless
```

The bot will:
1. Wait 3 seconds (focus your game window)
2. Press Shift+1 to teleport to shop
3. Press Space to open seed shop
4. Scroll through all pages, buying configured items
5. Loop back to step 2

Press `Ctrl+C` to stop.

### GUI Mode

```bash
uv run python main.py
```

Controls:
- **F6**: Start/Pause
- **F7**: Stop
- **Mouse to corner**: Emergency stop (pyautogui failsafe)

### Other Commands

```bash
# Set game region interactively
uv run python main.py --set-region
```

## Building Standalone Executable

You can package the bot as a standalone `.exe` that users can run without installing Python.

### Prerequisites for Building

1. Install PyInstaller:
   ```bash
   pip install pyinstaller
   ```

2. **Windows:** Ensure Tesseract is installed at `C:\Program Files\Tesseract-OCR`
   - The build will automatically bundle Tesseract into the executable

### Build

```bash
pyinstaller magic-garden.spec
```

The executable will be in the `dist/` folder as `MagicGardenBot.exe`.

### What Gets Bundled

- Python runtime
- All dependencies (OpenCV, pytesseract, EasyOCR, PyTorch)
- Tesseract OCR (Windows) - no separate install needed
- Default config and templates

**Notes:**
- Executable size is large (~500MB+) due to EasyOCR/PyTorch
- First run may be slow as EasyOCR downloads language models
- Users just double-click to run - no Python or Tesseract install required

### Creating a Release

GitHub Actions automatically builds and publishes releases when you push a version tag:

```bash
# Tag your commit with a version
git tag v1.0.0

# Push the tag to trigger the build
git push origin v1.0.0
```

This will:
1. Build `MagicGardenBot.exe` with all dependencies bundled
2. Create a GitHub Release with the executable attached

Users can download the `.exe` directly from the [Releases](../../releases) page.

## How It Works

1. **Shop Navigation** - Teleports to shop (Shift+1), opens seed/egg shop (Space)
2. **Screen Capture** - Captures the game region defined in config
3. **OCR Detection** - Uses pytesseract to read text on screen
4. **Stock Filter** - Only considers items with "STOCK" text on the same line
5. **Fuzzy Matching** - Matches partial text to handle OCR errors (e.g., "amboo" → "Bamboo")
6. **Click Item** - Clicks on the item to open the buy accordion
7. **Green Button Detection** - Finds buy buttons using HSV color matching
8. **Buy Loop** - Clicks buy button repeatedly until it turns grey (sold out)
9. **Re-scan Page** - After buying, re-scans the page for remaining items (handles layout shifts)
10. **Scroll & Repeat** - Scrolls down, continues scanning until end of shop, then loops

## Debugging

When debug mode is enabled, the bot saves diagnostic images to the `debug/` folder:
- `debug/screenshot.png` - Current screen capture
- `debug/green_mask.png` - HSV color mask showing detected green regions
- `debug/buttons_annotated.png` - Screenshot with detected buttons highlighted

These help diagnose issues with button detection or region setup.

## Troubleshooting

**Bot not detecting items:**
- Run `--set-region` to recapture game window bounds
- Check that `ocr_targets` in config.json matches exact item names
- Check debug output for OCR results and matched text

**Green buy button not detected:**
- Check `debug/green_mask.png` to see what green regions are detected
- The button must be wide (aspect ratio > 1.3) to avoid matching seed icons
- Ensure the game region covers the buy button area

**Clicking wrong things:**
- The bot filters for items with "STOCK" on the same line - popups shouldn't trigger
- If false positives persist, check the debug output for what text is being matched

**Tesseract not found (Windows):**
- Ensure Tesseract is installed and in PATH
- Or add the path manually in code (see Windows installation above)

**macOS permissions:**
- Grant accessibility permissions: System Settings > Privacy & Security > Accessibility
- Add Terminal (or your IDE) to the allowed apps

**Bot clicking but not buying:**
- Check `debug/buttons_annotated.png` to see if button is detected
- Increase `click_delay` in config.json if clicks are too fast
- Ensure the game window is focused and not obstructed

## Disclaimer

Use at your own risk. Automation may violate the game's terms of service.
