# Quicky Cleaner

Lightweight Windows cache/temp cleaner with a beautiful PyQt6 UI.

## Features
- Analyze reclaimable space for common cache/temp locations
- Clean selected locations (confirmation required)
- Preview files before cleaning
- Per-category cleanup selection
- Quarantine moved files instead of permanently deleting them
- Exclude directories from scans

## Run
Requires Python 3.8+ and PyQt6.

Install deps:
```powershell
pip install PyQt6
```

Run:
```powershell
python Quicky_Cleaner.py
```

## Notes
- The cleaner permanently deletes files. Use with caution.
