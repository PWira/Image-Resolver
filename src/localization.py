"""
Localization/i18n module for Image Resolver.
Supports English (default) and Indonesian.

All labels are written in simple, plain language that anyone can understand.
"""

# Translation dictionary
TRANSLATIONS = {
    "en": {
        # Window
        "title": "Image Resolver",

        # Tabs
        "tab_convert": "Convert Images",
        "tab_crop": "Crop Images",

        # Convert tab
        "pick_images": "Pick Your Images",
        "add_files": "Add Files",
        "add_folder": "Add Folder",
        "remove_selected": "Remove",
        "clear_all": "Clear All",
        "save_as": "Save As",
        "picture_quality": "Picture Quality",
        "save_to": "Save To",
        "browse": "Browse...",
        "change_size": "Change Size (optional)",
        "width": "Width",
        "height": "Height",
        "resize_percent": "Resize by %",
        "include_subfolders": "Include subfolders",
        "convert_now": "Convert Now",
        "files_in_list": "images ready",
        "no_files": "No images added yet. Click \"Add Files\" or \"Add Folder\" to start.",

        # Crop tab
        "crop_mode": "How do you want to crop?",
        "crop_same_size": "Same size for all images",
        "crop_one_by_one": "Crop each image manually",
        "crop_width": "Crop Width",
        "crop_height": "Crop Height",
        "crop_from": "Start From",
        "crop_center": "Center",
        "crop_top_left": "Top-Left Corner",
        "crop_area": "Crop Area",
        "crop_x": "Left",
        "crop_y": "Top",
        "crop_shape": "Shape",
        "crop_free": "Free",
        "crop_previous": "Previous",
        "crop_next": "Next",
        "crop_image_n_of": "Image {current} of {total}",
        "crop_skip": "Skip this image",
        "crop_save_all": "Crop & Save All",
        "crop_no_image": "No image loaded yet",
        "crop_hint": "Click and drag to select the area you want to keep",

        # Shared
        "select_btn": "Browse...",
        "all_images": "All images",
        "all_files": "All files",
        "log": "Activity Log",

        # Messages
        "error_title": "Oops!",
        "error_no_files": "Please add some images first.",
        "error_no_output": "Please pick a folder to save your images.",
        "error_no_crop": "Please set a crop area first.",
        "info_done": "Done!",
        "info_processing": "Working...",

        # Log
        "log_success": "✓",
        "log_error": "✗",
        "log_arrow": "→",
        "log_saved": "Saved",
        "log_failed": "Failed",
        "log_files_found": "images found",
        "log_completed": "Finished:",
        "log_ok_count": "saved",
        "log_err_count": "failed",
        "log_no_files": "No matching images found in that folder.",
    },
    "id": {
        # Window
        "title": "Image Resolver",

        # Tabs
        "tab_convert": "Konversi Gambar",
        "tab_crop": "Potong Gambar",

        # Convert tab
        "pick_images": "Pilih Gambar",
        "add_files": "Tambah File",
        "add_folder": "Tambah Folder",
        "remove_selected": "Hapus",
        "clear_all": "Hapus Semua",
        "save_as": "Simpan Sebagai",
        "picture_quality": "Kualitas Gambar",
        "save_to": "Simpan Ke",
        "browse": "Pilih...",
        "change_size": "Ubah Ukuran (opsional)",
        "width": "Lebar",
        "height": "Tinggi",
        "resize_percent": "Ubah ukuran %",
        "include_subfolders": "Masuk subfolder",
        "convert_now": "Konversi Sekarang",
        "files_in_list": "gambar siap",
        "no_files": "Belum ada gambar. Klik \"Tambah File\" atau \"Tambah Folder\".",

        # Crop tab
        "crop_mode": "Bagaimana cara potongnya?",
        "crop_same_size": "Ukuran sama untuk semua gambar",
        "crop_one_by_one": "Potong setiap gambar satu per satu",
        "crop_width": "Lebar Potong",
        "crop_height": "Tinggi Potong",
        "crop_from": "Mulai Dari",
        "crop_center": "Tengah",
        "crop_top_left": "Pojok Kiri Atas",
        "crop_area": "Area Potong",
        "crop_x": "Kiri",
        "crop_y": "Atas",
        "crop_shape": "Bentuk",
        "crop_free": "Bebas",
        "crop_previous": "Sebelumnya",
        "crop_next": "Berikutnya",
        "crop_image_n_of": "Gambar {current} dari {total}",
        "crop_skip": "Lewati gambar ini",
        "crop_save_all": "Potong & Simpan Semua",
        "crop_no_image": "Belum ada gambar",
        "crop_hint": "Klik dan seret untuk memilih area yang ingin disimpan",

        # Shared
        "select_btn": "Pilih...",
        "all_images": "Semua gambar",
        "all_files": "Semua file",
        "log": "Log Aktivitas",

        # Messages
        "error_title": "Oops!",
        "error_no_files": "Tambahkan gambar terlebih dahulu.",
        "error_no_output": "Pilih folder untuk menyimpan gambar.",
        "error_no_crop": "Tentukan area potong terlebih dahulu.",
        "info_done": "Selesai!",
        "info_processing": "Memproses...",

        # Log
        "log_success": "✓",
        "log_error": "✗",
        "log_arrow": "→",
        "log_saved": "Tersimpan",
        "log_failed": "Gagal",
        "log_files_found": "gambar ditemukan",
        "log_completed": "Selesai:",
        "log_ok_count": "tersimpan",
        "log_err_count": "gagal",
        "log_no_files": "Tidak ada gambar yang cocok di folder itu.",
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

    def __call__(self, key: str, **kwargs) -> str:
        """Allow calling instance as function: i18n(key, current=1, total=5)."""
        text = self.get(key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, IndexError):
                pass
        return text


# Global instance
_i18n = I18n("en")


def get_i18n() -> I18n:
    """Get global i18n instance."""
    return _i18n


def set_language(language: str):
    """Set global language."""
    _i18n.set_language(language)
