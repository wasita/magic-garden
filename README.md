# magic garden auto-buyer bot

Automatically monitors and purchases mythical eggs and seeds in the Magic Garden game.

## Features

- Screen monitoring with image recognition
- Auto-purchase when mythical items detected
- Cross-platform (Windows & macOS)
- GUI with activity logging
- Hotkey controls (F6 to start/pause, F7 to stop)
- Configurable scan intervals and confidence thresholds

## Setup

### Prerequisites

- Python 3.8 or higher
- Magic Garden game installed

### Installation

#### macOS

```bash
# Install Python if needed (via Homebrew)
brew install python

# Clone and setup
cd magic-garden
python3 -m pip install -r requirements.txt
```

#### Windows

```bash
# Download Python from python.org if needed

# Clone and setup
cd magic-garden
pip install -r requirements.txt
```

### Creating Templates

Before the bot can detect items, you need to capture template images:

1. Open Magic Garden and navigate to where mythical eggs/seeds appear
2. Run the template capture tool:

```bash
# Capture mythical egg template
python main.py --capture mythical_egg

# Capture mythical seed template
python main.py --capture mythical_seed

# Capture buy button template
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
python main.py
```

Controls:

- **F6**: Start/Pause
- **F7**: Stop
- **Mouse to corner**: Emergency stop

### Headless Mode (AFK)

```bash
python main.py --headless
```

Press Ctrl+C to stop.

## Configuration

Edit `config.json` to customize:

```json
{
    "scan_interval": 0.5,      // Seconds between scans
    "click_delay": 0.1,        // Delay after clicks
    "confidence_threshold": 0.8, // Match sensitivity (0-1)
    "auto_buy": true           // Auto-purchase when detected
}
```

## Troubleshooting

**Bot not detecting items:**

- Recapture templates at current game resolution
- Lower `confidence_threshold` in config.json
- Ensure game window is visible (not minimized)

**Clicks not registering:**

- Increase `click_delay` in config.json
- Check that game window is focused

**macOS permissions:**

- Grant accessibility permissions to Terminal/Python in System Preferences > Security & Privacy > Privacy > Accessibility
