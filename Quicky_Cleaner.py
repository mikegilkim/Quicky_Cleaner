import sys
import os
import shutil
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar, QFrame, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)

class WorkerThread(QThread):
    """Background worker to keep the UI buttery-smooth during disk scans."""
    scan_complete = pyqtSignal(dict, float)
    clean_complete = pyqtSignal(float)

    def __init__(self, mode, targets):
        super().__init__()
        self.mode = mode
        self.targets = targets

    def run(self):
        if self.mode == "scan":
            results = {}
            total_bytes = 0
            for category, paths in self.targets.items():
                cat_bytes = 0
                for path in paths:
                    if os.path.exists(path):
                        for root, _, files in os.walk(path):
                            for f in files:
                                fp = os.path.join(root, f)
                                try:
                                    if os.path.exists(fp):
                                        cat_bytes += os.path.getsize(fp)
                                except (PermissionError, FileNotFoundError):
                                    continue
                results[category] = cat_bytes
                total_bytes += cat_bytes
            self.scan_complete.emit(results, total_bytes)

        elif self.mode == "clean":
            cleaned_bytes = 0
            for category, paths in self.targets.items():
                for path in paths:
                    if os.path.exists(path):
                        for root, _, files in os.walk(path):
                            for f in files:
                                fp = os.path.join(root, f)
                                try:
                                    sz = os.path.getsize(fp)
                                    os.remove(fp)
                                    cleaned_bytes += sz
                                except Exception:
                                    continue
            self.clean_complete.emit(cleaned_bytes)


class MinimalistCleaner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Purge MVP")
        self.resize(500, 620)
        
        # Targets Setup
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        self.targets = {
            "Windows Temp Files": [os.environ.get("TEMP", ""), r"C:\Windows\Temp"],
            "Google Chrome Cache": [os.path.join(local_appdata, r"Google\Chrome\User Data\Default\Cache")],
            "Mozilla Firefox Cache": [os.path.join(local_appdata, r"Mozilla\Firefox\Profiles")],
            "User Application Temp": [os.path.join(local_appdata, "Temp")]
        }

        self.scanned_bytes = 0
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

        self.table = QTableWidget(len(self.targets), 2)
        self.table.setHorizontalHeaderLabels(["CATEGORY", "SIZE"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Initialize table placeholders
        for idx, cat in enumerate(self.targets.keys()):
            self.table.setItem(idx, 0, QTableWidgetItem(cat))
            self.table.setItem(idx, 1, QTableWidgetItem("-"))

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
        btn_layout.addWidget(self.clean_btn)
        main_layout.addLayout(btn_layout)

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

        self.worker = WorkerThread("scan", self.targets)
        self.worker.scan_complete.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_finished(self, results, total_bytes):
        self.progress.hide()
        self.scan_btn.setEnabled(True)
        self.scanned_bytes = total_bytes
        self.size_display.setText(self.format_bytes(total_bytes))

        for idx, (cat, cat_bytes) in enumerate(results.items()):
            self.table.item(idx, 1).setText(self.format_bytes(cat_bytes))

        if total_bytes > 0:
            self.clean_btn.setEnabled(True)

    def start_clean(self):
        resp = QMessageBox.question(
            self,
            "Confirm Clean",
            "This will permanently delete temporary/cache files. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if resp != QMessageBox.StandardButton.Yes:
            return

        self.scan_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        self.progress.show()

        self.worker = WorkerThread("clean", self.targets)
        self.worker.clean_complete.connect(self.on_clean_finished)
        self.worker.start()

    def on_clean_finished(self, cleaned_bytes):
        self.progress.hide()
        self.start_scan() # Automatic re-scan to confirm cleanup


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MinimalistCleaner()
    window.show()
    sys.exit(app.exec())