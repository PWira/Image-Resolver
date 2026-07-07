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


def main():
    """Entry point for the application."""
    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
