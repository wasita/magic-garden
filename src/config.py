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
    "detection_mode": "ocr",  # "ocr" or "dom"
    "scan_interval": 0.5,
    "click_delay": 0.1,
    "confidence_threshold": 0.8,
    "monitor_region": MONITOR_REGIONS.get(platform.system()),
    "templates": {
        "mythical_egg": "templates/mythical_egg.png",
        "mythical_seed": "templates/mythical_seed.png",
        "buy_button": "templates/buy_button.png"
    },
    "hotkeys": {
        "toggle": "f6",
        "stop": "f7"
    },
    "sound_alert": True,
    "auto_buy": True,
    # DOM detection settings
    "discord": {
        "remote_debugging_port": 9222,
        "game_frame_selector": "iframe"
    },
    "dom_selectors": {
        "shop": {
            "container": ".shop-container",
            "item_row": ".shop-item",
            "item_name": ".item-name",
            "stock_indicator": ".stock",
            "no_stock_class": "out-of-stock"
        },
        "buttons": {
            "buy": ".buy-button",
            "close": ".close-button",
            "open_seed_shop": "[data-action='open-seed-shop']",
            "open_egg_shop": "[data-action='open-egg-shop']"
        }
    },
    "dom_targets": [],
    "fallback": {
        "use_ocr_if_dom_fails": True
    }
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
                    merged = self._deep_merge(DEFAULT_CONFIG.copy(), loaded)

                    # Use platform-specific monitor_region only if not set in config
                    if "monitor_region" not in loaded or loaded["monitor_region"] is None:
                        merged["monitor_region"] = MONITOR_REGIONS.get(platform.system())
                        print(f"Using {platform.system()} default monitor region: {merged['monitor_region']}")
                    else:
                        print(f"Using config monitor region: {merged['monitor_region']}")

                    return merged
            except json.JSONDecodeError:
                print(f"Warning: Invalid config file, using defaults")
                return DEFAULT_CONFIG.copy()
        print(f"Using {platform.system()} monitor region: {DEFAULT_CONFIG['monitor_region']}")
        return DEFAULT_CONFIG.copy()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.data, f, indent=4)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()
