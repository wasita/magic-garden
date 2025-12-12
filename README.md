# magic garden auto-buyer bot

Automatically monitors and purchases seeds in the Magic Garden game.

## Features

- Screen monitoring with image recognition
- Auto-purchase when mythical items detected
- Cross-platform (Windows & macOS)
- GUI with activity logging
- Hotkey controls (F6 to start/pause, F7 to stop)
- Configurable scan intervals and confidence thresholds

## Setup

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (recommended) or Python 3.10+
- Magic Garden game installed

### Installation with uv (Recommended)

uv automatically manages Python versions and dependencies.

#### Install uv

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### Clone and Setup

```bash
git clone <your-repo-url>
cd magic-garden
uv sync
```

This will:

- Install the correct Python version (3.10)
- Create a virtual environment in `.venv/`
- Install all dependencies from the lock file

### Alternative: Manual pip Installation

If you prefer not to use uv:

```bash
cd magic-garden
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

## Creating Templates

Before the bot can detect items, you need to capture template images:

1. Open Magic Garden and navigate to where mythical eggs/seeds appear
2. Run the template capture tool:

```bash
# With uv
uv run python main.py --capture mythical_egg
uv run python main.py --capture mythical_seed
uv run python main.py --capture buy_button

# Without uv (venv activated)
python main.py --capture mythical_egg
python main.py --capture mythical_seed
python main.py --capture buy_button
```

3. After capture, crop the images in `templates/` folder to show ONLY the item (remove background). Use any image editor.

**Tips for good templates:**

- Crop tightly around the item
- Avoid including variable elements (prices, quantities)
- Use consistent game window size when capturing and running

## Usage

### GUI Mode (Recommended)

```bash
# With uv
uv run python main.py

# Without uv (venv activated)
python main.py
```

Controls:

- **F6**: Start/Pause
- **F7**: Stop
- **Mouse to corner**: Emergency stop

### Headless Mode (AFK)

```bash
# With uv
uv run python main.py --headless

# Without uv (venv activated)
python main.py --headless
```

Press Ctrl+C to stop.

## Configuration

Edit `config.json` to customize:

```json
{
    "scan_interval": 0.5,
    "click_delay": 0.1,
    "confidence_threshold": 0.8,
    "auto_buy": true
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `scan_interval` | Seconds between screen scans | 0.5 |
| `click_delay` | Delay after clicking (seconds) | 0.1 |
| `confidence_threshold` | Image match sensitivity (0-1) | 0.8 |
| `auto_buy` | Automatically purchase when detected | true |

## Troubleshooting

**Bot not detecting items:**

- Recapture templates at current game resolution
- Lower `confidence_threshold` in config.json
- Ensure game window is visible (not minimized)

**Clicks not registering:**

- Increase `click_delay` in config.json
- Check that game window is focused

**macOS permissions:**

- Grant accessibility permissions in System Settings > Privacy & Security > Accessibility
- Add Terminal (or your IDE) to the allowed apps

**Windows permissions:**

- Run as Administrator if clicks aren't registering
- Disable "UI Access" protection in some games

## Disclaimer

Use at your own risk. Automation may violate the game's terms of service.
