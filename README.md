# Image Resolver

A comprehensive GUI application for image format conversion and resizing using Python and tkinter.

## Features

- **Format Conversion**: Convert between multiple image formats including PNG, JPEG, WEBP, TIFF, BMP, GIF, ICO, ICNS, JPEG2000, TGA, PCX, PPM, SGI, AVIF, QOI, and DDS
- **Image Resizing**: Scale images to desired dimensions
- **User-Friendly GUI**: Built with tkinter (built-in Python module)
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Requirements

- Python 3.7+
- tkinter (usually comes with Python)
- Pillow
- cairosvg
- pymupdf

## Installation

1. Clone this repository:
```bash
git clone https://github.com/PWira/Image-Resolver.git
cd ImageResolver
```

2. Install dependencies:
```bash
pip install Pillow cairosvg pymupdf
```

## Usage

Run the application:
```bash
python ImageResolver.py
```

## Building Executable (Optional)

To create a standalone executable using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --icon=monolight.png --name="Image Resolver" --distpath="./dist" ImageResolver.py
```

## License

This project is licensed under the MIT License
