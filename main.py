#!/usr/bin/env python3
"""
Magic Garden Auto-Buyer Bot

Automatically monitors for and purchases mythical eggs and seeds
in the Magic Garden game.

Usage:
    python main.py           - Start with GUI
    python main.py --headless - Run without GUI (uses config.json settings)
"""

import sys
import argparse


def main():
    parser = argparse.ArgumentParser(description="Magic Garden Auto-Buyer Bot")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--capture", type=str, help="Capture a template screenshot",
                        choices=["mythical_egg", "mythical_seed", "buy_button"])
    args = parser.parse_args()

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
        buyer = AutoBuyer(config)

        def signal_handler(sig, frame):
            print("\nStopping...")
            buyer.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        if not buyer.load_templates():
            print("Error: Could not load templates. Create them first with:")
            print("  python main.py --capture mythical_egg")
            print("  python main.py --capture mythical_seed")
            print("  python main.py --capture buy_button")
            sys.exit(1)

        print("Starting auto-buyer in headless mode...")
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
