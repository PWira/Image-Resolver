"""
Main application window for Quick Image Formatting (PySide6 / Qt).

Unified workflow: import images -> configure format, resize, crop, LUT -> EXPORT
"""

import traceback
import sys
import threading
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSlider, QLineEdit, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QProgressBar, QTextEdit,
    QCheckBox, QRadioButton, QButtonGroup, QFrame, QAbstractItemView,
    QApplication, QSplitter, QScrollArea, QDialog, QStackedWidget, QMenu,
    QColorDialog, QTabWidget, QGroupBox,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QPixmap, QColor, QIcon
from PIL import Image

from src.constants import OUTPUT_FORMATS, EXT_MAP, INPUT_EXTS, LUT_EXTS
from src.image_processor import open_image, save_image, do_resize, do_crop, do_center_crop
from src.lut_processor import (
    apply_lut, load_lut_file, get_preset_lut, generate_lut_from_settings,
    export_lut_to_cube, PRESET_LUT_SETTINGS
)
from src.ui_components import file_filter_string, Separator, InteractiveCropView, FittedImageView, PlusMinusSpinBox
from src.localization import get_i18n, set_language
import src.theme as theme


if hasattr(sys, "_MEIPASS"):
    _PROJECT_ROOT = Path(sys._MEIPASS)
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent


class _WorkerSignals(QObject):
    log = Signal(str, str)
    progress = Signal(int)
    finished = Signal()


