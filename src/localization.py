"""
Localization/i18n module for Quick Image Formatting.
Supports English (default) and Indonesian.

All labels are written in simple, plain language that anyone can understand.
"""

# Translation dictionary
TRANSLATIONS = {
    "en": {
        # Window
        "title": "Quick Image Formatting",
        "file_menu": "File",
        "settings": "Settings",
        "about_qif": "About QIF",
        "language": "Language",
        "convert": "Convert & Resize",
        "crop": "Crop",
        "color_palette": "Color Palette",
        "custom_color": "Custom Accent Color...",
        "theme_gold": "Gold Dust",
        "theme_purple": "Cyber Neon",
        "theme_blue": "Nord Ocean",
        "theme_green": "Forest Mint",
        "theme_light": "Solar Light",

        # Tabs
        "tab_convert": "Convert Images",
        "tab_crop": "Crop Images",
        "tab_adjustments": "Adjustments",
        "tab_lut": "LUT",
        "tab_export": "Export",

        # LUT tab
        "lut_section": "LUT Color Grading",
        "lut_mode": "LUT Mode",
        "lut_none": "No LUT",
        "lut_same_size": "Same LUT for all images",
        "lut_one_by_one": "Custom LUT per image",
        "lut_load_file": "Load Custom LUT...",
        "lut_no_file": "No LUT file loaded",
        "lut_preset": "Preset LUT",
        "lut_preset_none": "-- None / Custom --",
        "lut_intensity": "Intensity",
        "lut_generator": "Create / Edit LUT",
        "lut_brightness": "Brightness",
        "lut_contrast": "Contrast",
        "lut_saturation": "Saturation",
        "lut_temp": "Temperature",
        "lut_tint": "Tint",
        "lut_gamma": "Gamma",
        "lut_hue": "Hue Shift",
        "lut_r_gain": "Red Gain",
        "lut_g_gain": "Green Gain",
        "lut_b_gain": "Blue Gain",
        "lut_export_cube": "Save LUT as .cube...",
        "lut_reset": "Reset LUT",
        "lut_files": "3D LUT Files (*.cube *.3dl)",
        "export_section": "Export",

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
        "convert_now": "EXPORT",
        "files_in_list": "images ready",
        "no_files": "No images added yet. Click \"Add Files\" or \"Add Folder\" to start.",

        # Crop tab
        "crop_section": "Crop",
        "crop_mode": "How do you want to crop?",
        "crop_none": "No crop",
        "crop_same_size": "Same size for all images",
        "crop_one_by_one": "Crop each manually",
        "crop_width": "Crop Width",
        "crop_height": "Crop Height",
        "crop_from": "Start From",
        "crop_center": "Center",
        "crop_top_left": "Top-Left Corner",
        "crop_top_right": "Top-Right Corner",
        "crop_bottom_left": "Bottom-Left Corner",
        "crop_bottom_right": "Bottom-Right Corner",
        "crop_top_center": "Top-Center",
        "crop_bottom_center": "Bottom-Center",
        "enable_crop": "Enable Crop",
        "enable_lut": "Enable LUT Color Grading",
        "crop_area": "Crop Area",
        "crop_x": "Left",
        "crop_y": "Top",
        "crop_shape": "Shape",
        "crop_free": "Free",
        "crop_previous": "Previous",
        "crop_next": "Next",
        "crop_image_n_of": "Image {current} of {total}",
        "crop_skip": "Skip this image",
        "crop_save_all": "EXPORT",
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
        "custom_filename": "Custom File Name (optional)",
        "custom_filename_placeholder": "Original name (e.g. photo)",
        "overwrite_warning_title": "Overwrite Existing Files?",
        "overwrite_warning_msg": "The following {count} file(s) already exist in the target folder:\n\n{files}\n\nDo you want to overwrite them?",
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

        # Project Menu
        "project": "Project",
        "open_project": "Open Project...",
        "open_recent": "Open Recent",
        "recovered_session": "Recovered Session",
        "no_recent_projects": "No Recent Projects",
        "save_project": "Save Project...",
        "project_files": "QIF Project Files (*.qif)",
        "project_saved": "Project saved successfully.",
        "project_loaded": "Project loaded successfully.",
        "project_corrupted_title": "Security Warning",
        "project_corrupted": "Failed to open project. The file structure is invalid or the file has been tampered with or corrupted.",
        "project_missing_images_title": "Missing Images",
        "project_missing_images": "The following images could not be found and were skipped:\n\n{paths}",
        "unsaved_changes_title": "Unsaved Changes",
        "unsaved_changes": "You have unsaved changes. Do you want to save your project before closing?",

        # Folder & Unified Add
        "add_files_or_folder": "Add File / Folder",
        "new_folder": "New Folder",
        "folder_properties": "Folder Settings",
        "folder_mode": "Manipulation Mode",
        "mode_same": "Shared Settings (All Images)",
        "mode_individual": "Individual Settings (Each Image)",
        "folder_export_mode": "Folder Export Mode",
        "export_single_image": "Export as Single Merged Image",
        "export_separate_files": "Export as Separate Files",
        "merge_layout": "Merge Layout",
        "layout_vertical": "Vertical Stack",
        "layout_horizontal": "Horizontal Stack",
        "layout_grid": "Grid Tile",
        "layout_overlay": "Overlay Blend",
    },
    "id": {
        # Window
        "title": "Quick Image Formatting",
        "file_menu": "File",
        "settings": "Pengaturan",
        "about_qif": "Tentang QIF",
        "language": "Bahasa",
        "convert": "Konversi & Ubah Ukuran",
        "crop": "Potong",
        "color_palette": "Tema Warna",
        "custom_color": "Warna Aksen Kustom...",
        "theme_gold": "Emas Klasik",
        "theme_purple": "Cyber Neon",
        "theme_blue": "Nord Ocean",
        "theme_green": "Forest Mint",
        "theme_light": "Solar Light",

        # Tabs
        "tab_convert": "Konversi Gambar",
        "tab_crop": "Potong Gambar",
        "tab_adjustments": "Penyesuaian",
        "tab_lut": "LUT",
        "tab_export": "Ekspor",

        # LUT tab
        "lut_section": "Warna Color Grading LUT",
        "lut_mode": "Mode LUT",
        "lut_none": "Tanpa LUT",
        "lut_same_size": "LUT sama untuk semua gambar",
        "lut_one_by_one": "LUT kustom tiap gambar",
        "lut_load_file": "Muat LUT Kustom...",
        "lut_no_file": "Belum ada file LUT",
        "lut_preset": "Preset LUT",
        "lut_preset_none": "-- Tanpa / Kustom --",
        "lut_intensity": "Intensitas",
        "lut_generator": "Buat / Edit LUT",
        "lut_brightness": "Kecerahan",
        "lut_contrast": "Kontras",
        "lut_saturation": "Saturasi",
        "lut_temp": "Temperatur",
        "lut_tint": "Semburat Warna",
        "lut_gamma": "Gamma",
        "lut_hue": "Pergeseran Warna",
        "lut_r_gain": "Penguatan Merah",
        "lut_g_gain": "Penguatan Hijau",
        "lut_b_gain": "Penguatan Biru",
        "lut_export_cube": "Simpan LUT sebagai .cube...",
        "lut_reset": "Reset LUT",
        "lut_files": "File 3D LUT (*.cube *.3dl)",
        "export_section": "Ekspor",

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
        "convert_now": "EXPORT",
        "files_in_list": "gambar siap",
        "no_files": "Belum ada gambar. Klik \"Tambah File\" atau \"Tambah Folder\".",

        # Crop tab
        "crop_section": "Potong",
        "crop_mode": "Bagaimana cara potongnya?",
        "crop_none": "Tanpa crop",
        "crop_same_size": "Ukuran sama untuk semua",
        "crop_one_by_one": "Potong tiap gambar satu per satu",
        "crop_width": "Lebar Potong",
        "crop_height": "Tinggi Potong",
        "crop_from": "Mulai Dari",
        "crop_center": "Tengah",
        "crop_top_left": "Pojok Kiri Atas",
        "crop_top_right": "Pojok Kanan Atas",
        "crop_bottom_left": "Pojok Kiri Bawah",
        "crop_bottom_right": "Pojok Kanan Bawah",
        "crop_top_center": "Tengah Atas",
        "crop_bottom_center": "Tengah Bawah",
        "enable_crop": "Aktifkan Potong",
        "enable_lut": "Aktifkan Warna LUT",
        "crop_area": "Area Potong",
        "crop_x": "Kiri",
        "crop_y": "Atas",
        "crop_shape": "Bentuk",
        "crop_free": "Bebas",
        "crop_previous": "Sebelumnya",
        "crop_next": "Berikutnya",
        "crop_image_n_of": "Gambar {current} dari {total}",
        "crop_skip": "Lewati gambar ini",
        "crop_save_all": "EXPORT",
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
        "custom_filename": "Nama File Kustom (opsional)",
        "custom_filename_placeholder": "Nama asli (cth: foto)",
        "overwrite_warning_title": "Timpa File yang Ada?",
        "overwrite_warning_msg": "{count} file berikut sudah ada di folder tujuan:\n\n{files}\n\nApakah Anda ingin menimpa file tersebut?",
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

        # Menu Proyek
        "project": "Proyek",
        "open_project": "Buka Proyek...",
        "open_recent": "Buka Terbaru",
        "recovered_session": "Sesi Pemulihan",
        "no_recent_projects": "Tidak Ada Proyek Terbaru",
        "save_project": "Simpan Proyek...",
        "project_files": "File Proyek QIF (*.qif)",
        "project_saved": "Proyek berhasil disimpan.",
        "project_loaded": "Proyek berhasil dimuat.",
        "project_corrupted_title": "Peringatan Keamanan",
        "project_corrupted": "Gagal membuka proyek. Struktur file tidak valid atau file telah dimodifikasi atau rusak.",
        "project_missing_images_title": "Gambar Hilang",
        "project_missing_images": "Gambar-gambar berikut tidak dapat ditemukan dan dilewati:\n\n{paths}",
        "unsaved_changes_title": "Perubahan Belum Disimpan",
        "unsaved_changes": "Ada perubahan yang belum disimpan. Apakah Anda ingin menyimpan proyek sebelum menutup?",

        # Folder & Unified Add
        "add_files_or_folder": "Tambah File / Folder",
        "new_folder": "Folder Baru",
        "folder_properties": "Pengaturan Folder",
        "folder_mode": "Mode Manipulasi",
        "mode_same": "Pengaturan Sama (Semua Gambar)",
        "mode_individual": "Pengaturan Masing-Masing (Individual)",
        "folder_export_mode": "Mode Ekspor Folder",
        "export_single_image": "Ekspor Jadi 1 Gambar Gabungan",
        "export_separate_files": "Ekspor File Terpisah",
        "merge_layout": "Tata Letak Penggabungan",
        "layout_vertical": "Tumpuk Vertikal",
        "layout_horizontal": "Tumpuk Horizontal",
        "layout_grid": "Kotak Grid",
        "layout_overlay": "Layer Transparan",
    },
}


class I18n:
    """Localization manager for Quick Image Formatting."""

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
