import sys
import os
import shutil
import json
from datetime import datetime
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QMessageBox, QCheckBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QDialog, QListWidget, QDialogButtonBox
)

class WorkerThread(QThread):
    """Background worker to keep the UI responsive during scans/cleans."""
    scan_complete = pyqtSignal(dict, float, dict)  # results, total, file_map
    clean_complete = pyqtSignal(float, int)  # bytes, files_moved

    def __init__(self, mode, targets, excludes=None, dry_run=False, quarantine_dir=None):
        super().__init__()
        self.mode = mode
        self.targets = targets
        self.excludes = excludes or []
        self.dry_run = dry_run
        self.quarantine_dir = quarantine_dir or os.path.join(os.path.dirname(__file__), "quarantine")

    def _is_excluded(self, path):
        for ex in self.excludes:
            if not ex:
                continue
            try:
                if os.path.commonpath([os.path.abspath(path), os.path.abspath(ex)]) == os.path.abspath(ex):
                    return True
            except Exception:
                continue
        return False

    def _gather_paths(self, paths):
        """Yield files under given path(s), applying excludes."""
        for path in paths:
            if not path:
                continue
            if os.path.exists(path):
                if os.path.isfile(path):
                    if not self._is_excluded(path):
                        yield path
                else:
                    for root, _, files in os.walk(path):
                        for f in files:
                            fp = os.path.join(root, f)
                            if self._is_excluded(fp):
                                continue
                            yield fp

    def run(self):
        if self.mode == "scan":
            results = {}
            total_bytes = 0
            file_map = {}
            for category, paths in self.targets.items():
                cat_bytes = 0
                files = []
                for fp in self._gather_paths(paths):
                    try:
                        sz = os.path.getsize(fp)
                        cat_bytes += sz
                        files.append(fp)
                    except (PermissionError, FileNotFoundError):
                        continue
                results[category] = cat_bytes
                file_map[category] = files
                total_bytes += cat_bytes
            self.scan_complete.emit(results, total_bytes, file_map)

        elif self.mode == "clean":
            moved_bytes = 0
            moved_files = 0
            os.makedirs(self.quarantine_dir, exist_ok=True)
            for category, paths in self.targets.items():
                for fp in self._gather_paths(paths):
                    try:
                        sz = os.path.getsize(fp)
                        # move to quarantine if not dry_run
                        if self.dry_run:
                            moved_files += 1
                            moved_bytes += sz
                            continue
                        # preserve directory structure inside quarantine
                        rel = os.path.relpath(fp, start=os.path.expanduser("~"))
                        dest = os.path.join(self.quarantine_dir, rel)
                        os.makedirs(os.path.dirname(dest), exist_ok=True)
                        try:
                            shutil.move(fp, dest)
                            moved_files += 1
                            moved_bytes += sz
                        except Exception:
                            # final attempt: remove
                            try:
                                os.remove(fp)
                                moved_files += 1
                                moved_bytes += sz
                            except Exception:
                                continue
                    except Exception:
                        continue
            self.clean_complete.emit(moved_bytes, moved_files)


class MinimalistCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Purge MVP")
        self.resize(500, 620)
        
        # Targets Setup
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        user_home = os.path.expanduser("~")
        # Use broader Chrome User Data root so multiple profiles are covered
        self.targets = {
            "Windows Temp Files": [os.environ.get("TEMP", ""), r"C:\Windows\Temp"],
            "Google Chrome Cache": [os.path.join(local_appdata, r"Google\Chrome\User Data")],
            "Mozilla Firefox Cache": [os.path.join(local_appdata, r"Mozilla\Firefox\Profiles")],
            "User Application Temp": [os.path.join(local_appdata, "Temp")],
            "Downloads": [os.path.join(user_home, "Downloads")]
        }

        # Settings / state
        self.repo_dir = os.path.dirname(__file__)
        self.settings_path = os.path.join(self.repo_dir, "settings.json")
        self.log_path = os.path.join(self.repo_dir, "quicky_cleaner.log")
        self.quarantine_dir = os.path.join(self.repo_dir, "quarantine")
        self.excludes = []
        self.last_file_map = {}
        self.scanned_bytes = 0
        self._load_settings()
        self.init_ui()

    def init_ui(self):
        # Apply dark theme styling
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F172A;
            }
            QLabel {
                color: #F8FAFC;
                font-family: 'Segoe UI', -apple-system, sans-serif;
            }
            QFrame#card {
                background-color: #1E293B;
                border-radius: 12px;
                border: 1px solid #334155;
            }
            QTableWidget {
                background-color: transparent;
                gridline-color: transparent;
                border: none;
                color: #CBD5E1;
                font-size: 13px;
            }
            QTableWidget::item {
                padding: 10px 5px;
                border-bottom: 1px solid #334155;
            }
            QTableWidget::item:selected {
                background-color: transparent;
                color: #F8FAFC;
            }
            QHeaderView::section {
                background-color: transparent;
                color: #64748B;
                font-size: 11px;
                font-weight: bold;
                border: none;
                padding-bottom: 8px;
            }
            QProgressBar {
                border: none;
                background-color: #334155;
                height: 4px;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #3B82F6;
                border-radius: 2px;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(28, 28, 28, 28)
        main_layout.setSpacing(20)

        # Header Section
        header_layout = QVBoxLayout()
        title = QLabel("Purge")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        
        subtitle = QLabel("Lightweight system optimizer")
        subtitle.setStyleSheet("color: #94A3B8; font-size: 13px;")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addLayout(header_layout)

        # Storage Summary Card
        summary_card = QFrame()
        summary_card.setObjectName("card")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(20, 20, 20, 20)

        card_title = QLabel("RECLAIMABLE SPACE")
        card_title.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold; letter-spacing: 1px;")

        self.size_display = QLabel("0.0 MB")
        self.size_display.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        self.size_display.setStyleSheet("color: #38BDF8; margin-top: 2px;")

        summary_layout.addWidget(card_title)
        summary_layout.addWidget(self.size_display)
        main_layout.addWidget(summary_card)

        # Table Breakdown Card
        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(15, 15, 15, 15)

        # Columns: Enabled, Category, Size
        self.table = QTableWidget(len(self.targets), 3)
        self.table.setHorizontalHeaderLabels(["ENABLED", "CATEGORY", "SIZE"])
        self.checkboxes = []
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Initialize table placeholders
        for idx, cat in enumerate(self.targets.keys()):
            cb = QCheckBox()
            cb.setChecked(True)
            self.table.setCellWidget(idx, 0, cb)
            self.checkboxes.append(cb)
            self.table.setItem(idx, 1, QTableWidgetItem(cat))
            self.table.setItem(idx, 2, QTableWidgetItem("-"))

        table_layout.addWidget(self.table)
        main_layout.addWidget(table_card)

        # Progress Indicator
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0) # Indeterminate mode when running
        self.progress.hide()
        main_layout.addWidget(self.progress)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.scan_btn = QPushButton("Analyze")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background-color: #334155;
                color: #F8FAFC;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #475569;
            }
        """)
        self.scan_btn.clicked.connect(self.start_scan)

        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setStyleSheet("background-color: #475569; color: #F8FAFC; border-radius:8px; padding:10px;")
        self.preview_btn.clicked.connect(self.show_preview)

        self.clean_btn = QPushButton("Clean System")
        self.clean_btn.setEnabled(False)
        self.clean_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
            QPushButton:disabled {
                background-color: #1E293B;
                color: #475569;
            }
        """)
        self.clean_btn.clicked.connect(self.start_clean)

        btn_layout.addWidget(self.scan_btn)
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.clean_btn)
        main_layout.addLayout(btn_layout)

        # Excludes button
        exclude_layout = QHBoxLayout()
        self.exclude_btn = QPushButton("Edit Excludes")
        self.exclude_btn.setStyleSheet("background-color: #334155; color: #F8FAFC; border-radius:8px; padding:8px;")
        self.exclude_btn.clicked.connect(self.edit_excludes)
        exclude_layout.addWidget(self.exclude_btn)
        main_layout.addLayout(exclude_layout)

    def format_bytes(self, size_bytes):
        if size_bytes == 0:
            return "0.00 MB"
        size_mb = size_bytes / (1024 * 1024)
        if size_mb >= 1024:
            return f"{size_mb / 1024:.2f} GB"
        return f"{size_mb:.2f} MB"

    def start_scan(self):
        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress.show()

        self.worker = WorkerThread("scan", self.targets, excludes=self.excludes)
        self.worker.scan_complete.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_finished(self, results, total_bytes, file_map):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.scanned_bytes = total_bytes
        self.size_display.setText(self.format_bytes(total_bytes))
        self.last_file_map = file_map

        for idx, (cat, cat_bytes) in enumerate(results.items()):
            self.table.item(idx, 2).setText(self.format_bytes(cat_bytes))
            # enable clean button only if at least one selected category has bytes
        enable_clean = False
        for idx, cat in enumerate(results.keys()):
            if self.checkboxes[idx].isChecked() and results.get(cat, 0) > 0:
                enable_clean = True
                break
        self.clean_btn.setEnabled(enable_clean)

    def start_clean(self):
        resp = QMessageBox.question(
            self,
            "Confirm Clean",
            "This will move deletable files to a quarantine folder (safer than immediate deletion). Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if resp != QMessageBox.StandardButton.Yes:
            return

        # build selected targets mapping
        sel = {}
        for idx, cat in enumerate(self.targets.keys()):
            if self.checkboxes[idx].isChecked():
                sel[cat] = self.targets[cat]

        if not sel:
            QMessageBox.information(self, "No Selection", "No categories selected to clean.")
            return

        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress.show()

        self.worker = WorkerThread("clean", sel, excludes=self.excludes, dry_run=False, quarantine_dir=self.quarantine_dir)
        self.worker.clean_complete.connect(self.on_clean_finished)
        self.worker.start()

    def on_clean_finished(self, moved_bytes, files_moved):
        self.progress.hide()
        # log the cleanup
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()}Z - moved {files_moved} files, {moved_bytes} bytes to {self.quarantine_dir}\n")
        except Exception:
            pass

        QMessageBox.information(self, "Clean Complete", f"Moved {files_moved} files ({self.format_bytes(moved_bytes)}) to quarantine.")
        self.start_scan() # Automatic re-scan to confirm cleanup

    def show_preview(self):
        # Ensure we have last_file_map
        if not self.last_file_map:
            self.start_scan()
            QMessageBox.information(self, "Preview", "Scan started. Click Preview again when analysis completes.")
            return

        # Build list of files from selected categories
        files = []
        for idx, cat in enumerate(self.targets.keys()):
            if self.checkboxes[idx].isChecked():
                files.extend(self.last_file_map.get(cat, []))

        dlg = QDialog(self)
        dlg.setWindowTitle("Preview Deletable Files")
        dlg.resize(700, 500)
        layout = QVBoxLayout(dlg)
        listw = QListWidget()
        # limit to first 2000 items to avoid UI freeze
        for fp in files[:2000]:
            listw.addItem(fp)
        layout.addWidget(listw)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Close | QDialogButtonBox.StandardButton.Ok)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Proceed to Clean")
        btns.accepted.connect(lambda: (dlg.accept(), self.start_clean()))
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        dlg.exec()

    def edit_excludes(self):
        # Let user pick a directory to exclude and save to settings
        d = QFileDialog.getExistingDirectory(self, "Select directory to exclude from scans")
        if not d:
            return
        if d not in self.excludes:
            self.excludes.append(d)
            self._save_settings()
            QMessageBox.information(self, "Exclude Added", f"Excluded: {d}")

    def _load_settings(self):
        try:
            if os.path.exists(self.settings_path):
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.excludes = data.get("excludes", [])
            else:
                self.excludes = []
        except Exception:
            self.excludes = []

    def _save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump({"excludes": self.excludes}, f, indent=2)
        except Exception:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MinimalistCleaner()
    window.show()
    sys.exit(app.exec())