class ProgressDialog(QDialog):
    def __init__(self, parent=None, title_text="Export Progress"):
        super().__init__(parent)
        self.setWindowTitle(title_text)
        self.setMinimumSize(450, 300)
        self.resize(500, 320)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.CustomizeWindowHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.status_label = QLabel("Exporting images...")
        self.status_label.setObjectName("headerLabel")
        layout.addWidget(self.status_label)

        prog_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_pct = QLabel("0%")
        self.progress_pct.setFixedWidth(36)
        self.progress_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog_layout.addWidget(self.progress_bar)
        prog_layout.addWidget(self.progress_pct)
        layout.addLayout(prog_layout)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logArea")
        layout.addWidget(self.log_text, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("primaryBtn")
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    def append_log(self, msg: str, tag: str = ""):
        self.log_text.append(msg)

    def set_progress(self, value: int):
        self.progress_bar.setValue(value)
        self.progress_pct.setText(f"{value}%")

    def on_finished(self, done_text: str = "Done!"):
        self.status_label.setText(done_text)
        self.set_progress(100)
        self.btn_close.setEnabled(True)


class App(QMainWindow):
    CROP_NONE   = 0
    CROP_SAME   = 1
    CROP_MANUAL = 2

    LUT_NONE   = 0
    LUT_SAME   = 1
    LUT_MANUAL = 2

    def __init__(self):
        super().__init__()
        self._load_settings()
        self.setWindowTitle(self.i18n("title"))
        self.setMinimumSize(960, 600)
        self.resize(1020, 680)
        self._set_icon()
        self.setStyleSheet(theme.get_stylesheet())

        self._files: List[str] = []
        self._crop_data: Dict[int, dict] = {}
        self._crop_updating = True
        self._crop_index: Optional[int] = None
        self._project_dirty = False
        self._recent_projects: List[str] = []

        # LUT State
        self._lut_mode = self.LUT_NONE
        self._lut_same_file: Optional[str] = None
        self._lut_same_preset: Optional[str] = None
        self._lut_same_intensity: float = 1.0
        self._lut_same_settings: dict = {
            "brightness": 0, "contrast": 0, "saturation": 0, "temperature": 0,
            "tint": 0, "gamma": 100, "hue_shift": 0, "r_gain": 100, "g_gain": 100, "b_gain": 100
        }
        self._lut_same_obj = None

        self._lut_per_image_data: Dict[int, dict] = {}
        self._lut_updating = True
        self._lut_index: Optional[int] = None

        # Viewport zoom/pan state retention per image index
        self._view_transforms: Dict[int, Tuple[object, int, int]] = {}
        self._current_file_row: Optional[int] = None

        # Fast Preview Cache & Debounced Autosave Timer
        self._preview_cache: Dict[str, Image.Image] = {}
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._do_auto_save_temp)

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        self._build_header(root_layout)

        main_splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(main_splitter, stretch=1)

        sidebar_widget = QWidget()
        self._build_sidebar(sidebar_widget)
        main_splitter.addWidget(sidebar_widget)

        top_right_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(top_right_splitter)

        self.viewport_stack = QStackedWidget()
        self.convert_preview = FittedImageView()
        self.crop_same_view = InteractiveCropView()
        self.crop_manual_view = InteractiveCropView()
        self.viewport_stack.addWidget(self.convert_preview)
        self.viewport_stack.addWidget(self.crop_same_view)
        self.viewport_stack.addWidget(self.crop_manual_view)
        top_right_splitter.addWidget(self.viewport_stack)

        unified_scroll = QScrollArea()
        unified_scroll.setWidgetResizable(True)
        unified_scroll.setFrameShape(QFrame.NoFrame)
        unified_scroll.setMinimumWidth(320)
        unified_widget = QWidget()
        self._build_unified_options(unified_widget)
        unified_scroll.setWidget(unified_widget)
        top_right_splitter.addWidget(unified_scroll)

        main_splitter.setSizes([220, 740])
        top_right_splitter.setSizes([440, 320])

        self._signals = _WorkerSignals()
        self._update_ui_texts()

        # Connect signals for Crop
        self.crop_same_view.cropChanged.connect(self._crop_same_on_view_changed)
        self.crop_same_w.valueChanged.connect(self._crop_same_update_view)
        self.crop_same_h.valueChanged.connect(self._crop_same_update_view)
        self.crop_anchor.currentIndexChanged.connect(self._crop_same_update_view)

        self.crop_manual_view.cropChanged.connect(self._crop_manual_on_view_changed)
        for sb in (self.crop_x, self.crop_y, self.crop_w, self.crop_h):
            sb.valueChanged.connect(self._crop_manual_update_view)
        self.crop_aspect.currentIndexChanged.connect(self._crop_update_aspect_ratio)

        # Connect signals for LUT
        self.lut_mode_group.idToggled.connect(self._on_lut_mode_changed)
        self.lut_preset_combo.currentIndexChanged.connect(self._on_lut_preset_changed)
        self.btn_browse_lut.clicked.connect(self._browse_lut_file)
        self.lut_intensity_slider.valueChanged.connect(self._on_lut_intensity_changed)

        for slider in (
            self.lut_gen_b_slider, self.lut_gen_c_slider, self.lut_gen_s_slider,
            self.lut_gen_temp_slider, self.lut_gen_tint_slider, self.lut_gen_gamma_slider,
            self.lut_gen_hue_slider, self.lut_gen_r_slider, self.lut_gen_g_slider, self.lut_gen_b_gain_slider
        ):
            slider.valueChanged.connect(self._on_lut_generator_slider_changed)

        self.btn_reset_lut.clicked.connect(self._reset_lut_generator)
        self.btn_export_lut.clicked.connect(self._export_lut_file)
        self.lut_prev_btn.clicked.connect(self._lut_go_prev)
        self.lut_next_btn.clicked.connect(self._lut_go_next)

        # Connect auto-save signals
        self.output_dir.textChanged.connect(self._auto_save_temp)
        self.conv_format.currentIndexChanged.connect(self._auto_save_temp)
        self.conv_quality_slider.valueChanged.connect(self._auto_save_temp)
        self.conv_width.valueChanged.connect(self._auto_save_temp)
        self.conv_height.valueChanged.connect(self._auto_save_temp)
        self.conv_scale.valueChanged.connect(self._auto_save_temp)

        self.crop_radio_none.toggled.connect(self._auto_save_temp)
        self.crop_radio_same.toggled.connect(self._auto_save_temp)
        self.crop_radio_manual.toggled.connect(self._auto_save_temp)
        self.crop_same_w.valueChanged.connect(self._auto_save_temp)
        self.crop_same_h.valueChanged.connect(self._auto_save_temp)
        self.crop_anchor.currentIndexChanged.connect(self._auto_save_temp)
        self.crop_aspect.currentIndexChanged.connect(self._auto_save_temp)

        for sb in (self.crop_x, self.crop_y, self.crop_w, self.crop_h):
            sb.valueChanged.connect(self._auto_save_temp)
        self.crop_skip_check.toggled.connect(self._auto_save_temp)

        self._center_window()
        self._crop_updating = False
        self._lut_updating = False
        self._project_dirty = False

    def _set_icon(self):
        try:
            icon_path = _PROJECT_ROOT / "monolight.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

    def _center_window(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)

    def _change_language(self, lang: str):
        set_language(lang)
        self.i18n = get_i18n()
        self._update_ui_texts()
        self._save_settings()

    def _load_settings(self):
        import json
        settings_file = Path(_PROJECT_ROOT) / "settings.json"
        lang = "en"
        palette = "gold"
        custom_accent = ""
        self._recent_projects = []
        if settings_file.exists():
            try:
                with open(settings_file, "r") as f:
                    data = json.load(f)
                    lang = data.get("language", "en")
                    palette = data.get("palette", "gold")
                    custom_accent = data.get("custom_accent", "")
                    self._recent_projects = data.get("recent_projects", [])
            except Exception:
                pass
        set_language(lang)
        self.i18n = get_i18n()
        if palette == "custom" and custom_accent:
            theme.set_custom_accent(custom_accent)
        else:
            theme.set_active_palette(palette)

    def _save_settings(self):
        import json
        settings_file = Path(_PROJECT_ROOT) / "settings.json"
        data = {
            "language": self.i18n.language,
            "palette": theme.current_palette_name,
            "custom_accent": theme.custom_accent_color,
            "recent_projects": self._recent_projects
        }
        try:
            with open(settings_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def _apply_theme(self, name: str):
        theme.set_active_palette(name)
        self.setStyleSheet(theme.get_stylesheet())
        self._save_settings()
        self._update_ui_texts()
        self._on_file_selected(self.file_list.currentRow())

    def _choose_custom_color(self):
        initial = QColor(theme.GOLD)
        color = QColorDialog.getColor(initial, self, self.i18n("custom_color"))
        if color.isValid():
            hex_color = color.name().upper()
            theme.set_custom_accent(hex_color)
            self.setStyleSheet(theme.get_stylesheet())
            self._save_settings()
            self._update_ui_texts()
            self._on_file_selected(self.file_list.currentRow())

    def _rebuild_file_menu(self):
        """Create/recreate the unified File menu."""
        menu = QMenu(self)
        ss = f"""
            QMenu {{
                background-color: {theme.CARD_BG};
                color: {theme.TEXT_PRIMARY};
                border: 1px solid {theme.BORDER};
                min-width: 240px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {theme.GOLD};
                color: {theme.BLACK_MATTE};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {theme.BORDER};
                margin: 4px 6px;
            }}
        """
        menu.setStyleSheet(ss)

        menu.addAction(self.i18n("open_project"), self._open_project)
        recent_menu = menu.addMenu(self.i18n("open_recent"))
        recent_menu.setStyleSheet(ss)

        recovery_file = Path(_PROJECT_ROOT) / "autosave.qif"
        if recovery_file.exists():
            recent_menu.addAction(
                f"\u21ba {self.i18n('recovered_session')}",
                lambda: self._load_project_file(str(recovery_file))
            )
            recent_menu.addSeparator()

        valid_recent = [p for p in self._recent_projects if Path(p).exists()]
        if len(valid_recent) != len(self._recent_projects):
            self._recent_projects = valid_recent
            self._save_settings()

        if self._recent_projects:
            for path in self._recent_projects:
                p = Path(path)
                recent_menu.addAction(p.name, lambda f=path: self._load_project_file(f))
        else:
            no_recent_action = recent_menu.addAction(self.i18n("no_recent_projects"))
            no_recent_action.setEnabled(False)

        menu.addSeparator()
        menu.addAction(self.i18n("save_project"), self._save_project)
        menu.addSeparator()

        lang_menu = menu.addMenu(self.i18n("language"))
        lang_menu.setStyleSheet(ss)
        lang_menu.addAction("English", lambda: self._change_language("en"))
        lang_menu.addAction("Bahasa Indonesia", lambda: self._change_language("id"))

        palette_menu = menu.addMenu(self.i18n("color_palette"))
        palette_menu.setStyleSheet(ss)
        palette_menu.addAction(self.i18n("theme_gold"),   lambda: self._apply_theme("gold"))
        palette_menu.addAction(self.i18n("theme_purple"), lambda: self._apply_theme("purple"))
        palette_menu.addAction(self.i18n("theme_blue"),   lambda: self._apply_theme("blue"))
        palette_menu.addAction(self.i18n("theme_green"),  lambda: self._apply_theme("green"))
        palette_menu.addAction(self.i18n("theme_light"),  lambda: self._apply_theme("light"))
        palette_menu.addSeparator()
        palette_menu.addAction(self.i18n("custom_color"), self._choose_custom_color)

        menu.addSeparator()
        menu.addAction(self.i18n("about_qif"), self._show_about)
        self.btn_file.setMenu(menu)

    def _update_ui_texts(self):
        """Update all UI text labels for current language."""
        self.setWindowTitle(self.i18n("title"))

        self.btn_file.setText(self.i18n("file_menu"))
        self._rebuild_file_menu()

        self.main_nav_tabs.setTabText(0, self.i18n("tab_adjustments"))
        self.main_nav_tabs.setTabText(1, self.i18n("tab_lut"))
        self.main_nav_tabs.setTabText(2, self.i18n("tab_export"))

        self.lbl_pick_images.setText(self.i18n("pick_images"))
        self.btn_add_files.setText(self.i18n("add_files"))
        self.btn_add_folder.setText(self.i18n("add_folder"))
        self.btn_remove.setText(self.i18n("remove_selected"))
        self.btn_clear.setText(self.i18n("clear_all"))
        self.subfolder_check.setText(self.i18n("include_subfolders"))
        self._update_count()

        # Adjustments Tab
        self.conv_resize_title.setText(self.i18n("change_size"))
        self.lbl_width.setText(self.i18n("width"))
        self.lbl_height.setText(self.i18n("height"))
        self.lbl_scale.setText(self.i18n("resize_percent"))

        self._crop_section_title.setText(self.i18n("crop_section"))
        self.crop_radio_none.setText(self.i18n("crop_none"))
        self.crop_radio_same.setText(self.i18n("crop_same_size"))
        self.crop_radio_manual.setText(self.i18n("crop_one_by_one"))

        self.lbl_same_w.setText(self.i18n("crop_width"))
        self.lbl_same_h.setText(self.i18n("crop_height"))
        self.lbl_same_from.setText(self.i18n("crop_from"))

        curr_anchor = self.crop_anchor.currentIndex()
        self.crop_anchor.clear()
        self.crop_anchor.addItems([self.i18n("crop_center"), self.i18n("crop_top_left")])
        self.crop_anchor.setCurrentIndex(max(curr_anchor, 0))

        self.lbl_manual_x.setText(self.i18n("crop_x"))
        self.lbl_manual_y.setText(self.i18n("crop_y"))
        self.lbl_manual_w.setText(self.i18n("crop_width"))
        self.lbl_manual_h.setText(self.i18n("crop_height"))
        self.lbl_manual_shape.setText(self.i18n("crop_shape"))

        curr_aspect = self.crop_aspect.currentIndex()
        self.crop_aspect.clear()
        self.crop_aspect.addItems([
            self.i18n("crop_free"), "1:1", "4:3", "3:2", "16:9", "9:16", "3:4", "2:3",
        ])
        self.crop_aspect.setCurrentIndex(max(curr_aspect, 0))

        self.crop_skip_check.setText(self.i18n("crop_skip"))
        self.lbl_crop_hint.setText(self.i18n("crop_hint"))
        self.crop_prev_btn.setText(f"\u25c4  {self.i18n('crop_previous')}")
        self.crop_next_btn.setText(f"{self.i18n('crop_next')}  \u25ba")

        # LUT Tab
        self._lut_section_title.setText(self.i18n("lut_section"))
        self.lut_radio_none.setText(self.i18n("lut_none"))
        self.lut_radio_same.setText(self.i18n("lut_same_size"))
        self.lut_radio_manual.setText(self.i18n("lut_one_by_one"))

        self.lbl_lut_preset.setText(self.i18n("lut_preset"))
        self.lbl_lut_file.setText(self.i18n("lut_load_file"))
        self.btn_browse_lut.setText(self.i18n("browse"))
        self.lbl_lut_intensity.setText(self.i18n("lut_intensity"))
        self.lut_gen_title.setText(self.i18n("lut_generator"))

        self.lbl_lut_b.setText(self.i18n("lut_brightness"))
        self.lbl_lut_c.setText(self.i18n("lut_contrast"))
        self.lbl_lut_s.setText(self.i18n("lut_saturation"))
        self.lbl_lut_temp.setText(self.i18n("lut_temp"))
        self.lbl_lut_tint.setText(self.i18n("lut_tint"))
        self.lbl_lut_gamma.setText(self.i18n("lut_gamma"))
        self.lbl_lut_hue.setText(self.i18n("lut_hue"))
        self.lbl_lut_r_gain.setText(self.i18n("lut_r_gain"))
        self.lbl_lut_g_gain.setText(self.i18n("lut_g_gain"))
        self.lbl_lut_b_gain.setText(self.i18n("lut_b_gain"))

        self.btn_export_lut.setText(self.i18n("lut_export_cube"))
        self.btn_reset_lut.setText(self.i18n("lut_reset"))
        self.lut_prev_btn.setText(f"\u25c4  {self.i18n('crop_previous')}")
        self.lut_next_btn.setText(f"{self.i18n('crop_next')}  \u25ba")

        # Standalone Export Panel
        self.lbl_export_section.setText(self.i18n("export_section"))
        self.lbl_save_as.setText(self.i18n("save_as"))
        self.lbl_quality.setText(self.i18n("picture_quality"))
        self.lbl_save_to.setText(self.i18n("save_to"))
        self.btn_browse_out.setText(self.i18n("browse"))
        self.btn_export.setText("EXPORT")

        self._update_crop_nav_label()
        self._update_lut_nav_label()

    def _show_about(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("About QIF")
        dlg.setFixedSize(420, 340)
        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {theme.CARD_BG}; }}
            QLabel {{ color: #CCCCCC; }}
            QLabel#aboutTitle {{ color: {theme.GOLD}; font-size: 18pt; font-weight: bold; }}
            QLabel#aboutSubtitle {{ color: #AAAAAA; font-size: 10pt; }}
            QPushButton {{
                background-color: {theme.GOLD}; color: {theme.BLACK_MATTE};
                border: none; border-radius: 6px; padding: 8px 28px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {theme.GOLD_HOVER}; }}
        """)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 24, 28, 20)

        icon_path = _PROJECT_ROOT / "monolight.png"
        if icon_path.exists():
            icon_label = QLabel()
            px = QPixmap(str(icon_path)).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(px)
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)

        title = QLabel("QIF - Quick Image Formatting")
        title.setObjectName("aboutTitle")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        version = QLabel("Image converter, resizer & cropper")
        version.setObjectName("aboutSubtitle")
        version.setAlignment(Qt.AlignCenter)
        layout.addWidget(version)
        layout.addSpacing(8)

        author = QLabel("Made by <b>Wira</b> (PWira)")
        author.setAlignment(Qt.AlignCenter)
        layout.addWidget(author)

        license_lbl = QLabel("All right reserved")
        license_lbl.setObjectName("aboutSubtitle")
        license_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(license_lbl)
        layout.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dlg.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignCenter)
        dlg.exec()

    def _log(self, msg: str, tag: str = ""):
        self._signals.log.emit(msg, tag)

    def _start_progress_dialog(self, title_text):
        for sig in (self._signals.log, self._signals.progress, self._signals.finished):
            try:
                sig.disconnect()
            except Exception:
                pass
        dlg = ProgressDialog(self, title_text=title_text)
        self._signals.log.connect(dlg.append_log)
        self._signals.progress.connect(dlg.set_progress)
        self._signals.finished.connect(lambda: dlg.on_finished(self.i18n("info_done")))
        dlg.show()
        return dlg

    # ---- Layout builders ----

    def _build_header(self, layout):
        header = QFrame()
        header.setObjectName("headerPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)

        self.btn_file = QPushButton()
        self.btn_file.setObjectName("settingsBtn")
        header_layout.addWidget(self.btn_file)
        header_layout.addStretch(1)

        layout.addWidget(header)

    def _build_sidebar(self, widget):
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.lbl_pick_images = QLabel()

        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)
        self.btn_add_files  = QPushButton()
        self.btn_add_folder = QPushButton()
        self.btn_remove     = QPushButton()
        self.btn_clear      = QPushButton()
        self.btn_add_files.clicked.connect(self._add_files)
        self.btn_add_folder.clicked.connect(self._add_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_all)
        btn_grid.addWidget(self.btn_add_files,  0, 0)
        btn_grid.addWidget(self.btn_add_folder, 0, 1)
        btn_grid.addWidget(self.btn_remove,     1, 0)
        btn_grid.addWidget(self.btn_clear,      1, 1)
        layout.addLayout(btn_grid)

        self.subfolder_check = QCheckBox()
        layout.addWidget(self.subfolder_check)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        self.file_list.setMinimumWidth(180)
        layout.addWidget(self.file_list, stretch=1)

        self.count_label = QLabel()
        self.count_label.setObjectName("dimLabel")
        layout.addWidget(self.count_label)

    def _build_unified_options(self, widget):
        """Build the unified options panel with Photoshop-style tabs (Adjustments / LUT) and standalone Export panel."""
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(10)

        # 1. Top Navigation Tab Bar (Photoshop style: Adjustments, LUT, Export)
        self.main_nav_tabs = QTabWidget()
        self.tab_adjustments = QWidget()
        self.tab_lut = QWidget()
        self.tab_export = QWidget()

        self.main_nav_tabs.addTab(self.tab_adjustments, "Adjustments")
        self.main_nav_tabs.addTab(self.tab_lut, "LUT")
        self.main_nav_tabs.addTab(self.tab_export, "Export")
        main_layout.addWidget(self.main_nav_tabs, stretch=1)

        # ── Build Tab 1: Adjustments ─────────────────────
        adj_layout = QVBoxLayout(self.tab_adjustments)
        adj_layout.setContentsMargins(8, 12, 8, 8)
        adj_layout.setSpacing(12)

        # Resize section
        self.conv_resize_title = QLabel()
        self.conv_resize_title.setObjectName("headerLabel")
        adj_layout.addWidget(self.conv_resize_title)

        rg = QGridLayout()
        rg.setSpacing(6)
        self.lbl_width  = QLabel()
        self.conv_width = PlusMinusSpinBox()
        self.conv_width.setRange(0, 99999)
        self.conv_width.setSpecialValueText("\u2014")
        self.conv_width.setSuffix(" px")
        self.lbl_height  = QLabel()
        self.conv_height = PlusMinusSpinBox()
        self.conv_height.setRange(0, 99999)
        self.conv_height.setSpecialValueText("\u2014")
        self.conv_height.setSuffix(" px")
        self.lbl_scale  = QLabel()
        self.conv_scale = PlusMinusSpinBox()
        self.conv_scale.setRange(0, 10000)
        self.conv_scale.setSpecialValueText("\u2014")
        self.conv_scale.setSuffix(" %")
        rg.addWidget(self.lbl_width,  0, 0); rg.addWidget(self.conv_width,  0, 1)
        rg.addWidget(self.lbl_height, 1, 0); rg.addWidget(self.conv_height, 1, 1)
        rg.addWidget(self.lbl_scale,  2, 0); rg.addWidget(self.conv_scale,  2, 1)
        adj_layout.addLayout(rg)

        # Crop section
        adj_layout.addWidget(Separator())
        self._crop_section_title = QLabel()
        self._crop_section_title.setObjectName("headerLabel")
        adj_layout.addWidget(self._crop_section_title)

        self.crop_mode_group  = QButtonGroup(self)
        self.crop_radio_none   = QRadioButton()
        self.crop_radio_same   = QRadioButton()
        self.crop_radio_manual = QRadioButton()
        self.crop_radio_none.setChecked(True)
        self.crop_mode_group.addButton(self.crop_radio_none,   self.CROP_NONE)
        self.crop_mode_group.addButton(self.crop_radio_same,   self.CROP_SAME)
        self.crop_mode_group.addButton(self.crop_radio_manual, self.CROP_MANUAL)
        self.crop_mode_group.setExclusive(True)
        self.crop_mode_group.idToggled.connect(self._on_crop_mode_changed)

        mc = QVBoxLayout()
        mc.setSpacing(4)
        mc.addWidget(self.crop_radio_none)
        mc.addWidget(self.crop_radio_same)
        mc.addWidget(self.crop_radio_manual)
        adj_layout.addLayout(mc)

        # Same-size sub-panel
        self.crop_same_panel = QWidget()
        sl = QVBoxLayout(self.crop_same_panel)
        sl.setContentsMargins(0, 4, 0, 0)
        sl.setSpacing(6)
        sg = QGridLayout()
        sg.setSpacing(6)
        self.lbl_same_w  = QLabel()
        self.crop_same_w = PlusMinusSpinBox()
        self.crop_same_w.setRange(1, 99999)
        self.crop_same_w.setValue(800)
        self.crop_same_w.setSuffix(" px")
        self.lbl_same_h  = QLabel()
        self.crop_same_h = PlusMinusSpinBox()
        self.crop_same_h.setRange(1, 99999)
        self.crop_same_h.setValue(600)
        self.crop_same_h.setSuffix(" px")
        self.lbl_same_from = QLabel()
        self.crop_anchor = QComboBox()
        self.crop_anchor.addItems(["", ""])
        sg.addWidget(self.lbl_same_w,    0, 0); sg.addWidget(self.crop_same_w,   0, 1)
        sg.addWidget(self.lbl_same_h,    1, 0); sg.addWidget(self.crop_same_h,   1, 1)
        sg.addWidget(self.lbl_same_from, 2, 0); sg.addWidget(self.crop_anchor,   2, 1)
        sl.addLayout(sg)
        self.crop_same_panel.setVisible(False)
        adj_layout.addWidget(self.crop_same_panel)

        # Manual crop sub-panel
        self.crop_manual_panel = QWidget()
        ml = QVBoxLayout(self.crop_manual_panel)
        ml.setContentsMargins(0, 4, 0, 0)
        ml.setSpacing(6)
        cg = QGridLayout()
        cg.setSpacing(6)
        self.lbl_manual_x     = QLabel()
        self.crop_x           = PlusMinusSpinBox()
        self.crop_x.setRange(0, 99999)
        self.lbl_manual_y     = QLabel()
        self.crop_y           = PlusMinusSpinBox()
        self.crop_y.setRange(0, 99999)
        self.lbl_manual_w     = QLabel()
        self.crop_w           = PlusMinusSpinBox()
        self.crop_w.setRange(1, 99999)
        self.crop_w.setValue(800)
        self.lbl_manual_h     = QLabel()
        self.crop_h           = PlusMinusSpinBox()
        self.crop_h.setRange(1, 99999)
        self.crop_h.setValue(600)
        self.lbl_manual_shape = QLabel()
        self.crop_aspect      = QComboBox()
        self.crop_aspect.addItems(["", "1:1", "4:3", "3:2", "16:9", "9:16", "3:4", "2:3"])
        cg.addWidget(self.lbl_manual_x,     0, 0); cg.addWidget(self.crop_x,      0, 1)
        cg.addWidget(self.lbl_manual_y,     1, 0); cg.addWidget(self.crop_y,      1, 1)
        cg.addWidget(self.lbl_manual_w,     2, 0); cg.addWidget(self.crop_w,      2, 1)
        cg.addWidget(self.lbl_manual_h,     3, 0); cg.addWidget(self.crop_h,      3, 1)
        cg.addWidget(self.lbl_manual_shape, 4, 0); cg.addWidget(self.crop_aspect, 4, 1)
        ml.addLayout(cg)
        self.crop_skip_check = QCheckBox()
        ml.addWidget(self.crop_skip_check)
        self.lbl_crop_hint = QLabel()
        self.lbl_crop_hint.setObjectName("dimLabel")
        self.lbl_crop_hint.setWordWrap(True)
        ml.addWidget(self.lbl_crop_hint)
        nav_row = QHBoxLayout()
        self.crop_prev_btn = QPushButton()
        self.crop_prev_btn.clicked.connect(self._crop_go_prev)
        self.crop_nav_label = QLabel("")
        self.crop_nav_label.setAlignment(Qt.AlignCenter)
        self.crop_next_btn = QPushButton()
        self.crop_next_btn.clicked.connect(self._crop_go_next)
        nav_row.addWidget(self.crop_prev_btn)
        nav_row.addWidget(self.crop_nav_label)
        nav_row.addWidget(self.crop_next_btn)
        ml.addLayout(nav_row)
        self.crop_manual_panel.setVisible(False)
        adj_layout.addWidget(self.crop_manual_panel)
        adj_layout.addStretch(1)

        # ── Build Tab 2: LUT ─────────────────────────────
        lut_layout = QVBoxLayout(self.tab_lut)
        lut_layout.setContentsMargins(8, 12, 8, 8)
        lut_layout.setSpacing(10)

        self._lut_section_title = QLabel()
        self._lut_section_title.setObjectName("headerLabel")
        lut_layout.addWidget(self._lut_section_title)

        self.lut_mode_group  = QButtonGroup(self)
        self.lut_radio_none   = QRadioButton()
        self.lut_radio_same   = QRadioButton()
        self.lut_radio_manual = QRadioButton()
        self.lut_radio_none.setChecked(True)
        self.lut_mode_group.addButton(self.lut_radio_none,   self.LUT_NONE)
        self.lut_mode_group.addButton(self.lut_radio_same,   self.LUT_SAME)
        self.lut_mode_group.addButton(self.lut_radio_manual, self.LUT_MANUAL)
        self.lut_mode_group.setExclusive(True)

        lmc = QVBoxLayout()
        lmc.setSpacing(4)
        lmc.addWidget(self.lut_radio_none)
        lmc.addWidget(self.lut_radio_same)
        lmc.addWidget(self.lut_radio_manual)
        lut_layout.addLayout(lmc)

        # Container panel when LUT is active
        self.lut_controls_panel = QWidget()
        lcl = QVBoxLayout(self.lut_controls_panel)
        lcl.setContentsMargins(0, 4, 0, 0)
        lcl.setSpacing(8)

        # Presets dropdown
        self.lbl_lut_preset = QLabel()
        lcl.addWidget(self.lbl_lut_preset)
        self.lut_preset_combo = QComboBox()
        self.lut_preset_combo.addItem(self.i18n("lut_preset_none"))
        for preset_name in PRESET_LUT_SETTINGS.keys():
            self.lut_preset_combo.addItem(preset_name)
        lcl.addWidget(self.lut_preset_combo)

        # File loader
        self.lbl_lut_file = QLabel()
        lcl.addWidget(self.lbl_lut_file)
        lut_file_row = QHBoxLayout()
        self.lut_file_edit = QLineEdit()
        self.lut_file_edit.setReadOnly(True)
        self.lut_file_edit.setPlaceholderText(self.i18n("lut_no_file"))
        self.btn_browse_lut = QPushButton()
        lut_file_row.addWidget(self.lut_file_edit, stretch=1)
        lut_file_row.addWidget(self.btn_browse_lut)
        lcl.addLayout(lut_file_row)

        # Intensity slider
        self.lbl_lut_intensity = QLabel()
        lcl.addWidget(self.lbl_lut_intensity)
        intensity_row = QHBoxLayout()
        self.lut_intensity_slider = QSlider(Qt.Horizontal)
        self.lut_intensity_slider.setRange(0, 100)
        self.lut_intensity_slider.setValue(100)
        self.lut_intensity_val_label = QLabel("100%")
        self.lut_intensity_val_label.setFixedWidth(40)
        self.lut_intensity_slider.valueChanged.connect(
            lambda v: self.lut_intensity_val_label.setText(f"{v}%")
        )
        intensity_row.addWidget(self.lut_intensity_slider)
        intensity_row.addWidget(self.lut_intensity_val_label)
        lcl.addLayout(intensity_row)

        lcl.addWidget(Separator())

        # Generator Group (Sliders for custom LUT design)
        self.lut_gen_title = QLabel()
        self.lut_gen_title.setObjectName("headerLabel")
        lcl.addWidget(self.lut_gen_title)

        gen_vbox = QVBoxLayout()
        gen_vbox.setSpacing(4)

        def _add_gen_slider(lbl_widget, slider_name, val_label_name, min_v, max_v, init_v, is_float=False):
            item_box = QVBoxLayout()
            item_box.setSpacing(1)
            item_box.setContentsMargins(0, 1, 0, 2)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(4)
            v_lbl = QLabel(f"{init_v/100:.2f}" if is_float else str(init_v))
            v_lbl.setFixedWidth(36)
            v_lbl.setAlignment(Qt.AlignCenter)
            v_lbl.setStyleSheet(f"""
                QLabel {{
                    background: #252526;
                    color: {theme.TEXT_PRIMARY};
                    border: 1px solid {theme.BORDER};
                    border-radius: 2px;
                    padding: 0px 2px;
                    font-size: 8pt;
                    font-family: monospace;
                }}
            """)
            top_row.addWidget(lbl_widget)
            top_row.addStretch(1)
            top_row.addWidget(v_lbl)
            item_box.addLayout(top_row)

            slider = QSlider(Qt.Horizontal)
            slider.setObjectName(slider_name)
            slider.setRange(min_v, max_v)
            slider.setValue(init_v)
            slider.setFixedHeight(14)
            if is_float:
                slider.valueChanged.connect(lambda v: v_lbl.setText(f"{v/100:.2f}"))
            else:
                slider.valueChanged.connect(lambda v: v_lbl.setText(str(v)))

            item_box.addWidget(slider)
            setattr(self, slider_name, slider)
            setattr(self, val_label_name, v_lbl)
            gen_vbox.addLayout(item_box)

        self.lbl_lut_b = QLabel(); _add_gen_slider(self.lbl_lut_b, "lut_gen_b_slider", "lut_gen_b_lbl", -100, 100, 0)
        self.lbl_lut_c = QLabel(); _add_gen_slider(self.lbl_lut_c, "lut_gen_c_slider", "lut_gen_c_lbl", -100, 100, 0)
        self.lbl_lut_s = QLabel(); _add_gen_slider(self.lbl_lut_s, "lut_gen_s_slider", "lut_gen_s_lbl", -100, 100, 0)
        self.lbl_lut_temp = QLabel(); _add_gen_slider(self.lbl_lut_temp, "lut_gen_temp_slider", "lut_gen_temp_lbl", -100, 100, 0)
        self.lbl_lut_tint = QLabel(); _add_gen_slider(self.lbl_lut_tint, "lut_gen_tint_slider", "lut_gen_tint_lbl", -100, 100, 0)
        self.lbl_lut_gamma = QLabel(); _add_gen_slider(self.lbl_lut_gamma, "lut_gen_gamma_slider", "lut_gen_gamma_lbl", 20, 250, 100, is_float=True)
        self.lbl_lut_hue = QLabel(); _add_gen_slider(self.lbl_lut_hue, "lut_gen_hue_slider", "lut_gen_hue_lbl", -180, 180, 0)
        self.lbl_lut_r_gain = QLabel(); _add_gen_slider(self.lbl_lut_r_gain, "lut_gen_r_slider", "lut_gen_r_lbl", 0, 200, 100, is_float=True)
        self.lbl_lut_g_gain = QLabel(); _add_gen_slider(self.lbl_lut_g_gain, "lut_gen_g_slider", "lut_gen_g_lbl", 0, 200, 100, is_float=True)
        self.lbl_lut_b_gain = QLabel(); _add_gen_slider(self.lbl_lut_b_gain, "lut_gen_b_gain_slider", "lut_gen_b_gain_lbl", 0, 200, 100, is_float=True)

        lcl.addLayout(gen_vbox)

        gen_btn_row = QHBoxLayout()
        self.btn_export_lut = QPushButton()
        self.btn_reset_lut = QPushButton()
        gen_btn_row.addWidget(self.btn_export_lut)
        gen_btn_row.addWidget(self.btn_reset_lut)
        lcl.addLayout(gen_btn_row)

        # Per-image navigation for LUT
        self.lut_manual_nav_panel = QWidget()
        lnl = QHBoxLayout(self.lut_manual_nav_panel)
        lnl.setContentsMargins(0, 4, 0, 0)
        self.lut_prev_btn = QPushButton()
        self.lut_nav_label = QLabel("")
        self.lut_nav_label.setAlignment(Qt.AlignCenter)
        self.lut_next_btn = QPushButton()
        lnl.addWidget(self.lut_prev_btn)
        lnl.addWidget(self.lut_nav_label)
        lnl.addWidget(self.lut_next_btn)
        self.lut_manual_nav_panel.setVisible(False)
        lcl.addWidget(self.lut_manual_nav_panel)

        self.lut_controls_panel.setVisible(False)
        lut_layout.addWidget(self.lut_controls_panel)
        lut_layout.addStretch(1)

        # ── 3. Build Tab 3: Export ────────────────────────
        exp_layout = QVBoxLayout(self.tab_export)
        exp_layout.setContentsMargins(8, 12, 8, 8)
        exp_layout.setSpacing(10)

        self.lbl_export_section = QLabel("Export Settings")
        self.lbl_export_section.setObjectName("headerLabel")
        exp_layout.addWidget(self.lbl_export_section)

        # Format & Quality
        self.lbl_save_as = QLabel()
        exp_layout.addWidget(self.lbl_save_as)
        self.conv_format = QComboBox()
        self.conv_format.addItems(OUTPUT_FORMATS)
        self.conv_format.setCurrentText("PNG")
        exp_layout.addWidget(self.conv_format)

        self.lbl_quality = QLabel()
        exp_layout.addWidget(self.lbl_quality)
        self.conv_quality_slider = QSlider(Qt.Horizontal)
        self.conv_quality_slider.setRange(1, 100)
        self.conv_quality_slider.setValue(85)
        self.conv_quality_label = QLabel("85")
        self.conv_quality_label.setFixedWidth(24)
        self.conv_quality_slider.valueChanged.connect(
            lambda v: self.conv_quality_label.setText(str(v))
        )
        q_row = QHBoxLayout()
        q_row.addWidget(self.conv_quality_slider)
        q_row.addWidget(self.conv_quality_label)
        exp_layout.addLayout(q_row)

        # Output directory
        self.lbl_save_to = QLabel()
        exp_layout.addWidget(self.lbl_save_to)
        out_row = QHBoxLayout()
        self.output_dir = QLineEdit()
        self.btn_browse_out = QPushButton()
        self.btn_browse_out.clicked.connect(self._browse_output)
        out_row.addWidget(self.output_dir, stretch=1)
        out_row.addWidget(self.btn_browse_out)
        exp_layout.addLayout(out_row)

        exp_layout.addStretch(1)

        # EXPORT button
        self.btn_export = QPushButton()
        self.btn_export.setObjectName("primaryBtn")
        self.btn_export.clicked.connect(self._run_export)
        exp_layout.addWidget(self.btn_export)

    # ---- Handlers ----

    def _on_crop_mode_changed(self, id_: int, checked: bool):
        """Updates viewport and sub-panels when a crop mode radio is toggled."""
        if not checked:
            return
        self.crop_same_panel.setVisible(id_ == self.CROP_SAME)
        self.crop_manual_panel.setVisible(id_ == self.CROP_MANUAL)
        vp_index = {self.CROP_NONE: 0, self.CROP_SAME: 1, self.CROP_MANUAL: 2}.get(id_, 0)
        self.viewport_stack.setCurrentIndex(vp_index)
        row = self.file_list.currentRow()
        if 0 <= row < self.file_list.count():
            path = self.file_list.item(row).data(Qt.UserRole)
            if id_ == self.CROP_NONE:
                self._load_convert_preview(path)
            elif id_ == self.CROP_SAME:
                self._crop_same_load_preview(path)
            elif id_ == self.CROP_MANUAL:
                self._crop_load_image(row)

    def _on_lut_mode_changed(self, id_: int, checked: bool):
        """Updates UI and viewport when LUT mode changes."""
        if not checked:
            return
        self._lut_mode = id_
        self.lut_controls_panel.setVisible(id_ != self.LUT_NONE)
        self.lut_manual_nav_panel.setVisible(id_ == self.LUT_MANUAL)

        if id_ == self.LUT_NONE:
            self._lut_same_obj = None
            self._lut_same_file = None
            self._lut_same_preset = None
            row = self.file_list.currentRow()
            if row in self._lut_per_image_data:
                self._lut_per_image_data[row]["obj"] = None
        elif id_ == self.LUT_MANUAL:
            row = self.file_list.currentRow()
            if row >= 0:
                self._lut_load_image_settings(row)
        else:
            self._update_active_lut_object()

        self._refresh_current_preview(retain_zoom=True)
        self._auto_save_temp()

    def _on_lut_preset_changed(self, index: int):
        if self._lut_updating:
            return
        preset_name = self.lut_preset_combo.currentText()
        if index == 0 or preset_name == self.i18n("lut_preset_none"):
            self._lut_updating = True
            self._reset_lut_generator_ui()
            self._lut_updating = False
            self._set_active_lut_object(None, file_path="", preset_name="")
            self._refresh_current_preview(retain_zoom=True)
            self._auto_save_temp()
            return

        if preset_name in PRESET_LUT_SETTINGS:
            settings = PRESET_LUT_SETTINGS[preset_name]
            self._lut_updating = True
            self.lut_gen_b_slider.setValue(settings.get("brightness", 0))
            self.lut_gen_c_slider.setValue(settings.get("contrast", 0))
            self.lut_gen_s_slider.setValue(settings.get("saturation", 0))
            self.lut_gen_temp_slider.setValue(settings.get("temperature", 0))
            self.lut_gen_tint_slider.setValue(settings.get("tint", 0))
            self.lut_gen_gamma_slider.setValue(int(settings.get("gamma", 1.0) * 100))
            self.lut_gen_hue_slider.setValue(settings.get("hue_shift", 0))
            self.lut_gen_r_slider.setValue(int(settings.get("r_gain", 1.0) * 100))
            self.lut_gen_g_slider.setValue(int(settings.get("g_gain", 1.0) * 100))
            self.lut_gen_b_gain_slider.setValue(int(settings.get("b_gain", 1.0) * 100))
            self.lut_file_edit.clear()
            self._lut_updating = False
            self._update_active_lut_object()
            self._refresh_current_preview(retain_zoom=True)
            self._auto_save_temp()

    def _browse_lut_file(self):
        filter_str = f"{self.i18n('lut_files')} (*.cube *.3dl);;{self.i18n('all_files')} (*.*)"
        file_path, _ = QFileDialog.getOpenFileName(self, self.i18n("lut_load_file"), "", filter_str)
        if file_path:
            try:
                lut_obj = load_lut_file(file_path)
                self.lut_file_edit.setText(Path(file_path).name)
                self._lut_updating = True
                self.lut_preset_combo.setCurrentIndex(0)
                self._lut_updating = False
                self._set_active_lut_object(lut_obj, file_path=file_path)
                self._refresh_current_preview()
                self._auto_save_temp()
            except Exception as e:
                QMessageBox.critical(self, self.i18n("error_title"), f"Failed to load LUT: {e}")

    def _on_lut_intensity_changed(self, value: int):
        if self._lut_updating:
            return
        intensity = value / 100.0
        if self._lut_mode == self.LUT_SAME:
            self._lut_same_intensity = intensity
        elif self._lut_mode == self.LUT_MANUAL:
            row = self.file_list.currentRow()
            if row >= 0:
                if row not in self._lut_per_image_data:
                    self._lut_per_image_data[row] = {}
                self._lut_per_image_data[row]["intensity"] = intensity
        self._refresh_current_preview()
        self._auto_save_temp()

    def _on_lut_generator_slider_changed(self, value: int):
        if self._lut_updating:
            return
        self._lut_updating = True
        self.lut_preset_combo.setCurrentIndex(0)
        self.lut_file_edit.clear()
        self._lut_updating = False
        self._update_active_lut_object()
        self._refresh_current_preview()
        self._auto_save_temp()

    def _reset_lut_generator(self):
        self._lut_updating = True
        self.lut_gen_b_slider.setValue(0)
        self.lut_gen_c_slider.setValue(0)
        self.lut_gen_s_slider.setValue(0)
        self.lut_gen_temp_slider.setValue(0)
        self.lut_gen_tint_slider.setValue(0)
        self.lut_gen_gamma_slider.setValue(100)
        self.lut_gen_hue_slider.setValue(0)
        self.lut_gen_r_slider.setValue(100)
        self.lut_gen_g_slider.setValue(100)
        self.lut_gen_b_gain_slider.setValue(100)
        self.lut_preset_combo.setCurrentIndex(0)
        self.lut_file_edit.clear()
        self._lut_updating = False
        self._update_active_lut_object()
        self._refresh_current_preview()
        self._auto_save_temp()

    def _export_lut_file(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, self.i18n("lut_export_cube"), "custom_lut.cube", "Adobe 3D LUT (*.cube)"
        )
        if filename:
            if not filename.endswith(".cube"):
                filename += ".cube"
            try:
                gen = self._get_current_generator_settings()
                export_lut_to_cube(filename, **gen, title=Path(filename).stem)
                QMessageBox.information(self, self.i18n("info_done"), f"LUT saved: {Path(filename).name}")
            except Exception as e:
                QMessageBox.critical(self, self.i18n("error_title"), f"Failed to export LUT: {e}")

    def _get_current_generator_settings(self) -> dict:
        return {
            "brightness": self.lut_gen_b_slider.value(),
            "contrast": self.lut_gen_c_slider.value(),
            "saturation": self.lut_gen_s_slider.value(),
            "temperature": self.lut_gen_temp_slider.value(),
            "tint": self.lut_gen_tint_slider.value(),
            "gamma": self.lut_gen_gamma_slider.value() / 100.0,
            "hue_shift": self.lut_gen_hue_slider.value(),
            "r_gain": self.lut_gen_r_slider.value() / 100.0,
            "g_gain": self.lut_gen_g_slider.value() / 100.0,
            "b_gain": self.lut_gen_b_gain_slider.value() / 100.0,
        }

    def _update_active_lut_object(self):
        gen = self._get_current_generator_settings()
        lut_obj = generate_lut_from_settings(**gen)
        preset_name = self.lut_preset_combo.currentText()
        file_path = self.lut_file_edit.text()
        self._set_active_lut_object(lut_obj, file_path=file_path, preset_name=preset_name, gen_settings=gen)

    def _set_active_lut_object(self, lut_obj, file_path: str = "", preset_name: str = "", gen_settings: dict = None):
        intensity = self.lut_intensity_slider.value() / 100.0
        if gen_settings is None:
            gen_settings = self._get_current_generator_settings()

        if self._lut_mode == self.LUT_SAME:
            self._lut_same_obj = lut_obj
            self._lut_same_file = file_path
            self._lut_same_preset = preset_name
            self._lut_same_intensity = intensity
            self._lut_same_settings = gen_settings
        elif self._lut_mode == self.LUT_MANUAL:
            row = self.file_list.currentRow()
            if row >= 0:
                self._lut_per_image_data[row] = {
                    "obj": lut_obj,
                    "file": file_path,
                    "preset": preset_name,
                    "intensity": intensity,
                    "settings": gen_settings,
                }

    def _get_active_lut(self, row: int = -1) -> Tuple[Optional[object], float]:
        if self._lut_mode == self.LUT_NONE:
            return None, 1.0
        elif self._lut_mode == self.LUT_SAME:
            return self._lut_same_obj, self._lut_same_intensity
        elif self._lut_mode == self.LUT_MANUAL:
            if row < 0:
                row = self.file_list.currentRow()
            if row in self._lut_per_image_data:
                d = self._lut_per_image_data[row]
                return d.get("obj"), d.get("intensity", 1.0)
        return None, 1.0

    def _lut_go_prev(self):
        row = self.file_list.currentRow()
        if row > 0:
            self.file_list.setCurrentRow(row - 1)

    def _lut_go_next(self):
        row = self.file_list.currentRow()
        if row < self.file_list.count() - 1:
            self.file_list.setCurrentRow(row + 1)

    def _lut_load_image_settings(self, index: int):
        if index < 0 or index >= self.file_list.count():
            return
        self._update_lut_nav_label()
        self.lut_prev_btn.setEnabled(index > 0)
        self.lut_next_btn.setEnabled(index < self.file_list.count() - 1)
        self._lut_updating = True
        if index in self._lut_per_image_data:
            d = self._lut_per_image_data[index]
            file_p = d.get("file", "")
            preset_p = d.get("preset", "")
            intensity = int(d.get("intensity", 1.0) * 100)
            settings = d.get("settings", {})

            self.lut_file_edit.setText(file_p)
            if preset_p and preset_p in PRESET_LUT_SETTINGS:
                idx = self.lut_preset_combo.findText(preset_p)
                self.lut_preset_combo.setCurrentIndex(max(0, idx))
            else:
                self.lut_preset_combo.setCurrentIndex(0)
            self.lut_intensity_slider.setValue(intensity)

            self.lut_gen_b_slider.setValue(settings.get("brightness", 0))
            self.lut_gen_c_slider.setValue(settings.get("contrast", 0))
            self.lut_gen_s_slider.setValue(settings.get("saturation", 0))
            self.lut_gen_temp_slider.setValue(settings.get("temperature", 0))
            self.lut_gen_tint_slider.setValue(settings.get("tint", 0))
            self.lut_gen_gamma_slider.setValue(int(settings.get("gamma", 1.0) * 100))
            self.lut_gen_hue_slider.setValue(settings.get("hue_shift", 0))
            self.lut_gen_r_slider.setValue(int(settings.get("r_gain", 1.0) * 100))
            self.lut_gen_g_slider.setValue(int(settings.get("g_gain", 1.0) * 100))
            self.lut_gen_b_gain_slider.setValue(int(settings.get("b_gain", 1.0) * 100))
        else:
            self._reset_lut_generator_ui()
        self._lut_updating = False

    def _reset_lut_generator_ui(self):
        self.lut_file_edit.clear()
        self.lut_preset_combo.setCurrentIndex(0)
        self.lut_intensity_slider.setValue(100)
        self.lut_gen_b_slider.setValue(0)
        self.lut_gen_c_slider.setValue(0)
        self.lut_gen_s_slider.setValue(0)
        self.lut_gen_temp_slider.setValue(0)
        self.lut_gen_tint_slider.setValue(0)
        self.lut_gen_gamma_slider.setValue(100)
        self.lut_gen_hue_slider.setValue(0)
        self.lut_gen_r_slider.setValue(100)
        self.lut_gen_g_slider.setValue(100)
        self.lut_gen_b_gain_slider.setValue(100)

    def _update_lut_nav_label(self):
        row = self.file_list.currentRow()
        total = self.file_list.count()
        if row >= 0 and total > 0:
            self.lut_nav_label.setText(self.i18n("crop_image_n_of", current=row + 1, total=total))
        else:
            self.lut_nav_label.setText("")

    def _refresh_current_preview(self, retain_zoom: bool = True):
        row = self.file_list.currentRow()
        if 0 <= row < self.file_list.count():
            path = self.file_list.item(row).data(Qt.UserRole)
            mode = self.crop_mode_group.checkedId()
            if mode == self.CROP_NONE:
                self._load_convert_preview(path, retain_zoom=retain_zoom)
            elif mode == self.CROP_SAME:
                self._crop_same_load_preview(path, retain_zoom=retain_zoom)
            elif mode == self.CROP_MANUAL:
                self._crop_load_image(row, retain_zoom=retain_zoom)

    def _on_file_selected(self, row: int):
        if row < 0 or row >= self.file_list.count():
            self._clear_viewport()
            return

        prev_row = getattr(self, "_current_file_row", None)
        if prev_row is not None and prev_row != row:
            curr_view = self.viewport_stack.currentWidget()
            if hasattr(curr_view, "transform") and hasattr(curr_view, "_pm_item") and curr_view._pm_item:
                self._view_transforms[prev_row] = (
                    curr_view.transform(),
                    curr_view.horizontalScrollBar().value(),
                    curr_view.verticalScrollBar().value()
                )

        self._current_file_row = row
        path = self.file_list.item(row).data(Qt.UserRole)
        if self._lut_mode == self.LUT_MANUAL:
            self._lut_load_image_settings(row)

        saved_state = self._view_transforms.get(row)
        retain = saved_state is not None

        mode = self.crop_mode_group.checkedId()
        if mode == self.CROP_NONE:
            self._load_convert_preview(path, retain_zoom=retain)
            curr_view = self.convert_preview
        elif mode == self.CROP_SAME:
            self._crop_same_load_preview(path, retain_zoom=retain)
            curr_view = self.crop_same_view
        elif mode == self.CROP_MANUAL:
            self._crop_load_image(row, retain_zoom=retain)
            curr_view = self.crop_manual_view

        if saved_state:
            tr, h_val, v_val = saved_state
            curr_view.setTransform(tr)
            curr_view.horizontalScrollBar().setValue(h_val)
            curr_view.verticalScrollBar().setValue(v_val)

    def _clear_viewport(self):
        self.convert_preview.clear_image()
        self.crop_same_view.clear_image()
        self.crop_manual_view.clear_image()
        self.crop_nav_label.setText("")
        self.lut_nav_label.setText("")

    def _get_preview_image(self, path: str, max_dim: int = 960) -> Image.Image:
        if path not in self._preview_cache:
            img = open_image(Path(path))
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
                img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
            self._preview_cache[path] = img
        return self._preview_cache[path].copy()

    def _load_convert_preview(self, path: str, retain_zoom: bool = False):
        try:
            row = self.file_list.currentRow()
            img = self._get_preview_image(path)
            lut_obj, intensity = self._get_active_lut(row)
            if lut_obj:
                img = apply_lut(img, lut_obj, intensity)
            self.convert_preview.load_image(img, retain_zoom=retain_zoom)
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    # ---- File management ----

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, self.i18n("add_files"), "", file_filter_string(self.i18n))
        for f in files:
            self._add_path(f)
        self._update_count()
        self._auto_load_preview()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.i18n("add_folder"))
        if not folder:
            return
        recursive = self.subfolder_check.isChecked()
        pattern = "**/*" if recursive else "*"
        try:
            for f in sorted(Path(folder).glob(pattern)):
                if f.is_file() and f.suffix.lower() in INPUT_EXTS:
                    self._add_path(str(f))
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  Error reading folder: {e}", "err")
        self._update_count()
        self._auto_load_preview()

    def _add_path(self, path: str):
        if path in self._files:
            return
        self._files.append(path)
        item = QListWidgetItem()
        p = Path(path)
        try:
            img = Image.open(path)
            w, h = img.size
            img.close()
            item.setText(f"{p.name}   ({w}\u00d7{h})")
        except Exception:
            item.setText(p.name)
        item.setData(Qt.UserRole, path)
        self.file_list.addItem(item)
        self._auto_save_temp()

    def _remove_selected(self):
        selected = self.file_list.selectedItems()
        if not selected:
            return
        if self.crop_radio_manual.isChecked():
            self._crop_save_current_settings()
        self._crop_index = None
        rows = sorted([self.file_list.row(i) for i in selected], reverse=True)
        for row in rows:
            self.file_list.takeItem(row)
            if row < len(self._files):
                self._files.pop(row)
            if row in self._crop_data:
                del self._crop_data[row]
            if row in self._lut_per_image_data:
                del self._lut_per_image_data[row]
        for r in rows:
            tmp_crop = {}
            for idx, val in self._crop_data.items():
                if idx < r:
                    tmp_crop[idx] = val
                elif idx > r:
                    tmp_crop[idx - 1] = val
            self._crop_data = tmp_crop

            tmp_lut = {}
            for idx, val in self._lut_per_image_data.items():
                if idx < r:
                    tmp_lut[idx] = val
                elif idx > r:
                    tmp_lut[idx - 1] = val
            self._lut_per_image_data = tmp_lut

        self._update_count()
        self._auto_load_preview()
        self._auto_save_temp()

    def _clear_all(self):
        self._crop_index = None
        self.file_list.clear()
        self._files.clear()
        self._crop_data.clear()
        self._lut_per_image_data.clear()
        self._preview_cache.clear()
        self._clear_viewport()
        self._update_count()
        self._auto_save_temp()

    def _update_count(self):
        count = self.file_list.count()
        if count == 0:
            self.count_label.setText(self.i18n("no_files"))
        else:
            self.count_label.setText(f"{count} {self.i18n('files_in_list')}")

    def _auto_load_preview(self):
        if self.file_list.count() > 0 and self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, self.i18n("save_to"))
        if folder:
            self.output_dir.setText(folder)

    # ---- Crop helpers ----

    def _crop_go_prev(self):
        row = self.file_list.currentRow()
        if row > 0:
            self._crop_save_current_settings()
            self.file_list.setCurrentRow(row - 1)

    def _crop_go_next(self):
        row = self.file_list.currentRow()
        if row < self.file_list.count() - 1:
            self._crop_save_current_settings()
            self.file_list.setCurrentRow(row + 1)

    def _crop_save_current_settings(self):
        row = self.file_list.currentRow()
        if row < 0:
            return
        self._crop_data[row] = {
            "x": self.crop_x.value(), "y": self.crop_y.value(),
            "w": self.crop_w.value(), "h": self.crop_h.value(),
            "skip": self.crop_skip_check.isChecked(),
        }

    def _crop_load_image(self, index: int, retain_zoom: bool = False):
        if index < 0 or index >= self.file_list.count():
            return
        if self._crop_index is not None and 0 <= self._crop_index < self.file_list.count():
            self._crop_data[self._crop_index] = {
                "x": self.crop_x.value(), "y": self.crop_y.value(),
                "w": self.crop_w.value(), "h": self.crop_h.value(),
                "skip": self.crop_skip_check.isChecked(),
            }
        self._crop_index = index
        self._update_crop_nav_label()
        self.crop_prev_btn.setEnabled(index > 0)
        self.crop_next_btn.setEnabled(index < self.file_list.count() - 1)
        try:
            path = self._files[index]
            pil_img = self._get_preview_image(path)
            lut_obj, intensity = self._get_active_lut(index)
            if lut_obj:
                pil_img = apply_lut(pil_img, lut_obj, intensity)
            iw, ih = pil_img.size
            self.crop_manual_view.load_image(pil_img, retain_zoom=retain_zoom)
            self._crop_updating = True
            if index in self._crop_data:
                d = self._crop_data[index]
                self.crop_x.setValue(d["x"]); self.crop_y.setValue(d["y"])
                self.crop_w.setValue(d["w"]); self.crop_h.setValue(d["h"])
                self.crop_skip_check.setChecked(d["skip"])
            else:
                self.crop_x.setValue(0); self.crop_y.setValue(0)
                self.crop_w.setValue(iw); self.crop_h.setValue(ih)
                self.crop_skip_check.setChecked(False)
            self._crop_updating = False
            self.crop_manual_view.set_crop_rect(
                self.crop_x.value(), self.crop_y.value(),
                self.crop_w.value(), self.crop_h.value())
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    def _crop_same_load_preview(self, path: str, retain_zoom: bool = False):
        try:
            row = self.file_list.currentRow()
            pil_img = self._get_preview_image(path)
            lut_obj, intensity = self._get_active_lut(row)
            if lut_obj:
                pil_img = apply_lut(pil_img, lut_obj, intensity)
            self.crop_same_view.load_image(pil_img, retain_zoom=retain_zoom)
            self._crop_same_update_view()
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    def _update_crop_nav_label(self):
        row = self.file_list.currentRow()
        total = self.file_list.count()
        if row >= 0 and total > 0:
            self.crop_nav_label.setText(
                self.i18n("crop_image_n_of", current=row + 1, total=total))
        else:
            self.crop_nav_label.setText("")

    def _crop_same_on_view_changed(self, x, y, w, h):
        if self._crop_updating:
            return
        self._crop_updating = True
        self.crop_same_w.setValue(w)
        self.crop_same_h.setValue(h)
        self._crop_updating = False
        self._auto_save_temp()

    def _crop_same_update_view(self):
        if self._crop_updating:
            return
        if self.crop_anchor.currentIndex() < 0:
            return
        img_sz = self.crop_same_view.image_size()
        if img_sz == (0, 0):
            return
        iw, ih = img_sz
        cw = min(self.crop_same_w.value(), iw)
        ch = min(self.crop_same_h.value(), ih)
        if self.crop_anchor.currentText() == self.i18n("crop_top_left"):
            cx, cy = 0, 0
        else:
            cx = max(0, (iw - cw) // 2)
            cy = max(0, (ih - ch) // 2)
        self.crop_same_view.set_crop_rect(cx, cy, cw, ch)

    def _crop_manual_on_view_changed(self, x, y, w, h):
        if self._crop_updating:
            return
        self._crop_updating = True
        self.crop_x.setValue(x); self.crop_y.setValue(y)
        self.crop_w.setValue(w); self.crop_h.setValue(h)
        self._crop_updating = False
        self._auto_save_temp()

    def _crop_manual_update_view(self):
        if self._crop_updating:
            return
        self.crop_manual_view.set_crop_rect(
            self.crop_x.value(), self.crop_y.value(),
            self.crop_w.value(), self.crop_h.value())

    def _crop_update_aspect_ratio(self):
        text = self.crop_aspect.currentText()
        if ":" in text:
            parts = text.split(":")
            try:
                ratio = float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                ratio = 0.0
        else:
            ratio = 0.0
        self.crop_manual_view.set_aspect_ratio(ratio)

    # ---- Unified Export ----

    def _run_export(self):
        """Run export (format + resize + crop + LUT) in a background thread."""
        count = self.file_list.count()
        if count == 0:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_files"))
            return
        out_dir = self.output_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_output"))
            return

        if self.crop_radio_manual.isChecked():
            self._crop_save_current_settings()

        fmt       = self.conv_format.currentText()
        quality   = self.conv_quality_slider.value()
        ext_out   = EXT_MAP.get(fmt, ".png")
        w         = self.conv_width.value() or None
        h         = self.conv_height.value() or None
        scale_pct = self.conv_scale.value() or None
        scale     = (scale_pct / 100) if scale_pct else None

        crop_mode      = self.crop_mode_group.checkedId()
        is_crop_same   = (crop_mode == self.CROP_SAME)
        is_crop_manual = (crop_mode == self.CROP_MANUAL)

        same_w      = self.crop_same_w.value()
        same_h      = self.crop_same_h.value()
        anchor_text = self.crop_anchor.currentText()
        anchor      = "top-left" if anchor_text == self.i18n("crop_top_left") else "center"

        crop_data = dict(self._crop_data)
        files     = [self.file_list.item(i).data(Qt.UserRole) for i in range(count)]
        out_path  = Path(out_dir)

        lut_mode = self._lut_mode
        lut_same_obj = self._lut_same_obj
        lut_same_intensity = self._lut_same_intensity
        lut_per_image_data = dict(self._lut_per_image_data)

        def task():
            ok, err, skipped = 0, 0, 0
            self._signals.progress.emit(0)
            self._log(f"{self.i18n('log_arrow')}  {len(files)} {self.i18n('log_files_found')}", "inf")
            for idx, fpath in enumerate(files, 1):
                src_path = Path(fpath)
                dst = out_path / (src_path.stem + ext_out)
                if is_crop_manual:
                    settings = crop_data.get(idx - 1)
                    if settings and settings.get("skip"):
                        skipped += 1
                        self._signals.progress.emit(int(idx / len(files) * 100))
                        continue
                try:
                    is_svg = src_path.suffix.lower() == ".svg"
                    if is_svg:
                        img = open_image(src_path, svg_width=w, svg_height=h, svg_scale=scale)
                    else:
                        img = open_image(src_path)
                        if w or h or scale:
                            img = do_resize(img, width=w, height=h, scale=scale)

                    if is_crop_same:
                        img = do_center_crop(img, same_w, same_h, anchor)
                    elif is_crop_manual:
                        settings = crop_data.get(idx - 1)
                        if settings:
                            cx, cy = settings["x"], settings["y"]
                            cw, ch = settings["w"], settings["h"]
                            if cw > 0 and ch > 0:
                                img = do_crop(img, cx, cy, cw, ch)

                    # Apply LUT if configured
                    if lut_mode == self.LUT_SAME and lut_same_obj:
                        img = apply_lut(img, lut_same_obj, lut_same_intensity)
                    elif lut_mode == self.LUT_MANUAL:
                        l_data = lut_per_image_data.get(idx - 1)
                        if l_data and l_data.get("obj"):
                            img = apply_lut(img, l_data["obj"], l_data.get("intensity", 1.0))

                    save_image(img, dst, quality=quality, fmt_override=fmt)
                    self._log(
                        f"{self.i18n('log_success')}  {src_path.name}  {self.i18n('log_arrow')}  {dst.name}  {img.size}",
                        "ok",
                    )
                    ok += 1
                except Exception as e:
                    self._log(f"{self.i18n('log_error')}  {src_path.name}: {e}", "err")
                    traceback.print_exc()
                    err += 1
                self._signals.progress.emit(int(idx / len(files) * 100))
            summary = f"{self.i18n('log_completed')} {ok} {self.i18n('log_ok_count')}, {err} {self.i18n('log_err_count')}."
            if skipped:
                summary += f" ({skipped} skipped)"
            self._log(summary, "inf")
            self._signals.finished.emit()

        self._start_progress_dialog(self.i18n("info_processing"))
        threading.Thread(target=task, daemon=True).start()

    # ---- Project management ----

    def _auto_save_temp(self):
        if self._crop_updating or self._lut_updating:
            return
        self._project_dirty = True
        self._autosave_timer.start(300)

    def _do_auto_save_temp(self):
        try:
            from src.project_manager import encrypt_project_data
            state = self._get_project_state()
            encrypted = encrypt_project_data(state)
            recovery_file = Path(_PROJECT_ROOT) / "autosave.qif"
            with open(recovery_file, "wb") as f:
                f.write(encrypted)
        except Exception:
            pass

    def _add_to_recent_projects(self, filepath: str):
        filepath = str(Path(filepath).resolve())
        if filepath in self._recent_projects:
            self._recent_projects.remove(filepath)
        self._recent_projects.insert(0, filepath)
        self._recent_projects = self._recent_projects[:5]
        self._save_settings()
        self._rebuild_file_menu()

    def _get_project_state(self) -> dict:
        return {
            "version": "1.2",
            "files": self._files,
            "crop_data": {str(k): v for k, v in self._crop_data.items()},
            "lut_state": {
                "lut_mode": self._lut_mode,
                "lut_same_file": self._lut_same_file,
                "lut_same_preset": self._lut_same_preset,
                "lut_same_intensity": self._lut_same_intensity,
                "lut_same_settings": self._lut_same_settings,
                "lut_per_image_data": {
                    str(k): {
                        "file": v.get("file"),
                        "preset": v.get("preset"),
                        "intensity": v.get("intensity", 1.0),
                        "settings": v.get("settings", {})
                    }
                    for k, v in self._lut_per_image_data.items()
                }
            },
            "settings": {
                "convert_format":  self.conv_format.currentText(),
                "convert_quality": self.conv_quality_slider.value(),
                "output_dir":      self.output_dir.text(),
                "convert_width":   self.conv_width.value(),
                "convert_height":  self.conv_height.value(),
                "convert_scale":   self.conv_scale.value(),
                "crop_mode":       self.crop_mode_group.checkedId(),
                "crop_same_w":     self.crop_same_w.value(),
                "crop_same_h":     self.crop_same_h.value(),
                "crop_anchor":     self.crop_anchor.currentIndex(),
                "crop_aspect":     self.crop_aspect.currentIndex(),
            }
        }

    def _apply_project_state(self, state: dict):
        self._crop_updating = True
        self._lut_updating = True
        self._clear_all()
        missing_files = []
        for f in state.get("files", []):
            if Path(f).exists():
                self._add_path(f)
            else:
                missing_files.append(f)
        self._update_count()

        self._crop_data = {}
        for k, v in state.get("crop_data", {}).items():
            try:
                self._crop_data[int(k)] = v
            except ValueError:
                pass

        # Restore LUT state
        lut_state = state.get("lut_state", {})
        self._lut_mode = lut_state.get("lut_mode", self.LUT_NONE)
        self._lut_same_file = lut_state.get("lut_same_file")
        self._lut_same_preset = lut_state.get("lut_same_preset")
        self._lut_same_intensity = lut_state.get("lut_same_intensity", 1.0)
        self._lut_same_settings = lut_state.get("lut_same_settings", {
            "brightness": 0, "contrast": 0, "saturation": 0, "temperature": 0,
            "tint": 0, "gamma": 100, "hue_shift": 0, "r_gain": 100, "g_gain": 100, "b_gain": 100
        })

        if self._lut_same_file and Path(self._lut_same_file).exists():
            try:
                self._lut_same_obj = load_lut_file(self._lut_same_file)
            except Exception:
                self._lut_same_obj = None
        elif self._lut_same_preset and self._lut_same_preset in PRESET_LUT_SETTINGS:
            self._lut_same_obj = get_preset_lut(self._lut_same_preset)
        elif self._lut_same_settings:
            s = dict(self._lut_same_settings)
            s["gamma"] = s.get("gamma", 100) / 100.0 if isinstance(s.get("gamma"), (int, float)) and s.get("gamma") > 2.5 else s.get("gamma", 1.0)
            s["r_gain"] = s.get("r_gain", 100) / 100.0 if isinstance(s.get("r_gain"), (int, float)) and s.get("r_gain") > 2.0 else s.get("r_gain", 1.0)
            s["g_gain"] = s.get("g_gain", 100) / 100.0 if isinstance(s.get("g_gain"), (int, float)) and s.get("g_gain") > 2.0 else s.get("g_gain", 1.0)
            s["b_gain"] = s.get("b_gain", 100) / 100.0 if isinstance(s.get("b_gain"), (int, float)) and s.get("b_gain") > 2.0 else s.get("b_gain", 1.0)
            self._lut_same_obj = generate_lut_from_settings(**s)

        self._lut_per_image_data = {}
        for k, v in lut_state.get("lut_per_image_data", {}).items():
            try:
                idx = int(k)
                f_path = v.get("file")
                preset_p = v.get("preset")
                intensity = v.get("intensity", 1.0)
                settings = v.get("settings", {})
                lut_obj = None
                if f_path and Path(f_path).exists():
                    lut_obj = load_lut_file(f_path)
                elif preset_p and preset_p in PRESET_LUT_SETTINGS:
                    lut_obj = get_preset_lut(preset_p)
                elif settings:
                    s = dict(settings)
                    s["gamma"] = s.get("gamma", 100) / 100.0 if isinstance(s.get("gamma"), (int, float)) and s.get("gamma") > 2.5 else s.get("gamma", 1.0)
                    s["r_gain"] = s.get("r_gain", 100) / 100.0 if isinstance(s.get("r_gain"), (int, float)) and s.get("r_gain") > 2.0 else s.get("r_gain", 1.0)
                    s["g_gain"] = s.get("g_gain", 100) / 100.0 if isinstance(s.get("g_gain"), (int, float)) and s.get("g_gain") > 2.0 else s.get("g_gain", 1.0)
                    s["b_gain"] = s.get("b_gain", 100) / 100.0 if isinstance(s.get("b_gain"), (int, float)) and s.get("b_gain") > 2.0 else s.get("b_gain", 1.0)
                    lut_obj = generate_lut_from_settings(**s)

                self._lut_per_image_data[idx] = {
                    "obj": lut_obj, "file": f_path, "preset": preset_p,
                    "intensity": intensity, "settings": settings
                }
            except ValueError:
                pass

        radio_lut_map = {
            self.LUT_NONE: self.lut_radio_none,
            self.LUT_SAME: self.lut_radio_same,
            self.LUT_MANUAL: self.lut_radio_manual,
        }
        radio_lut_map.get(self._lut_mode, self.lut_radio_none).setChecked(True)
        self._on_lut_mode_changed(self._lut_mode, True)

        settings = state.get("settings", {})
        if "convert_format"  in settings: self.conv_format.setCurrentText(settings["convert_format"])
        if "convert_quality" in settings: self.conv_quality_slider.setValue(settings["convert_quality"])

        out_dir = (
            settings.get("output_dir")
            or settings.get("convert_output_dir")
            or settings.get("crop_output_dir", "")
        )
        if out_dir:
            self.output_dir.setText(out_dir)

        if "convert_width"  in settings: self.conv_width.setValue(settings["convert_width"])
        if "convert_height" in settings: self.conv_height.setValue(settings["convert_height"])
        if "convert_scale"  in settings: self.conv_scale.setValue(settings["convert_scale"])

        if "crop_mode" in settings:
            crop_mode = int(settings["crop_mode"])
        elif settings.get("crop_is_manual", False):
            crop_mode = self.CROP_MANUAL
        else:
            crop_mode = self.CROP_NONE

        radio_map = {
            self.CROP_NONE: self.crop_radio_none,
            self.CROP_SAME: self.crop_radio_same,
            self.CROP_MANUAL: self.crop_radio_manual,
        }
        radio_map.get(crop_mode, self.crop_radio_none).setChecked(True)
        self._on_crop_mode_changed(crop_mode, True)

        if "crop_same_w" in settings: self.crop_same_w.setValue(settings["crop_same_w"])
        if "crop_same_h" in settings: self.crop_same_h.setValue(settings["crop_same_h"])
        if "crop_anchor" in settings: self.crop_anchor.setCurrentIndex(settings["crop_anchor"])
        if "crop_aspect" in settings: self.crop_aspect.setCurrentIndex(settings["crop_aspect"])

        self._crop_updating = False
        self._lut_updating = False
        self._auto_load_preview()
        if crop_mode == self.CROP_SAME and self.file_list.currentRow() >= 0:
            path = self.file_list.item(self.file_list.currentRow()).data(Qt.UserRole)
            self._crop_same_load_preview(path)

        if missing_files:
            QMessageBox.warning(
                self,
                self.i18n("project_missing_images_title"),
                self.i18n("project_missing_images", paths="\n".join(missing_files))
            )
            for f in missing_files:
                self._log(f"{self.i18n('log_error')} File not found: {f}", "err")

    def _save_project(self):
        if self.crop_radio_manual.isChecked():
            self._crop_save_current_settings()
        filename, _ = QFileDialog.getSaveFileName(
            self, self.i18n("save_project"), "", self.i18n("project_files"))
        if not filename:
            return
        if not filename.endswith(".qif"):
            filename += ".qif"
        try:
            from src.project_manager import encrypt_project_data
            encrypted = encrypt_project_data(self._get_project_state())
            with open(filename, "wb") as f:
                f.write(encrypted)
            self._project_dirty = False
            self._add_to_recent_projects(filename)
            self._log(f"{self.i18n('log_success')} {self.i18n('project_saved')}: {Path(filename).name}", "ok")
            QMessageBox.information(self, self.i18n("info_done"), self.i18n("project_saved"))
        except Exception as e:
            self._log(f"{self.i18n('log_error')} Error saving project: {e}", "err")
            QMessageBox.critical(self, self.i18n("error_title"), f"Error saving project: {e}")

    def _open_project(self):
        if self._project_dirty:
            reply = QMessageBox.question(
                self, self.i18n("unsaved_changes_title"), self.i18n("unsaved_changes"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if reply == QMessageBox.Save:
                self._save_project()
                if self._project_dirty:
                    return
            elif reply == QMessageBox.Cancel:
                return
        filename, _ = QFileDialog.getOpenFileName(
            self, self.i18n("open_project"), "", self.i18n("project_files"))
        if filename:
            self._load_project_file(filename)

    def _load_project_file(self, filepath: str):
        path = Path(filepath)
        if not path.exists():
            return
        try:
            from src.project_manager import decrypt_project_data
            from cryptography.fernet import InvalidToken
            with open(path, "rb") as f:
                encrypted_data = f.read()
            try:
                state = decrypt_project_data(encrypted_data)
            except (InvalidToken, Exception):
                QMessageBox.critical(
                    self, self.i18n("project_corrupted_title"), self.i18n("project_corrupted"))
                self._log(f"{self.i18n('log_error')} {self.i18n('project_corrupted')}", "err")
                return
            self._apply_project_state(state)
            if path.name != "autosave.qif":
                self._project_dirty = False
                self._add_to_recent_projects(str(path))
                self._log(f"{self.i18n('log_success')} {self.i18n('project_loaded')}: {path.name}", "ok")
            else:
                self._project_dirty = True
                self._log(f"{self.i18n('log_success')} Temporary session auto-recovered", "ok")
        except Exception as e:
            self._log(f"{self.i18n('log_error')} Error loading project: {e}", "err")
            QMessageBox.critical(self, self.i18n("error_title"), f"Error loading project: {e}")

    def closeEvent(self, event):
        if self._project_dirty:
            reply = QMessageBox.question(
                self, self.i18n("unsaved_changes_title"), self.i18n("unsaved_changes"),
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if reply == QMessageBox.Save:
                self._save_project()
                if self._project_dirty:
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
        self._auto_save_temp()
        event.accept()
