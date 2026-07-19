"""
Main application window for Quick Image Formatting (PySide6 / Qt).

Unified workflow: import images -> configure format, resize, crop -> EXPORT
"""

import traceback
import sys
import threading
from pathlib import Path
from typing import List, Optional, Dict

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QComboBox, QSlider, QLineEdit, QListWidget,
    QListWidgetItem, QFileDialog, QMessageBox, QProgressBar, QTextEdit,
    QCheckBox, QRadioButton, QButtonGroup, QFrame, QAbstractItemView,
    QApplication, QSplitter, QScrollArea, QDialog, QStackedWidget, QMenu,
    QColorDialog,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QPixmap, QColor, QIcon
from PIL import Image

from src.constants import OUTPUT_FORMATS, EXT_MAP, INPUT_EXTS
from src.image_processor import open_image, save_image, do_resize, do_crop, do_center_crop
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
        unified_scroll.setMinimumWidth(300)
        unified_widget = QWidget()
        self._build_unified_options(unified_widget)
        unified_scroll.setWidget(unified_widget)
        top_right_splitter.addWidget(unified_scroll)

        main_splitter.setSizes([220, 740])
        top_right_splitter.setSizes([440, 300])

        self._signals = _WorkerSignals()
        self._update_ui_texts()

        self.crop_same_view.cropChanged.connect(self._crop_same_on_view_changed)
        self.crop_same_w.valueChanged.connect(self._crop_same_update_view)
        self.crop_same_h.valueChanged.connect(self._crop_same_update_view)
        self.crop_anchor.currentIndexChanged.connect(self._crop_same_update_view)

        self.crop_manual_view.cropChanged.connect(self._crop_manual_on_view_changed)
        for sb in (self.crop_x, self.crop_y, self.crop_w, self.crop_h):
            sb.valueChanged.connect(self._crop_manual_update_view)
        self.crop_aspect.currentIndexChanged.connect(self._crop_update_aspect_ratio)

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
        """Create/recreate the unified File menu (project + settings combined)."""
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
        """Update all UI text labels for the current language."""
        self.setWindowTitle(self.i18n("title"))

        self.btn_file.setText(self.i18n("file_menu"))
        self._rebuild_file_menu()

        self.lbl_pick_images.setText(self.i18n("pick_images"))
        self.btn_add_files.setText(self.i18n("add_files"))
        self.btn_add_folder.setText(self.i18n("add_folder"))
        self.btn_remove.setText(self.i18n("remove_selected"))
        self.btn_clear.setText(self.i18n("clear_all"))
        self.subfolder_check.setText(self.i18n("include_subfolders"))
        self._update_count()

        self.lbl_save_as.setText(self.i18n("save_as"))
        self.lbl_quality.setText(self.i18n("picture_quality"))
        self.lbl_save_to.setText(self.i18n("save_to"))
        self.btn_browse_out.setText(self.i18n("browse"))

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

        self.btn_export.setText("EXPORT")
        self._update_crop_nav_label()

    def _show_about(self):
        """Show the About dialog."""
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
        """Thread-safe log — emits signal to main thread."""
        self._signals.log.emit(msg, tag)

    def _start_progress_dialog(self, title_text):
        """Prepare and show the progress dialog, connecting worker signals to it."""
        for attr in ("log", "progress", "finished"):
            try:
                getattr(self._signals, attr).disconnect()
            except RuntimeError:
                pass
        dlg = ProgressDialog(self, title_text=title_text)
        self._signals.log.connect(dlg.append_log)
        self._signals.progress.connect(dlg.set_progress)
        self._signals.finished.connect(lambda: dlg.on_finished(self.i18n("info_done")))
        dlg.show()
        return dlg

    # ---- Layout builders ----

    def _build_header(self, layout):
        """Build the header bar with a single File button on the left."""
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
        """Build the left sidebar containing file list and operations."""
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.lbl_pick_images = QLabel()  # kept but not added to layout (title hidden)

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
        """Build the unified options panel: format/quality, resize, crop, EXPORT."""
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # Format & Quality
        self.lbl_save_as = QLabel()
        layout.addWidget(self.lbl_save_as)
        self.conv_format = QComboBox()
        self.conv_format.addItems(OUTPUT_FORMATS)
        self.conv_format.setCurrentText("PNG")
        layout.addWidget(self.conv_format)

        self.lbl_quality = QLabel()
        layout.addWidget(self.lbl_quality)
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
        layout.addLayout(q_row)

        # Output directory
        self.lbl_save_to = QLabel()
        layout.addWidget(self.lbl_save_to)
        self.output_dir = QLineEdit()
        layout.addWidget(self.output_dir)
        self.btn_browse_out = QPushButton()
        self.btn_browse_out.clicked.connect(self._browse_output)
        layout.addWidget(self.btn_browse_out)

        # Resize section
        layout.addWidget(Separator())
        self.conv_resize_title = QLabel()
        self.conv_resize_title.setObjectName("headerLabel")
        layout.addWidget(self.conv_resize_title)

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
        layout.addLayout(rg)

        # Crop section
        layout.addWidget(Separator())
        self._crop_section_title = QLabel()
        self._crop_section_title.setObjectName("headerLabel")
        layout.addWidget(self._crop_section_title)

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
        layout.addLayout(mc)

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
        self.crop_anchor.addItems(["", ""])  # filled in _update_ui_texts
        sg.addWidget(self.lbl_same_w,    0, 0); sg.addWidget(self.crop_same_w,   0, 1)
        sg.addWidget(self.lbl_same_h,    1, 0); sg.addWidget(self.crop_same_h,   1, 1)
        sg.addWidget(self.lbl_same_from, 2, 0); sg.addWidget(self.crop_anchor,   2, 1)
        sl.addLayout(sg)
        self.crop_same_panel.setVisible(False)
        layout.addWidget(self.crop_same_panel)

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
        layout.addWidget(self.crop_manual_panel)

        layout.addStretch(1)

        # EXPORT button
        self.btn_export = QPushButton()
        self.btn_export.setObjectName("primaryBtn")
        self.btn_export.clicked.connect(self._run_export)
        layout.addWidget(self.btn_export)

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

    def _on_file_selected(self, row: int):
        """Triggered when a row in the unified file list is highlighted."""
        if row < 0 or row >= self.file_list.count():
            self._clear_viewport()
            return
        path = self.file_list.item(row).data(Qt.UserRole)
        mode = self.crop_mode_group.checkedId()
        if mode == self.CROP_NONE:
            self._load_convert_preview(path)
        elif mode == self.CROP_SAME:
            self._crop_same_load_preview(path)
        elif mode == self.CROP_MANUAL:
            self._crop_load_image(row)

    def _clear_viewport(self):
        """Reset all viewports to empty state."""
        self.convert_preview.clear_image()
        self.crop_same_view.clear_image()
        self.crop_manual_view.clear_image()
        self.crop_nav_label.setText("")

    def _load_convert_preview(self, path: str):
        """Load selected image into the fitted previewer."""
        try:
            self.convert_preview.load_image(open_image(Path(path)))
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
        for r in rows:
            tmp = {}
            for idx, val in self._crop_data.items():
                if idx < r:
                    tmp[idx] = val
                elif idx > r:
                    tmp[idx - 1] = val
            self._crop_data = tmp
        self._update_count()
        self._auto_load_preview()
        self._auto_save_temp()

    def _clear_all(self):
        self._crop_index = None
        self.file_list.clear()
        self._files.clear()
        self._crop_data.clear()
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

    def _crop_load_image(self, index: int):
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
            pil_img = open_image(Path(self._files[index]))
            iw, ih = pil_img.size
            self.crop_manual_view.load_image(pil_img)
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

    def _crop_same_load_preview(self, path: str):
        try:
            pil_img = open_image(Path(path))
            self.crop_same_view.load_image(pil_img)
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
        """Run the unified export (format + resize + crop) in a background thread."""
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
        if self._crop_updating:
            return
        self._project_dirty = True
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
            "version": "1.1",
            "files": self._files,
            "crop_data": {str(k): v for k, v in self._crop_data.items()},
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
