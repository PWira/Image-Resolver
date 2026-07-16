"""
Main application window for Quick Image Formatting (PySide6 / Qt).

Two tabs:
  1. Convert Images — unified single + batch workflow
  2. Crop Images — batch same-size or manual one-by-one crop
"""

import traceback
import sys
import threading
from pathlib import Path
from typing import List, Optional, Dict

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTabWidget, QLabel, QPushButton, QComboBox, QSlider, QSpinBox,
    QLineEdit, QListWidget, QListWidgetItem, QFileDialog, QMessageBox,
    QProgressBar, QTextEdit, QCheckBox, QRadioButton, QButtonGroup,
    QFrame, QSizePolicy, QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
    QGraphicsRectItem, QAbstractItemView, QGroupBox, QApplication,
    QSplitter, QScrollArea, QDialog, QStackedWidget, QMenu, QColorDialog,
)
from PySide6.QtCore import Qt, Signal, QObject, QRectF, QPointF, QTimer
from PySide6.QtGui import (
    QPixmap, QImage, QPen, QBrush, QColor, QIcon, QPainter, QCursor,
)
from PIL import Image, ImageQt

from src.constants import OUTPUT_FORMATS, EXT_MAP, INPUT_EXTS
from src.image_processor import open_image, save_image, do_resize, do_crop, do_center_crop
from src.ui_components import int_or_none, float_or_none, file_filter_string, CollapsibleSection, Separator, InteractiveCropView, FittedImageView
from src.localization import get_i18n, set_language
import src.theme as theme



if hasattr(sys, '_MEIPASS'):
    _PROJECT_ROOT = Path(sys._MEIPASS)
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent



# ── Signal bridge for thread-safe GUI updates ────────────────
class _WorkerSignals(QObject):
    """Signals emitted by background worker threads."""
    log = Signal(str, str)           # (message, tag)
    progress = Signal(int)           # 0-100
    finished = Signal()


# ── Main Window ──────────────────────────────────────────────

