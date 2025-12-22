#!/usr/bin/env python3
"""
Magic Garden Auto-Buyer Bot

Automatically monitors for and purchases mythical eggs and seeds
in the Magic Garden game.

Usage:
    python main.py              - Start with GUI
    python main.py --headless   - Run without GUI (uses config.json settings)
    python main.py --dom        - Force DOM detection mode
    python main.py --discover   - Launch DOM selector discovery tool
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Magic Garden Auto-Buyer Bot")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--capture", type=str, help="Capture a template screenshot",
                        choices=["mythical_egg", "mythical_seed", "buy_button"])
    parser.add_argument("--capture-template", type=str, metavar="NAME",
                        help="Interactive template capture - click on item to capture (e.g., sunflower_seed)")
    parser.add_argument("--set-region", action="store_true",
                        help="Set game region by clicking two corners, saves to config.json")
    parser.add_argument("--dom", action="store_true",
                        help="Force DOM detection mode (requires Discord with --remote-debugging-port=9222)")
    parser.add_argument("--ocr", action="store_true",
                        help="Force OCR detection mode (default)")
    parser.add_argument("--discover", action="store_true",
                        help="Launch interactive DOM selector discovery tool")
    parser.add_argument("--cdp-port", type=int, default=9222,
                        help="Chrome DevTools Protocol port (default: 9222)")
    args = parser.parse_args()

    # Handle --discover flag first (doesn't need other setup)
    if args.discover:
        print("=== DOM Selector Discovery Tool ===")
        print(f"Connecting to Discord on CDP port {args.cdp_port}...")
        print()
        print("Make sure Discord is running with:")
        print(f"  discord --remote-debugging-port={args.cdp_port}")
        print()
        try:
            from src.dom_capture import discover_selectors
            discover_selectors(args.cdp_port)
        except ImportError as e:
            print(f"Error: {e}")
            print("Install playwright with: pip install playwright && playwright install chromium")
            sys.exit(1)
        return

    if args.set_region:
        # Set game region interactively
        import pyautogui
        import json
        import time

        print("=== Set Game Region ===")
        print("1. Press ENTER, then you have 3 seconds to move mouse to TOP-LEFT corner")
        print("2. Press ENTER again, then 3 seconds to move mouse to BOTTOM-RIGHT corner")
        print()

        input("Press ENTER, then move mouse to TOP-LEFT corner...")
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        pos1 = pyautogui.position()
        print(f"Got top-left: ({pos1.x}, {pos1.y})")

        input("Press ENTER, then move mouse to BOTTOM-RIGHT corner...")
        for i in range(3, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        pos2 = pyautogui.position()
        print(f"Got bottom-right: ({pos2.x}, {pos2.y})")

        # Calculate region
        left = min(pos1.x, pos2.x)
        top = min(pos1.y, pos2.y)
        width = abs(pos2.x - pos1.x)
        height = abs(pos2.y - pos1.y)

        region = [int(left), int(top), int(width), int(height)]
        print(f"\nRegion: {region}")

        # Update config.json
        with open("config.json", "r") as f:
            config = json.load(f)
        config["monitor_region"] = region
        with open("config.json", "w") as f:
            json.dump(config, f, indent=4)
        print(f"Saved to config.json!")
        return

    if args.capture_template:
        # Interactive template capture - click to capture region around mouse
        import pyautogui
        from pynput import mouse
        from PIL import Image

        template_name = args.capture_template
        print(f"=== Template Capture: {template_name} ===")
        print("Click on the CENTER of the item you want to capture.")
        print("A 60x60 region around your click will be saved.")
        print("Press Ctrl+C to cancel.\n")

        click_pos = None

        def on_click(x, y, button, pressed):
            nonlocal click_pos
            if pressed:
                click_pos = (int(x), int(y))
                return False

        listener = mouse.Listener(on_click=on_click)
        listener.start()
        listener.join()

        if click_pos:
            x, y = click_pos
            # Capture 60x60 region centered on click
            size = 60
            region = (x - size//2, y - size//2, size, size)
            screenshot = pyautogui.screenshot(region=region)

            path = f"templates/{template_name}.png"
            screenshot.save(path)
            print(f"Saved {size}x{size} template to: {path}")
            print(f"Captured at click position: ({x}, {y})")
        return

    if args.capture:
        # Quick template capture mode
        from src.screen_capture import ScreenCapture
        import time
        print(f"Capturing '{args.capture}' template in 3 seconds...")
        print("Position your screen so the item is visible!")
        time.sleep(3)
        ScreenCapture.save_screenshot(f"templates/{args.capture}.png")
        print("Done! You may need to crop the image to just the item.")
        return

    if args.headless:
        # Headless mode
        from src.config import Config
        from src.auto_buyer import AutoBuyer
        import time
        import signal

        config = Config()

        # Override detection mode from CLI flags
        if args.dom:
            config.set("detection_mode", "dom")
            config.set("discord", {"remote_debugging_port": args.cdp_port, "game_frame_selector": "iframe"})
            print(f"Using DOM detection mode (CDP port: {args.cdp_port})")
        elif args.ocr:
            config.set("detection_mode", "ocr")
            print("Using OCR detection mode")

        buyer = AutoBuyer(config)

        def signal_handler(sig, frame):
            print("\nStopping...")
            buyer.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # Only load templates if using OCR mode
        if config.get("detection_mode", "ocr") == "ocr":
            if not buyer.load_templates():
                print("Warning: Could not load some templates. OCR mode may still work.")

        detection_mode = config.get("detection_mode", "ocr")
        print(f"Starting auto-buyer in headless mode (detection: {detection_mode})...")
        print("Press Ctrl+C to stop")
        buyer.start()

        try:
            while buyer.running:
                time.sleep(1)
        except KeyboardInterrupt:
            buyer.stop()
    else:
        # GUI mode
        from src.gui import BotGUI
        app = BotGUI()
        app.run()


if __name__ == "__main__":
    main()
