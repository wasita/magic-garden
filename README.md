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
    "monitor_region": [271, 87, 645, 534],
    "ocr_targets": [
        "Mythical Egg",
        "Sunflower Seed",
        "Bamboo Seed",
        "Cactus Seed",
        "Carrot Seed",
        "Dawnbinder Pod",
        "Moonbinder Pod",
        "Starweaver Pod"
    ],
    "max_buy_attempts": 20
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `scan_interval` | Seconds between shop cycles | 1.0 |
| `click_delay` | Delay after clicking (seconds) | 0.3 |
| `confidence_threshold` | Template match sensitivity (0-1) | 0.6 |
| `shop_mode` | Which shops to scan: `"seed"`, `"egg"`, or `"both"` | `"seed"` |
| `monitor_region` | Game window region `[x, y, width, height]` | - |
| `ocr_targets` | List of item names to buy | - |
| `max_buy_attempts` | Max clicks per item before moving on | 20 |
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

# Capture a template image (click on item)
uv run python main.py --capture-template sunflower_seed
```

## Building Standalone Executable

You can package the bot as a standalone executable:

### Install PyInstaller

```bash
pip install pyinstaller
```

### Build

```bash
# Using the spec file (recommended)
pyinstaller magic-garden.spec

# Or simple one-liner
pyinstaller --onefile --console main.py
```

The executable will be in the `dist/` folder.

**Notes:**
- Executable size is large (~500MB+) due to EasyOCR/PyTorch
- Windows users still need Tesseract OCR installed separately
- First run may be slow as EasyOCR downloads language models

## How It Works

1. **Screen Capture** - Captures the game region defined in config
2. **OCR Detection** - Uses pytesseract to read text on screen
3. **Stock Filter** - Only considers items with "STOCK" text nearby
4. **Fuzzy Matching** - Matches partial text (e.g., "arrot" → "Carrot Seed")
5. **Click Item** - Clicks on the item to open the buy accordion
6. **Color Detection** - Finds green buy buttons using HSV color matching
7. **Buy Loop** - Keeps clicking buy until button disappears (sold out)
8. **Scroll & Repeat** - Scrolls down, continues scanning, loops forever

## Troubleshooting

**Bot not detecting items:**
- Run `--set-region` to recapture game window bounds
- Check that `ocr_targets` in config.json matches exact item names
- Try running with debug output (first page shows OCR results)

**Clicking wrong things:**
- The bot filters for items with "STOCK" nearby - popups shouldn't trigger
- If false positives persist, check the debug output for what's being matched

**Tesseract not found (Windows):**
- Ensure Tesseract is installed and in PATH
- Or add the path manually in code (see Windows installation above)

**macOS permissions:**
- Grant accessibility permissions: System Settings > Privacy & Security > Accessibility
- Add Terminal (or your IDE) to the allowed apps

**Bot clicking but not buying:**
- Increase `click_delay` in config.json
- Check that the game window is focused and not obstructed

## Disclaimer

Use at your own risk. Automation may violate the game's terms of service.
