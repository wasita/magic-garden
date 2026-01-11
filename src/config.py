import json
import os
import platform
from pathlib import Path

# Platform-specific monitor regions
MONITOR_REGIONS = {
    "Darwin": [271, 87, 645, 534],   # macOS
    "Windows": [402, 57, 1638, 1053], # Windows
}

DEFAULT_CONFIG = {
    "scan_interval": 0.5,
    "click_delay": 0.1,
    "confidence_threshold": 0.8,
    "monitor_region": MONITOR_REGIONS.get(platform.system()),
    "templates": {
        "mythical_egg": "templates/mythical_egg.png",
        "buy_button": "templates/buy_button.png"
    },
    "hotkeys": {
        "toggle": "f6",
        "stop": "f7"
    },
    "sound_alert": True,
    "auto_buy": True
}

class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.data = self._load()

    def _load(self) -> dict:
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    loaded = json.load(f)
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(loaded)
                    # Use config.json region if set, otherwise use platform default
                    if "monitor_region" in loaded and loaded["monitor_region"]:
                        print(f"Using config.json monitor region: {merged['monitor_region']}")
                    else:
                        merged["monitor_region"] = MONITOR_REGIONS.get(platform.system())
                        print(f"Using {platform.system()} default monitor region: {merged['monitor_region']}")
                    return merged
            except json.JSONDecodeError:
                print(f"Warning: Invalid config file, using defaults")
                return DEFAULT_CONFIG.copy()
        print(f"Using {platform.system()} default monitor region: {DEFAULT_CONFIG['monitor_region']}")
        return DEFAULT_CONFIG.copy()

    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()
