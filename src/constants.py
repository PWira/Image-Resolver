"""
Konstanta untuk Quick Image Formatting - format, ekstensi, dan konfigurasi.
"""

# Format output yang praktis dan umum dipakai
OUTPUT_FORMATS = [
    "PNG", "JPEG", "WEBP", "TIFF", "BMP", "GIF", "ICO", "ICNS",
    "JPEG2000", "TGA", "PCX", "PPM", "SGI", "AVIF", "QOI", "DDS",
]

# Ekstensi default untuk setiap format output
EXT_MAP = {
    "PNG":      ".png",
    "JPEG":     ".jpg",
    "WEBP":     ".webp",
    "TIFF":     ".tiff",
    "BMP":      ".bmp",
    "GIF":      ".gif",
    "ICO":      ".ico",
    "ICNS":     ".icns",
    "JPEG2000": ".jp2",
    "TGA":      ".tga",
    "PCX":      ".pcx",
    "PPM":      ".ppm",
    "SGI":      ".sgi",
    "AVIF":     ".avif",
    "QOI":      ".qoi",
    "DDS":      ".dds",
}

# Semua ekstensi input yang didukung Pillow + SVG + PDF
INPUT_EXTS = {
    ".jpg", ".jpeg", ".jfif", ".jpe",
    ".png", ".apng",
    ".webp", ".avif", ".avifs", ".qoi",
    ".tiff", ".tif",
    ".bmp", ".dib",
    ".gif",
    ".ico", ".icns", ".cur",
    ".jp2", ".j2k", ".j2c", ".jpc", ".jpf", ".jpx",
    ".tga", ".icb", ".vda", ".vst",
    ".pcx", ".ppm", ".pbm", ".pgm", ".pnm", ".pfm",
    ".sgi", ".rgb", ".rgba", ".bw",
    ".dds", ".psd", ".xbm", ".xpm",
    ".dcx", ".msp", ".im",
    ".eps", ".ps",
    ".svg",
    ".pdf",
}

SVG_EXT = {".svg"}
PDF_EXT = {".pdf"}

# Format yang butuh konversi mode sebelum disimpan
NEEDS_RGB  = {"JPEG", "BMP", "PCX", "PPM", "SGI", "TGA", "DDS"}
NEEDS_RGBA = {"ICO", "ICNS"}
QUALITY_FMT = {"JPEG", "WEBP", "AVIF"}
