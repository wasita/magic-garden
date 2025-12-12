import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from typing import Optional
from pynput import keyboard
from .auto_buyer import AutoBuyer
from .config import Config

class BotGUI:
    def __init__(self):
        self.config = Config()
        self.buyer = AutoBuyer(self.config)
        self.root: Optional[tk.Tk] = None
        self.keyboard_listener: Optional[keyboard.Listener] = None

        # GUI elements
        self.status_label: Optional[tk.Label] = None
        self.log_text: Optional[tk.Text] = None
        self.stats_labels = {}

    def run(self):
        """Start the GUI."""
        self.root = tk.Tk()
        self.root.title("Magic Garden Auto-Buyer")
        self.root.geometry("500x400")
        self.root.resizable(True, True)

        self._create_widgets()
        self._setup_callbacks()
        self._setup_hotkeys()
        self._load_templates()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()

    def _create_widgets(self):
        """Create all GUI widgets."""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="5")
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = ttk.Label(status_frame, text="Stopped", font=("TkDefaultFont", 12, "bold"))
        self.status_label.pack()

        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_btn = ttk.Button(button_frame, text="Start (F6)", command=self._toggle_bot)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))

        self.stop_btn = ttk.Button(button_frame, text="Stop (F7)", command=self._stop_bot)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="Capture Template", command=self._capture_template).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(button_frame, text="Set Region", command=self._set_region).pack(side=tk.LEFT)

        # Stats section
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding="5")
        stats_frame.pack(fill=tk.X, pady=(0, 10))

        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack()

        labels = [("Items Detected:", "detected"), ("Items Purchased:", "purchased")]
        for i, (label, key) in enumerate(labels):
            ttk.Label(stats_grid, text=label).grid(row=i, column=0, sticky=tk.W, padx=(0, 10))
            self.stats_labels[key] = ttk.Label(stats_grid, text="0")
            self.stats_labels[key].grid(row=i, column=1, sticky=tk.W)

        # Log section
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Hotkey info
        info_label = ttk.Label(main_frame, text="Hotkeys: F6 = Start/Pause | F7 = Stop | Move mouse to corner = Emergency stop")
        info_label.pack(pady=(10, 0))

    def _setup_callbacks(self):
        """Setup callbacks for the auto-buyer."""
        self.buyer.on_status_change = self._on_log_message
        self.buyer.on_detection = self._on_item_detected
        self.buyer.on_purchase = self._on_item_purchased

    def _setup_hotkeys(self):
        """Setup global hotkeys."""
        def on_press(key):
            try:
                if key == keyboard.Key.f6:
                    self.root.after(0, self._toggle_bot)
                elif key == keyboard.Key.f7:
                    self.root.after(0, self._stop_bot)
            except Exception:
                pass

        self.keyboard_listener = keyboard.Listener(on_press=on_press)
        self.keyboard_listener.start()

    def _load_templates(self):
        """Load template images."""
        if self.buyer.load_templates():
            self._log("Templates loaded successfully")
        else:
            self._log("Warning: Some templates could not be loaded")
            self._log("Use 'Capture Template' to create them")

    def _toggle_bot(self):
        """Start or pause the bot."""
        if not self.buyer.running:
            self.buyer.start()
            self.status_label.config(text="Running")
            self.start_btn.config(text="Pause (F6)")
        else:
            self.buyer.toggle_pause()
            if self.buyer.paused:
                self.status_label.config(text="Paused")
                self.start_btn.config(text="Resume (F6)")
            else:
                self.status_label.config(text="Running")
                self.start_btn.config(text="Pause (F6)")

    def _stop_bot(self):
        """Stop the bot."""
        self.buyer.stop()
        self.status_label.config(text="Stopped")
        self.start_btn.config(text="Start (F6)")

    def _set_region(self):
        """Set the monitor region by clicking two corners."""
        import pyautogui

        self._log("Click TOP-LEFT corner of game window in 3s...")

        def capture_region():
            import time
            time.sleep(3)

            # Get first corner
            x1, y1 = pyautogui.position()
            self._log(f"Got top-left: ({x1}, {y1})")
            self._log("Now click BOTTOM-RIGHT corner in 3s...")

            time.sleep(3)

            # Get second corner
            x2, y2 = pyautogui.position()
            self._log(f"Got bottom-right: ({x2}, {y2})")

            # Calculate region (x, y, width, height)
            region = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
            self._log(f"Region set: {region}")

            # Save to config
            self.config.set("monitor_region", region)
            self.config.save()
            self._log("Region saved to config.json!")

        threading.Thread(target=capture_region, daemon=True).start()

    def _capture_template(self):
        """Capture a template screenshot."""
        templates = ["mythical_egg", "mythical_seed", "buy_button"]

        dialog = tk.Toplevel(self.root)
        dialog.title("Capture Template")
        dialog.geometry("300x200")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Select template to capture:").pack(pady=10)

        selected = tk.StringVar(value=templates[0])
        for template in templates:
            ttk.Radiobutton(dialog, text=template, value=template, variable=selected).pack(anchor=tk.W, padx=20)

        def capture():
            template_name = selected.get()
            dialog.destroy()
            self._log(f"Move to {template_name} and press Enter...")

            # Wait for user to position
            def do_capture():
                import time
                time.sleep(3)  # Give user time to position
                from .screen_capture import ScreenCapture

                path = f"templates/{template_name}.png"
                ScreenCapture.save_screenshot(path)
                self._log(f"Saved template to {path}")
                self.buyer.screen.load_template(template_name, path)

            threading.Thread(target=do_capture, daemon=True).start()

        ttk.Button(dialog, text="Capture (3s delay)", command=capture).pack(pady=20)

    def _on_log_message(self, message: str):
        """Handle log message callback."""
        self.root.after(0, lambda: self._log(message))

    def _on_item_detected(self, item_type: str, position: tuple):
        """Handle item detection callback."""
        stats = self.buyer.get_stats()
        self.root.after(0, lambda: self.stats_labels["detected"].config(text=str(stats["items_detected"])))

    def _on_item_purchased(self, item_type: str):
        """Handle item purchase callback."""
        stats = self.buyer.get_stats()
        self.root.after(0, lambda: self.stats_labels["purchased"].config(text=str(stats["items_purchased"])))

    def _log(self, message: str):
        """Add message to log."""
        if self.log_text:
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

    def _on_close(self):
        """Handle window close."""
        self.buyer.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.root.destroy()
