import os
import shutil
import tkinter as tk
from tkinter import ttk, messagebox

class CCleanerMVP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CCleaner MVP - Disk Cleaner")
        self.geometry("550x450")
        self.resizable(False, False)

        # Define targets to clean (Safe, standard user temp & cache locations)
        user_profile = os.environ.get("USERPROFILE", "")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        
        self.targets = {
            "Windows Temp Files": [
                os.environ.get("TEMP", ""),
                r"C:\Windows\Temp"
            ],
            "Google Chrome Cache": [
                os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Cache")
            ],
            "Mozilla Firefox Cache": [
                os.path.join(local_appdata, r"Mozilla\Firefox\Profiles")
            ],
            "Recycle Bin / User Temp": [
                os.path.join(local_appdata, "Temp")
            ]
        }

        self.scanned_results = {}
        self.setup_ui()

    def setup_ui(self):
        # Header
        header = tk.Label(self, text="System & Cache Cleaner (MVP)", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Targets Frame
        self.tree = ttk.Treeview(self, columns=("Category", "Size"), show="headings", height=8)
        self.tree.heading("Category", text="Category")
        self.tree.heading("Size", text="Calculated Size")
        self.tree.column("Category", width=350)
        self.tree.column("Size", width=150, anchor="e")
        self.tree.pack(padx=20, pady=10, fill="x")

        # Status Label
        self.status_label = tk.Label(self, text="Click 'Analyze' to scan for junk files.", font=("Arial", 10))
        self.status_label.pack(pady=10)

        # Progress Bar
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(padx=20, fill="x", pady=5)

        # Buttons Frame
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=15)

        self.analyze_btn = tk.Button(btn_frame, text="1. Analyze", command=self.analyze, width=12, bg="#e1e1e1")
        self.analyze_btn.pack(side="left", padx=10)

        self.clean_btn = tk.Button(btn_frame, text="2. Run Cleaner", command=self.clean, width=12, bg="#4CAF50", fg="white", state="disabled")
        self.clean_btn.pack(side="left", padx=10)

    def get_dir_size(self, path):
        """Calculates total size of files in a directory safely."""
        total_size = 0
        if not os.path.exists(path):
            return 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    if os.path.exists(fp):
                        try:
                            total_size += os.path.getsize(fp)
                        except (PermissionError, FileNotFoundError):
                            continue
        except Exception:
            pass
        return total_size

    def format_size(self, size_bytes):
        """Formats byte count into readable MB/GB units."""
        if size_bytes == 0:
            return "0 MB"
        size_mb = size_bytes / (1024 * 1024)
        if size_mb >= 1024:
            return f"{size_mb / 1024:.2f} GB"
        return f"{size_mb:.2f} MB"

    def analyze(self):
        """Scans defined targets and reports total recoverable space."""
        self.tree.delete(*self.tree.get_children())
        self.scanned_results.clear()
        total_junk = 0

        self.status_label.config(text="Analyzing files...")
        self.update_idletasks()

        for category, paths in self.targets.items():
            cat_size = 0
            for path in paths:
                cat_size += self.get_dir_size(path)
            self.scanned_results[category] = cat_size
            total_junk += cat_size
            self.tree.insert("", "end", values=(category, self.format_size(cat_size)))

        if total_junk > 0:
            self.status_label.config(text=f"Analysis Complete: {self.format_size(total_junk)} can be freed.")
            self.clean_btn.config(state="normal")
        else:
            self.status_label.config(text="System is clean. No junk files found.")
            self.clean_btn.config(state="disabled")

    def clean(self):
        """Executes file deletion on targeted temporary locations."""
        if not messagebox.askyesno("Confirm Deletion", "Are you sure you want to permanently delete these temporary files?"):
            return

        self.status_label.config(text="Cleaning files...")
        cleaned_size = 0

        for category, paths in self.targets.items():
            for path in paths:
                if not os.path.exists(path):
                    continue
                for root, dirs, files in os.walk(path):
                    for f in files:
                        file_path = os.path.join(root, f)
                        try:
                            size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_size += size
                        except Exception:
                            # Skip locked or system-restricted files safely
                            continue

        messagebox.showinfo("Success", f"Cleaning Complete!\nFreed {self.format_size(cleaned_size)} of disk space.")
        self.analyze()  # Re-scan to update UI

if __name__ == "__main__":
    app = CCleanerMVP()
    app.mainloop()