class App(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        # Load language and palette settings first
        self._load_settings()

        self.setWindowTitle(self.i18n("title"))
        self.setMinimumSize(820, 680)
        self.resize(880, 720)
        self._set_icon()

        # Apply theme stylesheet dynamically
        self.setStyleSheet(theme.get_stylesheet())

        # Internal states
        self._files: List[str] = []
        self._crop_data: Dict[int, dict] = {}
        self._crop_updating = False

        # Central widget and root layout
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(10)

        # 1. Green Header (Top Panel)
        self._build_header(root_layout)

        # 2. Splitters for Yellow, Grey, Blue, Red
        main_splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(main_splitter, stretch=1)

        # Yellow Sidebar Container (Left Panel)
        sidebar_widget = QWidget()
        self._build_sidebar(sidebar_widget)
        main_splitter.addWidget(sidebar_widget)

        # Right area container (contains Grey + Blue top, Red bottom)
        right_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(right_splitter)

        # Top Right Splitter (Grey Viewport Left, Blue Options Right)
        top_right_splitter = QSplitter(Qt.Horizontal)
        right_splitter.addWidget(top_right_splitter)

        # Grey Viewport Stack
        self.viewport_stack = QStackedWidget()
        self.convert_preview = FittedImageView()
        self.crop_same_view = InteractiveCropView()
        self.crop_manual_view = InteractiveCropView()
        self.viewport_stack.addWidget(self.convert_preview)   # Index 0
        self.viewport_stack.addWidget(self.crop_same_view)     # Index 1
        self.viewport_stack.addWidget(self.crop_manual_view)   # Index 2
        top_right_splitter.addWidget(self.viewport_stack)

        # Blue Options Stack
        self.options_stack = QStackedWidget()
        
        # Convert options page (wrapped in scroll area)
        conv_scroll = QScrollArea()
        conv_scroll.setWidgetResizable(True)
        conv_scroll.setFrameShape(QFrame.NoFrame)
        conv_widget = QWidget()
        self._build_convert_options(conv_widget)
        conv_scroll.setWidget(conv_widget)
        self.options_stack.addWidget(conv_scroll) # Index 0
        
        # Crop options page (wrapped in scroll area)
        crop_scroll = QScrollArea()
        crop_scroll.setWidgetResizable(True)
        crop_scroll.setFrameShape(QFrame.NoFrame)
        crop_widget = QWidget()
        self._build_crop_options(crop_widget)
        crop_scroll.setWidget(crop_widget)
        self.options_stack.addWidget(crop_scroll) # Index 1
        
        top_right_splitter.addWidget(self.options_stack)

        # Red Log and Progress Panel (Bottom)
        log_container = QWidget()
        log_layout = QVBoxLayout(log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.setSpacing(6)
        self._build_log_area(log_layout)
        self._build_progress_bar(log_layout)
        right_splitter.addWidget(log_container)

        # Set default splitter sizes
        main_splitter.setSizes([220, 660])
        right_splitter.setSizes([480, 140])
        top_right_splitter.setSizes([440, 220])

        # Worker signals
        self._signals = _WorkerSignals()
        self._signals.log.connect(self._append_log)
        self._signals.progress.connect(self._set_progress)
        self._signals.finished.connect(self._on_finished)

        # Initialize UI texts and settings menu
        self._update_ui_texts()

        # Connect interactive crop signals
        # Same-size mode: view ↔ spinboxes
        self.crop_same_view.cropChanged.connect(self._crop_same_on_view_changed)
        self.crop_same_w.valueChanged.connect(self._crop_same_update_view)
        self.crop_same_h.valueChanged.connect(self._crop_same_update_view)
        self.crop_anchor.currentIndexChanged.connect(self._crop_same_update_view)

        # One-by-one mode: view ↔ spinboxes
        self.crop_manual_view.cropChanged.connect(self._crop_manual_on_view_changed)
        for sb in (self.crop_x, self.crop_y, self.crop_w, self.crop_h):
            sb.valueChanged.connect(self._crop_manual_update_view)
        self.crop_aspect.currentIndexChanged.connect(self._crop_update_aspect_ratio)

        # Center on screen
        self._center_window()

    # ── Setup helpers ────────────────────────────────────────

    def _set_icon(self):
        """Set window icon if available."""
        try:
            icon_path = _PROJECT_ROOT / "monolight.png"
            if icon_path.exists():
                self.setWindowIcon(QIcon(str(icon_path)))
        except Exception:
            pass

    def _center_window(self):
        """Center window on screen."""
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = (geo.width() - self.width()) // 2 + geo.x()
            y = (geo.height() - self.height()) // 2 + geo.y()
            self.move(x, y)

    def _change_language(self, lang: str):
        """Change language, update UI, and save configuration."""
        set_language(lang)
        self.i18n = get_i18n()
        self._update_ui_texts()
        self._save_settings()

    def _load_settings(self):
        """Load settings from settings.json."""
        import json
        settings_file = Path(_PROJECT_ROOT) / "settings.json"
        
        # Default settings
        lang = "en"
        palette = "gold"
        custom_accent = ""
        
        if settings_file.exists():
            try:
                with open(settings_file, "r") as f:
                    data = json.load(f)
                    lang = data.get("language", "en")
                    palette = data.get("palette", "gold")
                    custom_accent = data.get("custom_accent", "")
            except Exception:
                pass
        
        # Set language
        set_language(lang)
        self.i18n = get_i18n()
        
        # Set active color palette
        if palette == "custom" and custom_accent:
            theme.set_custom_accent(custom_accent)
        else:
            theme.set_active_palette(palette)

    def _save_settings(self):
        """Save settings to settings.json."""
        import json
        settings_file = Path(_PROJECT_ROOT) / "settings.json"
        data = {
            "language": self.i18n.language,
            "palette": theme.current_palette_name,
            "custom_accent": theme.custom_accent_color
        }
        try:
            with open(settings_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def _apply_theme(self, name: str):
        """Apply preset theme color palette."""
        theme.set_active_palette(name)
        self.setStyleSheet(theme.get_stylesheet())
        self._save_settings()
        self._update_ui_texts()
        self._on_file_selected(self.file_list.currentRow())

    def _choose_custom_color(self):
        """Open dialog to pick a custom accent color."""
        initial = QColor(theme.GOLD)
        color = QColorDialog.getColor(initial, self, self.i18n("custom_color"))
        if color.isValid():
            hex_color = color.name().upper()
            theme.set_custom_accent(hex_color)
            self.setStyleSheet(theme.get_stylesheet())
            self._save_settings()
            self._update_ui_texts()
            self._on_file_selected(self.file_list.currentRow())

    def _rebuild_settings_menu(self):
        """Create/recreate settings menu in correct language."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.CARD_BG};
                color: {theme.TEXT_PRIMARY};
                border: 1px solid {theme.BORDER};
            }}
            QMenu::item:selected {{
                background-color: {theme.GOLD};
                color: {theme.BLACK_MATTE};
            }}
        """)
        
        lang_menu = menu.addMenu(self.i18n("language"))
        lang_menu.addAction("English", lambda: self._change_language("en"))
        lang_menu.addAction("Bahasa Indonesia", lambda: self._change_language("id"))
        
        palette_menu = menu.addMenu(self.i18n("color_palette"))
        palette_menu.addAction(self.i18n("theme_gold"), lambda: self._apply_theme("gold"))
        palette_menu.addAction(self.i18n("theme_purple"), lambda: self._apply_theme("purple"))
        palette_menu.addAction(self.i18n("theme_blue"), lambda: self._apply_theme("blue"))
        palette_menu.addAction(self.i18n("theme_green"), lambda: self._apply_theme("green"))
        palette_menu.addAction(self.i18n("theme_light"), lambda: self._apply_theme("light"))
        palette_menu.addSeparator()
        palette_menu.addAction(self.i18n("custom_color"), self._choose_custom_color)
        
        menu.addAction(self.i18n("about_qif"), self._show_about)
        self.btn_settings.setMenu(menu)

    def _update_ui_texts(self):
        """Update all UI text labels for the current language."""
        self.setWindowTitle(self.i18n("title"))
        self._log_label.setText(self.i18n("log"))
        
        # Header / Green
        self.btn_convert_mode.setText(self.i18n("convert"))
        self.btn_crop_mode.setText(self.i18n("crop"))
        self.btn_settings.setText(self.i18n("settings"))
        self._rebuild_settings_menu()
        
        # Sidebar / Yellow
        self.lbl_pick_images.setText(self.i18n("pick_images"))
        self.btn_add_files.setText(self.i18n("add_files"))
        self.btn_add_folder.setText(self.i18n("add_folder"))
        self.btn_remove.setText(self.i18n("remove_selected"))
        self.btn_clear.setText(self.i18n("clear_all"))
        self.subfolder_check.setText(self.i18n("include_subfolders"))
        self._update_count()
        
        # Convert Options / Blue Stack Page 0
        self.lbl_save_as.setText(self.i18n("save_as"))
        self.lbl_quality.setText(self.i18n("picture_quality"))
        self.lbl_save_to.setText(self.i18n("save_to"))
        self.btn_browse_out.setText(self.i18n("browse"))
        self.conv_resize_section.setTitle(self.i18n("change_size"))
        self.lbl_width.setText(self.i18n("width"))
        self.lbl_height.setText(self.i18n("height"))
        self.lbl_scale.setText(self.i18n("resize_percent"))
        self.btn_convert.setText(f"★  {self.i18n('convert_now')}")
        
        # Crop Options / Blue Stack Page 1
        self.lbl_crop_mode.setText(self.i18n("crop_mode"))
        self.crop_radio_same.setText(self.i18n("crop_same_size"))
        self.crop_radio_manual.setText(self.i18n("crop_one_by_one"))
        
        self.lbl_same_w.setText(self.i18n("crop_width"))
        self.lbl_same_h.setText(self.i18n("crop_height"))
        self.lbl_same_from.setText(self.i18n("crop_from"))
        
        # Populate anchor combobox
        curr_anchor = self.crop_anchor.currentIndex()
        self.crop_anchor.clear()
        self.crop_anchor.addItems([self.i18n("crop_center"), self.i18n("crop_top_left")])
        if curr_anchor >= 0:
            self.crop_anchor.setCurrentIndex(curr_anchor)
        else:
            self.crop_anchor.setCurrentIndex(0)
        
        self.lbl_manual_x.setText(self.i18n("crop_x"))
        self.lbl_manual_y.setText(self.i18n("crop_y"))
        self.lbl_manual_w.setText(self.i18n("crop_width"))
        self.lbl_manual_h.setText(self.i18n("crop_height"))
        self.lbl_manual_shape.setText(self.i18n("crop_shape"))
        
        # Populate aspect ratios combobox
        curr_aspect = self.crop_aspect.currentIndex()
        self.crop_aspect.clear()
        self.crop_aspect.addItems([
            self.i18n("crop_free"), "1:1", "4:3", "3:2", "16:9", "9:16", "3:4", "2:3",
        ])
        if curr_aspect >= 0:
            self.crop_aspect.setCurrentIndex(curr_aspect)
        else:
            self.crop_aspect.setCurrentIndex(0)
        
        self.crop_skip_check.setText(self.i18n("crop_skip"))
        self.lbl_crop_hint.setText(self.i18n("crop_hint"))
        self.crop_prev_btn.setText(f"◀  {self.i18n('crop_previous')}")
        self.crop_next_btn.setText(f"{self.i18n('crop_next')}  ▶")
        
        self.lbl_crop_save_as.setText(self.i18n("save_as"))
        self.lbl_crop_save_to.setText(self.i18n("save_to"))
        self.btn_crop_browse.setText(self.i18n("browse"))
        self.btn_crop.setText(f"★  {self.i18n('crop_save_all')}")
        
        # Update navigation text
        self._update_crop_nav_label()

    # ── About dialog ─────────────────────────────────────────

    def _show_about(self):
        """Show the About dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("About QIF")
        dlg.setFixedSize(420, 340)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.CARD_BG};
            }}
            QLabel {{
                color: #CCCCCC;
            }}
            QLabel#aboutTitle {{
                color: {theme.GOLD};
                font-size: 18pt;
                font-weight: bold;
            }}
            QLabel#aboutSubtitle {{
                color: #AAAAAA;
                font-size: 10pt;
            }}
            QLabel#aboutLink {{
                color: {theme.GOLD};
                font-size: 10pt;
            }}
            QPushButton {{
                background-color: {theme.GOLD};
                color: {theme.BLACK_MATTE};
                border: none;
                border-radius: 6px;
                padding: 8px 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.GOLD_HOVER};
            }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setSpacing(10)
        layout.setContentsMargins(28, 24, 28, 20)

        # App icon
        icon_path = _PROJECT_ROOT / "monolight.png"
        if icon_path.exists():
            icon_label = QLabel()
            px = QPixmap(str(icon_path)).scaled(
                64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
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

        author = QLabel(
            "Made by <b>Wira</b> (PWira)\n"
        )
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

    # ── Log area ─────────────────────────────────────────────

    def _build_log_area(self, parent_layout):
        """Build the activity log text area."""
        self._log_label = QLabel(self.i18n("log"))
        self._log_label.setObjectName("headerLabel")
        parent_layout.addWidget(self._log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(110)
        parent_layout.addWidget(self.log_text)

    def _build_progress_bar(self, parent_layout):
        """Build progress bar."""
        prog_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(8)
        self.progress_label = QLabel("0%")
        self.progress_label.setObjectName("dimLabel")
        self.progress_label.setFixedWidth(36)
        self.progress_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog_row.addWidget(self.progress_bar)
        prog_row.addWidget(self.progress_label)
        parent_layout.addLayout(prog_row)

    def _log(self, msg: str, tag: str = ""):
        """Thread-safe log — emits signal to main thread."""
        self._signals.log.emit(msg, tag)

    def _append_log(self, msg: str, tag: str):
        """Append text to log widget (called on main thread)."""
        color_map = {"ok": theme.SUCCESS, "err": theme.ERROR, "inf": theme.INFO}
        color = color_map.get(tag, "#CCCCCC")
        self.log_text.append(f'<span style="color:{color}">{msg}</span>')

    def _set_progress(self, value: int):
        """Update progress bar value."""
        self.progress_bar.setValue(value)
        self.progress_label.setText(f"{value}%")

    def _on_finished(self):
        """Called when worker thread finishes."""

        self._set_progress(100)
        QTimer.singleShot(800, lambda: self._set_progress(0))

    # ── Custom Layout Construction Builders ──────────────────

    def _build_header(self, layout):
        """Build the Green header bar with feature buttons and settings button."""
        header = QFrame()
        header.setObjectName("headerPanel")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)
        header_layout.setSpacing(12)

        # Title/Logo
        title = QLabel("QIF — Quick Image Formatting")
        title.setObjectName("headerLabel")
        header_layout.addWidget(title)
        
        header_layout.addStretch(1)

        # Feature Selection (Convert & Crop)
        self.btn_convert_mode = QPushButton()
        self.btn_convert_mode.setObjectName("featureBtn")
        self.btn_convert_mode.setCheckable(True)
        self.btn_convert_mode.setChecked(True)
        
        self.btn_crop_mode = QPushButton()
        self.btn_crop_mode.setObjectName("featureBtn")
        self.btn_crop_mode.setCheckable(True)

        header_layout.addWidget(self.btn_convert_mode)
        header_layout.addWidget(self.btn_crop_mode)

        # Button Group for exclusiveness
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.btn_convert_mode, 0)
        self.mode_group.addButton(self.btn_crop_mode, 1)
        self.mode_group.setExclusive(True)
        self.mode_group.idToggled.connect(self._on_feature_mode_changed)

        # Settings Dropdown Button
        self.btn_settings = QPushButton()
        self.btn_settings.setObjectName("settingsBtn")
        header_layout.addWidget(self.btn_settings)

        layout.addWidget(header)

    def _build_sidebar(self, widget):
        """Build the Yellow left sidebar containing file lists and operations."""
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header label
        self.lbl_pick_images = QLabel()
        self.lbl_pick_images.setObjectName("headerLabel")
        layout.addWidget(self.lbl_pick_images)

        # Buttons grid
        btn_grid = QGridLayout()
        btn_grid.setSpacing(6)
        
        self.btn_add_files = QPushButton()
        self.btn_add_files.clicked.connect(self._add_files)
        
        self.btn_add_folder = QPushButton()
        self.btn_add_folder.clicked.connect(self._add_folder)
        
        self.btn_remove = QPushButton()
        self.btn_remove.clicked.connect(self._remove_selected)
        
        self.btn_clear = QPushButton()
        self.btn_clear.clicked.connect(self._clear_all)

        btn_grid.addWidget(self.btn_add_files, 0, 0)
        btn_grid.addWidget(self.btn_add_folder, 0, 1)
        btn_grid.addWidget(self.btn_remove, 1, 0)
        btn_grid.addWidget(self.btn_clear, 1, 1)
        layout.addLayout(btn_grid)

        # Include subfolders check
        self.subfolder_check = QCheckBox()
        layout.addWidget(self.subfolder_check)

        # File List widget
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.currentRowChanged.connect(self._on_file_selected)
        self.file_list.setMinimumWidth(180)
        layout.addWidget(self.file_list, stretch=1)

        # File count label
        self.count_label = QLabel()
        self.count_label.setObjectName("dimLabel")
        layout.addWidget(self.count_label)

    def _build_convert_options(self, widget):
        """Build Convert options panel inside widget."""
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(12)

        # Save As
        self.lbl_save_as = QLabel()
        layout.addWidget(self.lbl_save_as)
        
        self.conv_format = QComboBox()
        self.conv_format.addItems(OUTPUT_FORMATS)
        self.conv_format.setCurrentText("PNG")
        layout.addWidget(self.conv_format)

        # Picture Quality
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
        
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.conv_quality_slider)
        quality_row.addWidget(self.conv_quality_label)
        layout.addLayout(quality_row)

        # Save To
        self.lbl_save_to = QLabel()
        layout.addWidget(self.lbl_save_to)
        
        self.conv_output_dir = QLineEdit()
        layout.addWidget(self.conv_output_dir)
        
        self.btn_browse_out = QPushButton()
        self.btn_browse_out.clicked.connect(self._conv_browse_output)
        layout.addWidget(self.btn_browse_out)

        # Resize Section
        self.conv_resize_section = CollapsibleSection("")
        resize_layout = self.conv_resize_section.content_layout()
        
        resize_grid = QGridLayout()
        resize_grid.setSpacing(6)
        
        self.lbl_width = QLabel()
        self.conv_width = QSpinBox()
        self.conv_width.setRange(0, 99999)
        self.conv_width.setSpecialValueText("—")
        self.conv_width.setSuffix(" px")
        
        self.lbl_height = QLabel()
        self.conv_height = QSpinBox()
        self.conv_height.setRange(0, 99999)
        self.conv_height.setSpecialValueText("—")
        self.conv_height.setSuffix(" px")
        
        self.lbl_scale = QLabel()
        self.conv_scale = QSpinBox()
        self.conv_scale.setRange(0, 10000)
        self.conv_scale.setSpecialValueText("—")
        self.conv_scale.setSuffix(" %")

        resize_grid.addWidget(self.lbl_width, 0, 0)
        resize_grid.addWidget(self.conv_width, 0, 1)
        resize_grid.addWidget(self.lbl_height, 1, 0)
        resize_grid.addWidget(self.conv_height, 1, 1)
        resize_grid.addWidget(self.lbl_scale, 2, 0)
        resize_grid.addWidget(self.conv_scale, 2, 1)
        resize_layout.addLayout(resize_grid)
        layout.addWidget(self.conv_resize_section)

        layout.addStretch(1)

        # Convert button
        self.btn_convert = QPushButton()
        self.btn_convert.setObjectName("primaryBtn")
        self.btn_convert.clicked.connect(self._run_convert)
        layout.addWidget(self.btn_convert)

    def _build_crop_options(self, widget):
        """Build Crop options panel inside widget."""
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # Crop Mode
        self.lbl_crop_mode = QLabel()
        self.lbl_crop_mode.setObjectName("headerLabel")
        layout.addWidget(self.lbl_crop_mode)

        self.crop_mode_group = QButtonGroup(self)
        self.crop_radio_same = QRadioButton()
        self.crop_radio_manual = QRadioButton()
        self.crop_radio_same.setChecked(True)
        self.crop_mode_group.addButton(self.crop_radio_same, 0)
        self.crop_mode_group.addButton(self.crop_radio_manual, 1)
        self.crop_mode_group.idToggled.connect(self._crop_mode_changed)

        mode_col = QVBoxLayout()
        mode_col.setSpacing(4)
        mode_col.addWidget(self.crop_radio_same)
        mode_col.addWidget(self.crop_radio_manual)
        layout.addLayout(mode_col)

        layout.addWidget(Separator())

        # ── Same-size panel ──────────────────────────────
        self.crop_same_panel = QWidget()
        same_layout = QVBoxLayout(self.crop_same_panel)
        same_layout.setContentsMargins(0, 0, 0, 0)
        same_layout.setSpacing(6)

        same_grid = QGridLayout()
        same_grid.setSpacing(6)

        self.lbl_same_w = QLabel()
        self.crop_same_w = QSpinBox()
        self.crop_same_w.setRange(1, 99999)
        self.crop_same_w.setValue(800)
        self.crop_same_w.setSuffix(" px")

        self.lbl_same_h = QLabel()
        self.crop_same_h = QSpinBox()
        self.crop_same_h.setRange(1, 99999)
        self.crop_same_h.setValue(600)
        self.crop_same_h.setSuffix(" px")

        self.lbl_same_from = QLabel()
        self.crop_anchor = QComboBox()
        self.crop_anchor.addItems(["", ""]) # filled in update_ui_texts

        same_grid.addWidget(self.lbl_same_w, 0, 0)
        same_grid.addWidget(self.crop_same_w, 0, 1)
        same_grid.addWidget(self.lbl_same_h, 1, 0)
        same_grid.addWidget(self.crop_same_h, 1, 1)
        same_grid.addWidget(self.lbl_same_from, 2, 0)
        same_grid.addWidget(self.crop_anchor, 2, 1)
        same_layout.addLayout(same_grid)
        layout.addWidget(self.crop_same_panel)

        # ── Manual panel (hidden by default) ──────────────
        self.crop_manual_panel = QWidget()
        manual_layout = QVBoxLayout(self.crop_manual_panel)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)

        crop_grid = QGridLayout()
        crop_grid.setSpacing(6)

        self.lbl_manual_x = QLabel()
        self.crop_x = QSpinBox()
        self.crop_x.setRange(0, 99999)

        self.lbl_manual_y = QLabel()
        self.crop_y = QSpinBox()
        self.crop_y.setRange(0, 99999)

        self.lbl_manual_w = QLabel()
        self.crop_w = QSpinBox()
        self.crop_w.setRange(1, 99999)
        self.crop_w.setValue(800)

        self.lbl_manual_h = QLabel()
        self.crop_h = QSpinBox()
        self.crop_h.setRange(1, 99999)
        self.crop_h.setValue(600)

        self.lbl_manual_shape = QLabel()
        self.crop_aspect = QComboBox()
        self.crop_aspect.addItems(["", "1:1", "4:3", "3:2", "16:9", "9:16", "3:4", "2:3"]) # free item localized in update_ui_texts

        crop_grid.addWidget(self.lbl_manual_x, 0, 0)
        crop_grid.addWidget(self.crop_x, 0, 1)
        crop_grid.addWidget(self.lbl_manual_y, 1, 0)
        crop_grid.addWidget(self.crop_y, 1, 1)
        crop_grid.addWidget(self.lbl_manual_w, 2, 0)
        crop_grid.addWidget(self.crop_w, 2, 1)
        crop_grid.addWidget(self.lbl_manual_h, 3, 0)
        crop_grid.addWidget(self.crop_h, 3, 1)
        crop_grid.addWidget(self.lbl_manual_shape, 4, 0)
        crop_grid.addWidget(self.crop_aspect, 4, 1)
        manual_layout.addLayout(crop_grid)

        self.crop_skip_check = QCheckBox()
        manual_layout.addWidget(self.crop_skip_check)

        self.lbl_crop_hint = QLabel()
        self.lbl_crop_hint.setObjectName("dimLabel")
        self.lbl_crop_hint.setWordWrap(True)
        manual_layout.addWidget(self.lbl_crop_hint)

        # Nav bar inside panel
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
        manual_layout.addLayout(nav_row)

        self.crop_manual_panel.setVisible(False)
        layout.addWidget(self.crop_manual_panel)

        layout.addWidget(Separator())

        # Output settings
        self.lbl_crop_save_as = QLabel()
        layout.addWidget(self.lbl_crop_save_as)
        self.crop_format = QComboBox()
        self.crop_format.addItems(OUTPUT_FORMATS)
        self.crop_format.setCurrentText("PNG")
        layout.addWidget(self.crop_format)

        self.lbl_crop_save_to = QLabel()
        layout.addWidget(self.lbl_crop_save_to)
        self.crop_output_dir = QLineEdit()
        layout.addWidget(self.crop_output_dir)
        self.btn_crop_browse = QPushButton()
        self.btn_crop_browse.clicked.connect(self._crop_browse_output)
        layout.addWidget(self.btn_crop_browse)

        layout.addStretch(1)

        # Crop action button
        self.btn_crop = QPushButton()
        self.btn_crop.setObjectName("primaryBtn")
        self.btn_crop.clicked.connect(self._run_crop)
        layout.addWidget(self.btn_crop)

    # ── Signal Event Handlers ────────────────────────────────

    def _on_feature_mode_changed(self, id_: int, checked: bool):
        """Swaps stacks and updates previews when active feature mode is toggled."""
        if not checked:
            return
        if id_ == 0:
            # Convert mode
            self.viewport_stack.setCurrentIndex(0)
            self.options_stack.setCurrentIndex(0)
        else:
            # Crop mode
            self.options_stack.setCurrentIndex(1)
            if self.crop_radio_manual.isChecked():
                self.viewport_stack.setCurrentIndex(2)
            else:
                self.viewport_stack.setCurrentIndex(1)
        self._on_file_selected(self.file_list.currentRow())

    def _on_file_selected(self, row: int):
        """Triggered when a row in the unified file list is highlighted."""
        if row < 0 or row >= self.file_list.count():
            self._clear_viewport()
            return
        
        path = self.file_list.item(row).data(Qt.UserRole)
        
        # Load image based on active feature
        if self.btn_convert_mode.isChecked():
            # Convert mode
            self._load_convert_preview(path)
        else:
            # Crop mode
            if self.crop_radio_same.isChecked():
                self._crop_same_load_preview(path)
            else:
                self._crop_load_image(row)

    def _clear_viewport(self):
        """Reset all viewports to empty state."""
        self.convert_preview.clear_image()
        self.crop_same_view.clear_image()
        self.crop_manual_view.clear_image()
        self.crop_nav_label.setText("")

    def _load_convert_preview(self, path: str):
        """Load selected image into Convert mode's fitted previewer."""
        try:
            pil_img = open_image(Path(path))
            self.convert_preview.load_image(pil_img)
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    # ── Unified File management helpers ─────────────────────

    def _add_files(self):
        """Open file dialog to add individual images."""
        files, _ = QFileDialog.getOpenFileNames(
            self, self.i18n("add_files"), "",
            file_filter_string(self.i18n),
        )
        for f in files:
            self._add_path(f)
        self._update_count()
        self._auto_load_preview()

    def _add_folder(self):
        """Open folder dialog and add all images from it."""
        folder = QFileDialog.getExistingDirectory(self, self.i18n("add_folder"))
        if not folder:
            return
        recursive = self.subfolder_check.isChecked()
        pattern = "**/*" if recursive else "*"
        folder_path = Path(folder)
        try:
            for f in sorted(folder_path.glob(pattern)):
                if f.is_file() and f.suffix.lower() in INPUT_EXTS:
                    self._add_path(str(f))
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  Error reading folder: {e}", "err")
        self._update_count()
        self._auto_load_preview()

    def _add_path(self, path: str):
        """Add a single file path to the list (no duplicates)."""
        if path in self._files:
            return
        self._files.append(path)
        item = QListWidgetItem()
        p = Path(path)
        try:
            img = Image.open(path)
            w, h = img.size
            img.close()
            item.setText(f"{p.name}   ({w}×{h})")
        except Exception:
            item.setText(p.name)
        item.setData(Qt.UserRole, path)
        self.file_list.addItem(item)

    def _remove_selected(self):
        """Remove selected items from the file list."""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        rows = sorted([self.file_list.row(item) for item in selected_items], reverse=True)
        for row in rows:
            self.file_list.takeItem(row)
            if row < len(self._files):
                self._files.pop(row)
            # Remove from crop settings data if it exists
            if row in self._crop_data:
                del self._crop_data[row]
        
        # Shift indices in self._crop_data for correct mapping
        for r in rows:
            temp_crop_data = {}
            for idx, val in self._crop_data.items():
                if idx < r:
                    temp_crop_data[idx] = val
                elif idx > r:
                    temp_crop_data[idx - 1] = val
            self._crop_data = temp_crop_data

        self._update_count()
        self._auto_load_preview()

    def _clear_all(self):
        """Clear all items from the file list."""
        self.file_list.clear()
        self._files.clear()
        self._crop_data.clear()
        self._clear_viewport()
        self._update_count()

    def _update_count(self):
        """Update the file count label."""
        count = self.file_list.count()
        if count == 0:
            self.count_label.setText(self.i18n("no_files"))
        else:
            self.count_label.setText(f"{count} {self.i18n('files_in_list')}")

    def _auto_load_preview(self):
        """Auto load preview of first image if nothing is selected."""
        if self.file_list.count() > 0 and self.file_list.currentRow() < 0:
            self.file_list.setCurrentRow(0)

    def _conv_browse_output(self):
        """Browse for convert output directory."""
        folder = QFileDialog.getExistingDirectory(self, self.i18n("save_to"))
        if folder:
            self.conv_output_dir.setText(folder)

    def _crop_browse_output(self):
        """Browse for crop output directory."""
        folder = QFileDialog.getExistingDirectory(self, self.i18n("save_to"))
        if folder:
            self.crop_output_dir.setText(folder)

    # ── Crop tab: mode switching ─────────────────────────────

    def _crop_mode_changed(self, id_: int, checked: bool):
        if not checked:
            return
        is_manual = (id_ == 1)
        self.crop_same_panel.setVisible(not is_manual)
        self.crop_manual_panel.setVisible(is_manual)
        
        if self.btn_crop_mode.isChecked():
            self.viewport_stack.setCurrentIndex(2 if is_manual else 1)
            
        row = self.file_list.currentRow()
        if row >= 0 and row < self.file_list.count():
            path = self.file_list.item(row).data(Qt.UserRole)
            if is_manual:
                self._crop_load_image(row)
            else:
                self._crop_same_load_preview(path)

    # ── Crop tab: one-by-one navigation ──────────────────────

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
        """Save the current crop fields into the data dict for this image."""
        row = self.file_list.currentRow()
        if row < 0:
            return
        self._crop_data[row] = {
            "x": self.crop_x.value(),
            "y": self.crop_y.value(),
            "w": self.crop_w.value(),
            "h": self.crop_h.value(),
            "skip": self.crop_skip_check.isChecked(),
        }

    def _crop_load_image(self, index: int):
        """Load image at the given index into the one-by-one interactive view."""
        if index < 0 or index >= self.file_list.count():
            return
        self._crop_index = index

        # Update navigation label
        self._update_crop_nav_label()
        self.crop_prev_btn.setEnabled(index > 0)
        self.crop_next_btn.setEnabled(index < self.file_list.count() - 1)

        # Load image into the interactive view
        path = self._files[index]
        try:
            pil_img = open_image(Path(path))
            iw, ih = pil_img.size
            self.crop_manual_view.load_image(pil_img)

            # Restore saved settings or defaults
            self._crop_updating = True
            if index in self._crop_data:
                d = self._crop_data[index]
                self.crop_x.setValue(d["x"])
                self.crop_y.setValue(d["y"])
                self.crop_w.setValue(d["w"])
                self.crop_h.setValue(d["h"])
                self.crop_skip_check.setChecked(d["skip"])
            else:
                self.crop_x.setValue(0)
                self.crop_y.setValue(0)
                self.crop_w.setValue(iw)
                self.crop_h.setValue(ih)
                self.crop_skip_check.setChecked(False)
            self._crop_updating = False

            # Sync the view to match spinbox values
            self.crop_manual_view.set_crop_rect(
                self.crop_x.value(), self.crop_y.value(),
                self.crop_w.value(), self.crop_h.value(),
            )

        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    # ── Crop tab: auto-load preview ──────────────────────────

    def _crop_same_load_preview(self, path: str):
        """Load an image into the same-size mode preview."""
        try:
            pil_img = open_image(Path(path))
            self.crop_same_view.load_image(pil_img)
            # Set crop rect based on current w/h and anchor
            self._crop_same_update_view()
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    def _update_crop_nav_label(self):
        """Updates manual crop navigation label."""
        row = self.file_list.currentRow()
        total = self.file_list.count()
        if row >= 0 and total > 0:
            self.crop_nav_label.setText(
                self.i18n("crop_image_n_of", current=row + 1, total=total)
            )
        else:
            self.crop_nav_label.setText("")

    # ── Crop tab: same-size ↔ view sync ──────────────────────

    def _crop_same_on_view_changed(self, x, y, w, h):
        """Handle mouse crop change in same-size preview."""
        if self._crop_updating:
            return
        self._crop_updating = True
        self.crop_same_w.setValue(w)
        self.crop_same_h.setValue(h)
        self._crop_updating = False

    def _crop_same_update_view(self):
        """Update same-size preview when spinboxes or anchor change."""
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

        anchor_text = self.crop_anchor.currentText()
        if anchor_text == self.i18n("crop_top_left"):
            cx, cy = 0, 0
        else:  # center
            cx = max(0, (iw - cw) // 2)
            cy = max(0, (ih - ch) // 2)

        self.crop_same_view.set_crop_rect(cx, cy, cw, ch)

    # ── Crop tab: one-by-one ↔ view sync ─────────────────────

    def _crop_manual_on_view_changed(self, x, y, w, h):
        """Handle mouse crop change in one-by-one view."""
        if self._crop_updating:
            return
        self._crop_updating = True
        self.crop_x.setValue(x)
        self.crop_y.setValue(y)
        self.crop_w.setValue(w)
        self.crop_h.setValue(h)
        self._crop_updating = False

    def _crop_manual_update_view(self):
        """Update one-by-one view when spinboxes change."""
        if self._crop_updating:
            return
        self.crop_manual_view.set_crop_rect(
            self.crop_x.value(), self.crop_y.value(),
            self.crop_w.value(), self.crop_h.value(),
        )

    def _crop_update_aspect_ratio(self):
        """Update the manual view's aspect ratio from the combo."""
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

    # ── Convert tab: run conversion ──────────────────────────

    def _run_convert(self):
        """Run the conversion in a background thread."""
        count = self.file_list.count()
        if count == 0:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_files"))
            return

        out_dir = self.conv_output_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_output"))
            return

        # Gather parameters
        fmt = self.conv_format.currentText()
        quality = self.conv_quality_slider.value()
        ext_out = EXT_MAP.get(fmt, ".png")
        w = self.conv_width.value() or None
        h = self.conv_height.value() or None
        scale_pct = self.conv_scale.value() or None
        scale = (scale_pct / 100) if scale_pct else None

        # Collect file paths
        files = []
        for i in range(count):
            files.append(self.file_list.item(i).data(Qt.UserRole))

        out_path = Path(out_dir)

        def task():
            ok, err = 0, 0
            self._signals.progress.emit(0)
            self._log(f"{self.i18n('log_arrow')}  {len(files)} {self.i18n('log_files_found')}", "inf")

            for idx, fpath in enumerate(files, 1):
                src_path = Path(fpath)
                dst = out_path / (src_path.stem + ext_out)
                try:
                    is_svg = src_path.suffix.lower() == ".svg"
                    if is_svg:
                        img = open_image(src_path, svg_width=w, svg_height=h, svg_scale=scale)
                    else:
                        img = open_image(src_path)
                        if w or h or scale:
                            img = do_resize(img, width=w, height=h, scale=scale)
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

            self._log(
                f"{self.i18n('log_completed')} {ok} {self.i18n('log_ok_count')}, {err} {self.i18n('log_err_count')}.",
                "inf",
            )
            self._signals.finished.emit()

        threading.Thread(target=task, daemon=True).start()

    # ── Crop tab: run crop ───────────────────────────────────

    def _run_crop(self):
        """Run crop in a background thread."""
        count = self.file_list.count()
        if count == 0:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_files"))
            return

        out_dir = self.crop_output_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_output"))
            return

        # Save current manual settings if in manual mode
        if self.crop_radio_manual.isChecked():
            self._crop_save_current_settings()

        is_same_mode = self.crop_radio_same.isChecked()
        fmt = self.crop_format.currentText()
        ext_out = EXT_MAP.get(fmt, ".png")
        out_path = Path(out_dir)

        # Same-size parameters
        same_w = self.crop_same_w.value()
        same_h = self.crop_same_h.value()
        anchor_text = self.crop_anchor.currentText()
        anchor = "top-left" if anchor_text == self.i18n("crop_top_left") else "center"

        # Copy per-image crop data
        crop_data = dict(self._crop_data)
        files = [self.file_list.item(i).data(Qt.UserRole) for i in range(count)]

        def task():
            ok, err, skipped = 0, 0, 0
            self._signals.progress.emit(0)
            total = len(files)

            for idx, fpath in enumerate(files, 1):
                src_path = Path(fpath)
                dst = out_path / (src_path.stem + "_cropped" + ext_out)

                if is_same_mode:
                    # Same-size mode
                    try:
                        img = open_image(src_path)
                        cropped = do_center_crop(img, same_w, same_h, anchor)
                        save_image(cropped, dst, fmt_override=fmt)
                        self._log(
                            f"{self.i18n('log_success')}  {src_path.name}  {self.i18n('log_arrow')}  {dst.name}  {cropped.size}",
                            "ok",
                        )
                        ok += 1
                    except Exception as e:
                        self._log(f"{self.i18n('log_error')}  {src_path.name}: {e}", "err")
                        err += 1
                else:
                    # Manual mode — check per-image settings
                    settings = crop_data.get(idx - 1)
                    if settings and settings.get("skip"):
                        skipped += 1
                        self._signals.progress.emit(int(idx / total * 100))
                        continue

                    if settings:
                        cx, cy = settings["x"], settings["y"]
                        cw, ch = settings["w"], settings["h"]
                    else:
                        # Default: no crop (full image)
                        cx, cy, cw, ch = 0, 0, 0, 0

                    try:
                        img = open_image(src_path)
                        if cw > 0 and ch > 0:
                            cropped = do_crop(img, cx, cy, cw, ch)
                        else:
                            cropped = img
                        save_image(cropped, dst, fmt_override=fmt)
                        self._log(
                            f"{self.i18n('log_success')}  {src_path.name}  {self.i18n('log_arrow')}  {dst.name}  {cropped.size}",
                            "ok",
                        )
                        ok += 1
                    except Exception as e:
                        self._log(f"{self.i18n('log_error')}  {src_path.name}: {e}", "err")
                        err += 1

                self._signals.progress.emit(int(idx / total * 100))

            summary = f"{self.i18n('log_completed')} {ok} {self.i18n('log_ok_count')}, {err} {self.i18n('log_err_count')}."
            if skipped:
                summary += f" ({skipped} skipped)"
            self._log(summary, "inf")
            self._signals.finished.emit()

        threading.Thread(target=task, daemon=True).start()

