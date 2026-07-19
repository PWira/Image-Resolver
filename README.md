# QIF - Quick Image Formatting

A comprehensive GUI application for quick image format conversion and resizing using Python and PySide6 (Qt for Python).

## Features

- **Format Conversion**: Convert between 16+ image formats (PNG, JPEG, WEBP, TIFF, BMP, GIF, ICO, ICNS, JPEG2000, TGA, PCX, PPM, SGI, AVIF, QOI, DDS)
- **Image Resizing**: Scale images with multiple modes (proportional, exact, thumbnail/crop)
- **SVG & PDF Support**: Direct conversion from SVG and PDF files
- **Batch Processing**: Process multiple files at once with recursive folder support
- **Quality Control**: Adjustable compression quality for lossy formats
- **Project File Management**: Save, load, and manage sessions securely using encrypted `.qif` project files (AES-128 via Cryptography/Fernet)
- **Session Auto-Recovery**: Recovers unsaved changes automatically from temporary `autosave.qif` sessions in case of crash/unexpected quit
- **Windows File Association**: Registers `.qif` file association in the Windows registry on start, enabling double-click to open project files
- **User-Friendly GUI**: Modern, responsive interface built with PySide6 (Qt) and customizable theme color palettes (Gold, Purple, Blue, Green, Light, and Custom accents)
- **Cross-Platform**: Works on Windows, macOS, and Linux

### Application Tabs

1. **Convert & Resize** - Convert single image to different format with advanced resize options (scale %, max dimensions, multiple resize modes)
2. **Batch** - Process multiple images from a folder with consistent settings
3. **Crop** - Crop single image with multiple modes

## Requirements

- Python 3.7+
- PySide6
- Pillow
- cairosvg
- pymupdf
- openpyxl
- cryptography


## Installation

1. Clone this repository:
```bash
git clone https://github.com/PWira/QIF-Quick-Image-Formatting.git
cd QIF-Quick-Image-Formatting
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install PySide6 Pillow cairosvg pymupdf openpyxl cryptography
```

## Quick Start

1. Run the application:
```bash
python main.py
```

You can also open project files directly by double-clicking a `.qif` file (on Windows after the first run as compiled executable) or by passing the project path as an argument:
```bash
python main.py path/to/project.qif
```

2. Choose a tab based on your needs:
   - **Convert & Resize**: Single image conversion and resizing
   - **Batch**: Process multiple images from a folder with consistent settings
   - **Crop**: Crop single image with multiple modes

3. Select input file/folder, set options, and click the button

## Usage

### Tab 1: Convert & Resize
- Convert a single image to a different format
- Optional: Resize while converting with advanced options:
  - **Proportional (fit)**: Maintain aspect ratio
  - **Exact**: Force exact dimensions
  - **Thumbnail (crop)**: Crop to fill dimensions
  - **Scale (%)**: Scale image size by percentage
  - **Maximum width/height constraints**
- Adjustable quality for JPEG/WEBP/AVIF
- Auto-generates output filename

### Tab 2: Batch
- Process multiple images from a folder
- Recursive option to process subfolders
- Consistent format and quality across all images
- Detailed success/failure log

### Tab 3: Crop
- Crop single image with multiple modes:
  - **Proporsional (fit)**: Maintain aspect ratio
  - **Tepat (exact)**: Force exact dimensions
  - **Thumbnail (crop)**: Crop to fill dimensions
  - **Center (crop)**: Crop to fill dimensions from center

## Project Structure

```
ImageConversion/
├── main.py                      # Entry point application
├── src/                         # Source code package
│   ├── app.py                   # Main GUI application class
│   ├── image_processor.py       # Core image processing functions
│   ├── project_manager.py       # Handles secure encryption/decryption of project state
│   ├── theme.py                 # Core palette theme configuration
│   ├── localization.py          # Multilingual localization settings (EN/ID)
│   ├── constants.py             # Format, extension, and configuration constants
│   └── ui_components.py         # GUI utilities (Tooltip, custom widgets, helpers)
├── depricated/                  # Legacy files
│   └── ImageResolver.py         # (deprecated - use main.py)
├── requirements.txt             # Python dependencies
├── LICENSE                      # MIT License
├── README.md                    # This file
├── monolight.png                # Application icon
└── .gitignore                   # Git ignore rules
```

### Module Descriptions

| Module | Purpose |
|--------|---------|
| **main.py** | Entry point application. Validates dependencies, registers Windows file association, parses command line args, and boots PySide6. |
| **src/app.py** | `App` class (QMainWindow) handling PySide6 UI, menus, settings persistence, and project state. |
| **src/project_manager.py** | Encrypts and decrypts `.qif` project files using AES-128 via the Cryptography library. |
| **src/theme.py** | Theme manager supporting multiple preset color palettes (Gold, Purple, Blue, Green, Light) and custom color accents. |
| **src/localization.py** | Handles language translation configuration for a bilingual interface (English / Indonesian). |
| **src/image_processor.py** | Core functions for opening images (SVG/PDF/Raster), resizing (Proportional, Exact, Thumbnail), and saving with conversions. |
| **src/constants.py** | Global constants for formats, extension mappings, and default parameters. |
| **src/ui_components.py** | Reusable PySide6 custom widgets, tools (Tooltip), and input validation helper functions. |

## Building Executable (Optional)

To create a standalone executable using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconfirm "Quick Image Formatting.spec"
```

The executable will be available in `./dist/` folder.

## Development

### Project Architecture

The project follows a modular architecture:
- **main.py**: Bootstrap and dependency validation
- **src/app.py**: UI layer (tkinter GUI)
- **src/image_processor.py**: Business logic (image operations)
- **src/constants.py**: Configuration and constants
- **src/ui_components.py**: Reusable UI components

### Adding New Formats

1. Add format to `OUTPUT_FORMATS` in `src/constants.py`
2. Add extension mapping to `EXT_MAP` if needed
3. Add mode conversion logic in `save_image()` if needed

### Running Tests

To create tests, import modules from `src/`:
```python
from src.image_processor import open_image, do_resize
from src.constants import OUTPUT_FORMATS
```

## Supported Formats

### Input Formats
- **Raster**: JPG, PNG, WEBP, AVIF, QOI, TIFF, BMP, GIF, ICO, ICNS, JP2, TGA, PCX, PPM, SGI, DDS, PSD, XBM, XPM, DCX, MSP, EPS
- **Vector**: SVG
- **Document**: PDF

### Output Formats (16+)
PNG, JPEG, WEBP, TIFF, BMP, GIF, ICO, ICNS, JPEG2000, TGA, PCX, PPM, SGI, AVIF, QOI, DDS

## License

This project is licensed under the MIT License
