"""
Image Resolver - GUI for image format conversion, resizing, and cropping.

Dependencies:
    pip install Pillow cairosvg pymupdf PySide6

Run:
    python main.py
"""

import sys

# Validate PySide6
try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    sys.exit("PySide6 is not installed. Run: pip install PySide6")

# Validate Pillow
try:
    from PIL import Image
except ImportError:
    sys.exit("Pillow is not installed. Run: pip install Pillow")

from src.app import App


def register_file_association():
    """Register .qif file association in Windows registry (per-user, no elevation needed)."""
    import sys
    import winreg
    from pathlib import Path
    import ctypes

    # Only register if running on Windows and as a compiled executable (frozen)
    if sys.platform != "win32" or not getattr(sys, 'frozen', False):
        return

    try:
        exe_path = str(Path(sys.executable).resolve())
        icon_path = f"{exe_path},0"
        
        # 1. Register file extension .qif -> QIF.Project
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.qif") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "QIF.Project")
            
        # 2. Register ProgID QIF.Project
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\QIF.Project") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "QIF Project File")
            
        # 3. Set default icon
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\QIF.Project\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, icon_path)
            
        # 4. Set shell open command: "executable_path" "%1"
        command = f'"{exe_path}" "%1"'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\QIF.Project\shell\open\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, command)
            
        # Notify Windows Shell that file association has changed (SHCNE_ASSOCCHANGED)
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    except Exception:
        pass


def main():
    """Entry point for the application."""
    # Auto-register file association on startup
    register_file_association()

    app = QApplication(sys.argv)
    window = App()
    window.show()

    # Load project from command-line argument if specified
    if len(sys.argv) > 1:
        arg_path = sys.argv[1]
        if arg_path.endswith(".qif"):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: window._load_project_file(arg_path))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
