"""
Localization/i18n module for Image Resolver.
Supports English (default) and Indonesian.
"""

# Translation dictionary
TRANSLATIONS = {
    "en": {
        # Window and tabs
        "title": "Image Converter & Resizer",
        "tab_convert": "Convert & Resize",
        "tab_batch": "Batch",
        "tab_crop": "Crop",
        
        # Common UI
        "log": "Log",
        "format_output": "Output format",
        "quality": "Quality",
        "width_px": "Width (px)",
        "height_px": "Height (px)",
        "mode": "Mode",
        "select_btn": "Browse...",
        "all_images": "All images",
        "all_files": "All files",
        
        # Tab: Convert & Resize
        "file_input": "Input file",
        "file_output": "Output file",
        "resize_optional": "Resize (optional)",
        "mode_resize": "Resize mode",
        "resize_fit": "Proportional (fit)",
        "resize_exact": "Exact",
        "resize_thumbnail": "Thumbnail (crop)",
        "resize_percent": "Percentage (%)",
        "btn_convert_now": "Convert & Resize Now",
        "tooltip_quality": "Quality only applies to JPEG, WEBP, AVIF",
        "tooltip_width": "Leave empty if not used",
        "tooltip_height": "Leave empty if not used",
        "scale_percent": "Scale (%)",
        "max_width": "Max width",
        "max_height": "Max height",
        "tooltip_scale": "Example: 50 = half size",
        "tooltip_max_w": "Maximum width limit",
        "tooltip_max_h": "Maximum height limit",
        
        # Tab: Batch
        "tab_batch_label": "Batch",
        "folder_input": "Input folder",
        "folder_output": "Output folder",
        "recursive": "Process subfolders (recursive)",
        "btn_batch_start": "Start Batch",
        
        # Tab: Crop
        "crop_x": "X offset (px)",
        "crop_y": "Y offset (px)",
        "crop_width": "Crop width (px)",
        "crop_height": "Crop height (px)",
        "btn_crop_now": "Crop Now",
        "crop_preview_hint": "Click and drag on the preview to select crop area",
        "crop_aspect_label": "Aspect ratio",
        "crop_aspect_free": "Free",
        "crop_load_preview": "Load Preview",
        "crop_no_image": "No image loaded",
        
        # Messages
        "error_input_missing": "Missing input",
        "error_select_file": "Please select input and output files first.",
        "error_select_folder": "Please select input and output folders.",
        "error_crop_region": "Please specify a valid crop region.",
        "info_files_found": "files found in",
        "info_no_files": "No matching files found in folder.",
        "info_completed": "Completed:",
        "info_ok": "successful",
        "info_err": "failed",
        
        # Log messages (symbols kept, text translated)
        "log_success": "✓",
        "log_error": "✗",
        "log_arrow": "→",
    },
    "id": {
        # Window and tabs
        "title": "Image Converter & Resizer",
        "tab_convert": "Konversi & Resize",
        "tab_batch": "Batch",
        "tab_crop": "Potong",
        
        # Common UI
        "log": "Log",
        "format_output": "Format output",
        "quality": "Kualitas",
        "width_px": "Lebar (px)",
        "height_px": "Tinggi (px)",
        "mode": "Mode",
        "select_btn": "Pilih...",
        "all_images": "Semua gambar",
        "all_files": "Semua file",
        
        # Tab: Convert & Resize
        "file_input": "File input",
        "file_output": "File output",
        "resize_optional": "Resize (opsional)",
        "mode_resize": "Mode resize",
        "resize_fit": "Proporsional (fit)",
        "resize_exact": "Tepat (exact)",
        "resize_thumbnail": "Thumbnail (crop)",
        "resize_percent": "Persentase (%)",
        "btn_convert_now": "Konversi & Resize Sekarang",
        "tooltip_quality": "Hanya berlaku untuk JPEG, WEBP, AVIF",
        "tooltip_width": "Kosongkan jika tidak dipakai",
        "tooltip_height": "Kosongkan jika tidak dipakai",
        "scale_percent": "Skala (%)",
        "max_width": "Maks lebar",
        "max_height": "Maks tinggi",
        "tooltip_scale": "Contoh: 50 = setengah ukuran",
        "tooltip_max_w": "Batas lebar maksimal",
        "tooltip_max_h": "Batas tinggi maksimal",
        
        # Tab: Batch
        "tab_batch_label": "Batch",
        "folder_input": "Folder input",
        "folder_output": "Folder output",
        "recursive": "Masuk subfolder (recursive)",
        "btn_batch_start": "Mulai Batch Konversi",
        
        # Tab: Crop
        "crop_x": "Offset X (px)",
        "crop_y": "Offset Y (px)",
        "crop_width": "Lebar potong (px)",
        "crop_height": "Tinggi potong (px)",
        "btn_crop_now": "Potong Sekarang",
        "crop_preview_hint": "Klik dan seret pada preview untuk memilih area potong",
        "crop_aspect_label": "Rasio aspek",
        "crop_aspect_free": "Bebas",
        "crop_load_preview": "Muat Preview",
        "crop_no_image": "Belum ada gambar",
        
        # Messages
        "error_input_missing": "Input kurang",
        "error_select_file": "Pilih file input dan output terlebih dahulu.",
        "error_select_folder": "Pilih folder input dan output.",
        "error_crop_region": "Tentukan area potong yang valid.",
        "info_files_found": "file ditemukan di",
        "info_no_files": "Tidak ada file yang cocok di folder.",
        "info_completed": "Selesai:",
        "info_ok": "berhasil",
        "info_err": "gagal",
        
        # Log messages (symbols kept, text translated)
        "log_success": "✓",
        "log_error": "✗",
        "log_arrow": "→",
    },
}


class I18n:
    """Localization manager for Image Resolver."""
    
    def __init__(self, language: str = "en"):
        """
        Initialize with language.
        
        Args:
            language: Language code ("en" or "id")
        """
        self.language = language if language in TRANSLATIONS else "en"
        self.translations = TRANSLATIONS[self.language]
    
    def set_language(self, language: str):
        """Set language and reload translations."""
        if language in TRANSLATIONS:
            self.language = language
            self.translations = TRANSLATIONS[self.language]
    
    def get(self, key: str, default: str = "") -> str:
        """
        Get translated string.
        
        Args:
            key: Translation key
            default: Default value if key not found
        
        Returns:
            Translated string
        """
        return self.translations.get(key, default)
    
    def __call__(self, key: str) -> str:
        """Allow calling instance as function: i18n(key)."""
        return self.get(key)


# Global instance
_i18n = I18n("en")


def get_i18n() -> I18n:
    """Get global i18n instance."""
    return _i18n


def set_language(language: str):
    """Set global language."""
    _i18n.set_language(language)
