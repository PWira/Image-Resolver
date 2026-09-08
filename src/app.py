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
    QColorDialog, QTabWidget, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QDialogButtonBox, QFormLayout,
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QPixmap, QColor, QIcon
from PIL import Image

from src.constants import OUTPUT_FORMATS, EXT_MAP, INPUT_EXTS, LUT_EXTS
from src.image_processor import (
    open_image, save_image, do_resize, do_crop, do_center_crop,
    composite_folder_images
)
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


class FolderSettingsDialog(QDialog):
    """Dialog for configuring folder manipulation mode and single-image layer export mode."""

    def __init__(self, parent=None, title="Folder Settings", name="New Folder", mode="same", export_mode="separate", merge_layout="vertical", i18n=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.i18n = i18n or (lambda k: k)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        self.name_edit = QLineEdit(name)
        form.addRow("Folder Name:", self.name_edit)
        layout.addLayout(form)

        # Manipulation mode group
        mode_group_box = QGroupBox(self.i18n("folder_mode"))
        mode_layout = QVBoxLayout(mode_group_box)
        self.radio_mode_same = QRadioButton(self.i18n("mode_same"))
        self.radio_mode_indiv = QRadioButton(self.i18n("mode_individual"))
        if mode == "same":
            self.radio_mode_same.setChecked(True)
        else:
            self.radio_mode_indiv.setChecked(True)
        mode_layout.addWidget(self.radio_mode_same)
        mode_layout.addWidget(self.radio_mode_indiv)
        layout.addWidget(mode_group_box)

        # Export mode group
        export_group_box = QGroupBox(self.i18n("folder_export_mode"))
        exp_layout = QVBoxLayout(export_group_box)
        self.radio_exp_sep = QRadioButton(self.i18n("export_separate_files"))
        self.radio_exp_single = QRadioButton(self.i18n("export_single_image"))
        if export_mode == "single_image":
            self.radio_exp_single.setChecked(True)
        else:
            self.radio_exp_sep.setChecked(True)
        exp_layout.addWidget(self.radio_exp_sep)
        exp_layout.addWidget(self.radio_exp_single)

        # Merge Layout combo
        layout_row = QHBoxLayout()
        layout_row.addWidget(QLabel(self.i18n("merge_layout") + ":"))
        self.combo_layout = QComboBox()
        self.combo_layout.addItem(self.i18n("layout_vertical"), "vertical")
        self.combo_layout.addItem(self.i18n("layout_horizontal"), "horizontal")
        self.combo_layout.addItem(self.i18n("layout_grid"), "grid")
        self.combo_layout.addItem(self.i18n("layout_overlay"), "overlay")

        idx = self.combo_layout.findData(merge_layout)
        if idx >= 0:
            self.combo_layout.setCurrentIndex(idx)
        layout_row.addWidget(self.combo_layout)
        exp_layout.addLayout(layout_row)

        # Keep combo_layout enabled and interactive always
        self.combo_layout.setEnabled(True)

        layout.addWidget(export_group_box)

        # Button Box
        bbox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bbox.accepted.connect(self.accept)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

    def get_settings(self):
        selected_data = self.combo_layout.currentData()
        if not selected_data:
            selected_data = "vertical"
        return {
            "name": self.name_edit.text().strip() or "Folder",
            "mode": "same" if self.radio_mode_same.isChecked() else "individual",
            "export_mode": "single_image" if self.radio_exp_single.isChecked() else "separate",
            "merge_layout": selected_data
        }


class CustomFileTreeWidget(QTreeWidget):
    """QTreeWidget with custom drag-and-drop behavior to insert dropped files at index 0 of target folder."""

    def dropEvent(self, event):
        target_item = self.itemAt(event.position().toPoint())
        selected_items = self.selectedItems()
        if not selected_items:
            super().dropEvent(event)
            return

        folder_item = None
        if target_item:
            if target_item.data(0, Qt.UserRole + 1) == "folder":
                folder_item = target_item
            elif target_item.parent() and target_item.parent().data(0, Qt.UserRole + 1) == "folder":
                folder_item = target_item.parent()

        if folder_item:
            items_to_move = [i for i in selected_items if i != folder_item]
            for item in reversed(items_to_move):
                parent = item.parent()
                if parent:
                    parent.removeChild(item)
                else:
                    idx = self.indexOfTopLevelItem(item)
                    if idx >= 0:
                        self.takeTopLevelItem(idx)
                # Prepend at very top (index 0)
                folder_item.insertChild(0, item)
            folder_item.setExpanded(True)
            event.accept()
            main_win = self.window()
            if hasattr(main_win, "_update_folder_item_display"):
                main_win._update_folder_item_display(folder_item)
            if hasattr(main_win, "_auto_save_temp"):
                main_win._auto_save_temp()
        else:
            super().dropEvent(event)


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
        self._crop_mode = self.CROP_NONE
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
        # Connect signals for LUT
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
        self.output_filename_edit.textChanged.connect(self._auto_save_temp)
        self.conv_format.currentIndexChanged.connect(self._auto_save_temp)
        self.conv_quality_slider.valueChanged.connect(self._auto_save_temp)
        self.conv_width.valueChanged.connect(self._auto_save_temp)
        self.conv_height.valueChanged.connect(self._auto_save_temp)
        self.conv_scale.valueChanged.connect(self._auto_save_temp)

        self.crop_enable_check.toggled.connect(self._auto_save_temp)
        self.lut_enable_check.toggled.connect(self._auto_save_temp)
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
        self._on_file_selected(self._get_current_file_index())

    def _choose_custom_color(self):
        initial = QColor(theme.GOLD)
        color = QColorDialog.getColor(initial, self, self.i18n("custom_color"))
        if color.isValid():
            hex_color = color.name().upper()
            theme.set_custom_accent(hex_color)
            self.setStyleSheet(theme.get_stylesheet())
            self._save_settings()
            self._update_ui_texts()
            self._on_file_selected(self._get_current_file_index())

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
        self.btn_add.setText(self.i18n("add_files_or_folder"))
        self.act_add_files.setText("📄 " + self.i18n("add_files"))
        self.act_add_folder.setText("📁 " + self.i18n("add_folder"))
        self.act_new_folder.setText("📂 " + self.i18n("new_folder"))
        self.btn_new_folder.setText(self.i18n("new_folder"))
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
        self.crop_enable_check.setText(self.i18n("enable_crop"))

        self.lbl_same_w.setText(self.i18n("crop_width"))
        self.lbl_same_h.setText(self.i18n("crop_height"))
        self.lbl_same_from.setText(self.i18n("crop_from"))

        curr_anchor = self.crop_anchor.currentIndex()
        self.crop_anchor.clear()
        self.crop_anchor.addItems([
            self.i18n("crop_center"),
            self.i18n("crop_top_left"),
            self.i18n("crop_top_right"),
            self.i18n("crop_bottom_left"),
            self.i18n("crop_bottom_right"),
            self.i18n("crop_top_center"),
            self.i18n("crop_bottom_center"),
        ])
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
        self.lut_enable_check.setText(self.i18n("enable_lut"))

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
        self.lbl_custom_filename.setText(self.i18n("custom_filename"))
        self.output_filename_edit.setPlaceholderText(self.i18n("custom_filename_placeholder"))
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
        self._signals = _WorkerSignals()
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
        self.btn_add        = QPushButton()
        self.btn_new_folder = QPushButton()
        self.btn_remove     = QPushButton()
        self.btn_clear      = QPushButton()

        # Build dropdown menu for unified Add button
        self.add_menu = QMenu(self)
        self.act_add_files = self.add_menu.addAction("📄 " + self.i18n("add_files"))
        self.act_add_files.triggered.connect(self._add_files)
        self.act_add_folder = self.add_menu.addAction("📁 " + self.i18n("add_folder"))
        self.act_add_folder.triggered.connect(self._add_folder)
        self.add_menu.addSeparator()
        self.act_new_folder = self.add_menu.addAction("📂 " + self.i18n("new_folder"))
        self.act_new_folder.triggered.connect(self._create_new_folder)
        self.btn_add.setMenu(self.add_menu)

        self.btn_new_folder.clicked.connect(self._create_new_folder)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_clear.clicked.connect(self._clear_all)

        btn_grid.addWidget(self.btn_add,        0, 0)
        btn_grid.addWidget(self.btn_new_folder, 0, 1)
        btn_grid.addWidget(self.btn_remove,     1, 0)
        btn_grid.addWidget(self.btn_clear,      1, 1)
        layout.addLayout(btn_grid)

        self.subfolder_check = QCheckBox()
        layout.addWidget(self.subfolder_check)

        self.file_tree = CustomFileTreeWidget()
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self._show_tree_context_menu)
        self.file_tree.currentItemChanged.connect(self._on_tree_item_changed)
        self.file_tree.setMinimumWidth(180)
        layout.addWidget(self.file_tree, stretch=1)

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

        self.crop_enable_check = QCheckBox()
        self.crop_enable_check.toggled.connect(self._on_crop_enable_toggled)
        adj_layout.addWidget(self.crop_enable_check)

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

        self.lut_enable_check = QCheckBox()
        self.lut_enable_check.toggled.connect(self._on_lut_enable_toggled)
        lut_layout.addWidget(self.lut_enable_check)

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

        # Custom Filename
        self.lbl_custom_filename = QLabel()
        exp_layout.addWidget(self.lbl_custom_filename)
        self.output_filename_edit = QLineEdit()
        self.output_filename_edit.setClearButtonEnabled(True)
        exp_layout.addWidget(self.output_filename_edit)

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

    def _on_crop_enable_toggled(self, checked: bool):
        self._update_crop_visibility()
        self._auto_save_temp()

    def _on_lut_enable_toggled(self, checked: bool):
        self._update_lut_visibility()
        self._auto_save_temp()

    def _update_crop_visibility(self):
        enabled = self.crop_enable_check.isChecked()
        curr_folder = self._get_folder_node_for_item(self.file_tree.currentItem())
        folder_mode = curr_folder.data(0, Qt.UserRole + 3) if curr_folder else "same"

        if not enabled:
            self._crop_mode = self.CROP_NONE
            self.crop_same_panel.setVisible(False)
            self.crop_manual_panel.setVisible(False)
            self.viewport_stack.setCurrentIndex(0)
        else:
            if folder_mode == "same":
                self._crop_mode = self.CROP_SAME
                self.crop_same_panel.setVisible(True)
                self.crop_manual_panel.setVisible(False)
                self.viewport_stack.setCurrentIndex(1)
            else:
                self._crop_mode = self.CROP_MANUAL
                self.crop_same_panel.setVisible(False)
                self.crop_manual_panel.setVisible(True)
                self.viewport_stack.setCurrentIndex(2)

        row = self._get_current_file_index()
        all_items = self._get_all_file_items()
        if 0 <= row < len(all_items):
            path = all_items[row].data(0, Qt.UserRole)
            if self._crop_mode == self.CROP_NONE:
                self._load_convert_preview(path)
            elif self._crop_mode == self.CROP_SAME:
                self._crop_same_load_preview(path)
            elif self._crop_mode == self.CROP_MANUAL:
                self._crop_load_image(row)

    def _update_lut_visibility(self):
        enabled = self.lut_enable_check.isChecked()
        curr_folder = self._get_folder_node_for_item(self.file_tree.currentItem())
        folder_mode = curr_folder.data(0, Qt.UserRole + 3) if curr_folder else "same"

        if not enabled:
            self._lut_mode = self.LUT_NONE
            self.lut_controls_panel.setVisible(False)
            self.lut_manual_nav_panel.setVisible(False)
        else:
            if folder_mode == "same":
                self._lut_mode = self.LUT_SAME
                self.lut_controls_panel.setVisible(True)
                self.lut_manual_nav_panel.setVisible(False)
            else:
                self._lut_mode = self.LUT_MANUAL
                self.lut_controls_panel.setVisible(True)
                self.lut_manual_nav_panel.setVisible(True)

        self._refresh_current_preview(retain_zoom=True)

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
            row = self._get_current_file_index()
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
            row = self._get_current_file_index()
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
                row = self._get_current_file_index()
            if row in self._lut_per_image_data:
                d = self._lut_per_image_data[row]
                return d.get("obj"), d.get("intensity", 1.0)
        return None, 1.0

    def _lut_go_prev(self):
        all_items = self._get_all_file_items()
        row = self._get_current_file_index()
        if row > 0:
            self.file_tree.setCurrentItem(all_items[row - 1])

    def _lut_go_next(self):
        all_items = self._get_all_file_items()
        row = self._get_current_file_index()
        if 0 <= row < len(all_items) - 1:
            self.file_tree.setCurrentItem(all_items[row + 1])

    def _lut_load_image_settings(self, index: int):
        total = len(self._get_all_file_items())
        if index < 0 or index >= total:
            return
        self._update_lut_nav_label()
        self.lut_prev_btn.setEnabled(index > 0)
        self.lut_next_btn.setEnabled(index < total - 1)
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
        row = self._get_current_file_index()
        total = len(self._get_all_file_items())
        if row >= 0 and total > 0:
            self.lut_nav_label.setText(self.i18n("crop_image_n_of", current=row + 1, total=total))
        else:
            self.lut_nav_label.setText("")

    def _refresh_current_preview(self, retain_zoom: bool = True):
        curr_item = self._get_current_file_item()
        if not curr_item:
            return
        path = curr_item.data(0, Qt.UserRole)
        if not path:
            return
        row = self._get_current_file_index()
        mode = self._crop_mode
        if mode == self.CROP_NONE:
            self._load_convert_preview(path, retain_zoom=retain_zoom)
        elif mode == self.CROP_SAME:
            self._crop_same_load_preview(path, retain_zoom=retain_zoom)
        elif mode == self.CROP_MANUAL:
            self._crop_load_image(row, retain_zoom=retain_zoom)

    def _on_file_selected(self, row: int):
        all_items = self._get_all_file_items()
        if row < 0 or row >= len(all_items):
            self._clear_viewport()
            return
        item = all_items[row]
        self.file_tree.setCurrentItem(item)

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
            row = self._get_current_file_index()
            img = self._get_preview_image(path)
            lut_obj, intensity = self._get_active_lut(row)
            if lut_obj:
                img = apply_lut(img, lut_obj, intensity)
            self.convert_preview.load_image(img, retain_zoom=retain_zoom)
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    # ---- Tree and File management ----

    def _get_all_file_items(self) -> list[QTreeWidgetItem]:
        items = []
        root = self.file_tree.invisibleRootItem()
        def search(item):
            for i in range(item.childCount()):
                child = item.child(i)
                kind = child.data(0, Qt.UserRole + 1)
                if kind == "file":
                    items.append(child)
                elif kind == "folder":
                    search(child)
        search(root)
        return items

    def _get_all_file_paths(self) -> list[str]:
        paths = []
        for item in self._get_all_file_items():
            p = item.data(0, Qt.UserRole)
            if p:
                paths.append(p)
        return paths

    def _get_current_file_item(self) -> Optional[QTreeWidgetItem]:
        curr = self.file_tree.currentItem()
        if curr and curr.data(0, Qt.UserRole + 1) == "file":
            return curr
        return None

    def _get_current_folder_item(self) -> Optional[QTreeWidgetItem]:
        curr = self.file_tree.currentItem()
        if not curr:
            return None
        if curr.data(0, Qt.UserRole + 1) == "folder":
            return curr
        parent = curr.parent()
        if parent and parent.data(0, Qt.UserRole + 1) == "folder":
            return parent
        return None

    def _get_current_file_index(self) -> int:
        curr_item = self._get_current_file_item()
        if not curr_item:
            return -1
        all_items = self._get_all_file_items()
        try:
            return all_items.index(curr_item)
        except ValueError:
            return -1

    def _create_file_tree_item(self, path: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem()
        item.setData(0, Qt.UserRole, path)
        item.setData(0, Qt.UserRole + 1, "file")
        p = Path(path)
        try:
            img = Image.open(path)
            w, h = img.size
            img.close()
            item.setText(0, f"📄 {p.name}   ({w}×{h})")
        except Exception:
            item.setText(0, f"📄 {p.name}")
        return item

    def _update_folder_item_display(self, folder_item: QTreeWidgetItem):
        name = folder_item.data(0, Qt.UserRole + 2) or "Folder"
        mode = folder_item.data(0, Qt.UserRole + 3) or "same"
        exp_mode = folder_item.data(0, Qt.UserRole + 4) or "separate"

        count = folder_item.childCount()
        mode_str = "Same" if mode == "same" else "Indiv"
        exp_str = "Single Img" if exp_mode == "single_image" else "Sep Files"

        folder_item.setText(0, f"📁 {name}   ({count})   [{mode_str} | {exp_str}]")

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, self.i18n("add_files"), "", file_filter_string(self.i18n))
        if files:
            target_parent = self._get_current_folder_item()
            self._add_paths_sequential(files, target_parent=target_parent)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.i18n("add_folder"))
        if not folder:
            return
        recursive = self.subfolder_check.isChecked()
        pattern = "**/*" if recursive else "*"
        try:
            matched_files = []
            for f in sorted(Path(folder).glob(pattern)):
                if f.is_file() and f.suffix.lower() in INPUT_EXTS:
                    matched_files.append(str(f))
            if matched_files:
                folder_name = Path(folder).name or "Imported Folder"
                f_item = QTreeWidgetItem()
                f_item.setData(0, Qt.UserRole + 1, "folder")
                f_item.setData(0, Qt.UserRole + 2, folder_name)
                f_item.setData(0, Qt.UserRole + 3, "same")
                f_item.setData(0, Qt.UserRole + 4, "separate")
                f_item.setData(0, Qt.UserRole + 5, "vertical")
                self._update_folder_item_display(f_item)
                self.file_tree.addTopLevelItem(f_item)
                f_item.setExpanded(True)

                self._add_paths_sequential(matched_files, target_parent=f_item)
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  Error reading folder: {e}", "err")

    def _add_paths_sequential(self, file_paths: list[str], target_parent=None):
        if not file_paths:
            return
        existing = set(self._get_all_file_paths())
        new_paths = [p for p in file_paths if p not in existing and Path(p).exists()]
        if not new_paths:
            return

        CHUNK_SIZE = 35
        total = len(new_paths)

        def process_chunk(start_idx):
            end_idx = min(start_idx + CHUNK_SIZE, total)
            for i in range(start_idx, end_idx):
                fpath = new_paths[i]
                item = self._create_file_tree_item(fpath)
                if target_parent:
                    target_parent.addChild(item)
                else:
                    self.file_tree.addTopLevelItem(item)
                if fpath not in self._files:
                    self._files.append(fpath)

            if target_parent:
                self._update_folder_item_display(target_parent)

            self._update_count()
            QApplication.processEvents()

            if end_idx < total:
                QTimer.singleShot(1, lambda: process_chunk(end_idx))
            else:
                self._update_count()
                self._auto_load_preview()
                self._auto_save_temp()
                self._log(f"{self.i18n('log_success')}  Imported {total} images.", "ok")

        process_chunk(0)

    def _create_new_folder(self):
        dlg = FolderSettingsDialog(self, title=self.i18n("new_folder"), name="New Folder", i18n=self.i18n)
        if dlg.exec() == QDialog.Accepted:
            st = dlg.get_settings()
            item = QTreeWidgetItem()
            item.setData(0, Qt.UserRole + 1, "folder")
            item.setData(0, Qt.UserRole + 2, st["name"])
            item.setData(0, Qt.UserRole + 3, st["mode"])
            item.setData(0, Qt.UserRole + 4, st["export_mode"])
            item.setData(0, Qt.UserRole + 5, st["merge_layout"])
            self._update_folder_item_display(item)

            self.file_tree.addTopLevelItem(item)
            item.setExpanded(True)
            self._auto_save_temp()

    def _show_tree_context_menu(self, pos):
        item = self.file_tree.itemAt(pos)
        menu = QMenu(self)
        if item:
            kind = item.data(0, Qt.UserRole + 1)
            if kind == "folder":
                act_settings = menu.addAction("⚙️ " + self.i18n("folder_properties"))
                act_settings.triggered.connect(lambda: self._edit_folder_settings(item))
                act_del = menu.addAction("❌ " + self.i18n("remove_selected"))
                act_del.triggered.connect(lambda: self._delete_tree_item(item))
            elif kind == "file":
                act_del = menu.addAction("❌ " + self.i18n("remove_selected"))
                act_del.triggered.connect(lambda: self._delete_tree_item(item))
        else:
            act_add = menu.addAction("📄 " + self.i18n("add_files"))
            act_add.triggered.connect(self._add_files)
            act_folder = menu.addAction("📁 " + self.i18n("add_folder"))
            act_folder.triggered.connect(self._add_folder)
            menu.addSeparator()
            act_new_folder = menu.addAction("📂 " + self.i18n("new_folder"))
            act_new_folder.triggered.connect(self._create_new_folder)
        menu.exec(self.file_tree.viewport().mapToGlobal(pos))

    def _edit_folder_settings(self, item: QTreeWidgetItem):
        name = item.data(0, Qt.UserRole + 2) or "Folder"
        mode = item.data(0, Qt.UserRole + 3) or "same"
        exp_mode = item.data(0, Qt.UserRole + 4) or "separate"
        layout = item.data(0, Qt.UserRole + 5) or "vertical"

        dlg = FolderSettingsDialog(
            self, title=self.i18n("folder_properties"),
            name=name, mode=mode, export_mode=exp_mode, merge_layout=layout,
            i18n=self.i18n
        )
        if dlg.exec() == QDialog.Accepted:
            st = dlg.get_settings()
            item.setData(0, Qt.UserRole + 2, st["name"])
            item.setData(0, Qt.UserRole + 3, st["mode"])
            item.setData(0, Qt.UserRole + 4, st["export_mode"])
            item.setData(0, Qt.UserRole + 5, st["merge_layout"])
            self._update_folder_item_display(item)
            self._auto_save_temp()

    def _get_folder_node_for_item(self, item: Optional[QTreeWidgetItem]) -> Optional[QTreeWidgetItem]:
        if not item:
            return None
        kind = item.data(0, Qt.UserRole + 1)
        if kind == "folder":
            return item
        parent = item.parent()
        if parent and parent.data(0, Qt.UserRole + 1) == "folder":
            return parent
        return None

    def _save_folder_state(self, folder_item: Optional[QTreeWidgetItem]):
        if not folder_item or folder_item.data(0, Qt.UserRole + 1) != "folder":
            return
        lut_state = {
            "lut_enabled": self.lut_enable_check.isChecked(),
            "lut_mode": self._lut_mode,
            "lut_same_file": self._lut_same_file,
            "lut_same_preset": self._lut_same_preset,
            "lut_same_intensity": self._lut_same_intensity,
            "lut_same_settings": dict(self._lut_same_settings) if hasattr(self, "_lut_same_settings") and self._lut_same_settings else {},
            "lut_same_obj": self._lut_same_obj,
            "lut_per_image_data": dict(self._lut_per_image_data),
        }
        crop_state = {
            "crop_enabled": self.crop_enable_check.isChecked(),
            "crop_mode": self._crop_mode,
            "crop_same_w": self.crop_same_w.value(),
            "crop_same_h": self.crop_same_h.value(),
            "crop_anchor": self.crop_anchor.currentIndex(),
            "crop_aspect": self.crop_aspect.currentIndex(),
            "crop_data": dict(self._crop_data),
        }
        folder_item.setData(0, Qt.UserRole + 6, lut_state)
        folder_item.setData(0, Qt.UserRole + 7, crop_state)

    def _load_folder_state(self, folder_item: Optional[QTreeWidgetItem]):
        if not folder_item or folder_item.data(0, Qt.UserRole + 1) != "folder":
            lut_state = {}
            crop_state = {}
        else:
            lut_state = folder_item.data(0, Qt.UserRole + 6) or {}
            crop_state = folder_item.data(0, Qt.UserRole + 7) or {}

        self._lut_updating = True
        self._crop_updating = True

        crop_enabled = crop_state.get("crop_enabled", crop_state.get("crop_mode", 0) != 0)
        self.crop_enable_check.setChecked(crop_enabled)

        lut_enabled = lut_state.get("lut_enabled", lut_state.get("lut_mode", 0) != 0)
        self.lut_enable_check.setChecked(lut_enabled)

        self._lut_same_file = lut_state.get("lut_same_file")
        self._lut_same_preset = lut_state.get("lut_same_preset")
        self._lut_same_intensity = lut_state.get("lut_same_intensity", 1.0)
        self._lut_same_settings = dict(lut_state.get("lut_same_settings", {
            "brightness": 0, "contrast": 0, "saturation": 0, "temperature": 0,
            "tint": 0, "gamma": 100, "hue_shift": 0, "r_gain": 100, "g_gain": 100, "b_gain": 100
        }))
        self._lut_same_obj = lut_state.get("lut_same_obj")
        self._lut_per_image_data = dict(lut_state.get("lut_per_image_data", {}))

        self.crop_same_w.setValue(crop_state.get("crop_same_w", 800))
        self.crop_same_h.setValue(crop_state.get("crop_same_h", 600))
        self.crop_anchor.setCurrentIndex(crop_state.get("crop_anchor", 0))
        self.crop_aspect.setCurrentIndex(crop_state.get("crop_aspect", 0))
        self._crop_data = dict(crop_state.get("crop_data", {}))

        self._lut_updating = False
        self._crop_updating = False

        self._update_crop_visibility()
        self._update_lut_visibility()

    def _on_tree_item_changed(self, current, previous):
        if previous:
            prev_folder = self._get_folder_node_for_item(previous)
            if prev_folder:
                self._save_folder_state(prev_folder)

        if not current:
            self._clear_viewport()
            return

        curr_folder = self._get_folder_node_for_item(current)
        if curr_folder:
            self._load_folder_state(curr_folder)
        else:
            self._load_folder_state(None)

        kind = current.data(0, Qt.UserRole + 1)
        if kind == "file":
            path = current.data(0, Qt.UserRole)
            if path:
                self._refresh_current_preview()
        elif kind == "folder":
            if current.childCount() > 0:
                first_child = current.child(0)
                path = first_child.data(0, Qt.UserRole)
                if path:
                    self._refresh_current_preview()

    def _delete_tree_item(self, item: QTreeWidgetItem, save_temp=True):
        if not item:
            return
        parent = item.parent()
        if parent:
            parent.removeChild(item)
            if parent.data(0, Qt.UserRole + 1) == "folder":
                self._update_folder_item_display(parent)
        else:
            idx = self.file_tree.indexOfTopLevelItem(item)
            if idx >= 0:
                self.file_tree.takeTopLevelItem(idx)

        kind = item.data(0, Qt.UserRole + 1)
        if kind == "file":
            p = item.data(0, Qt.UserRole)
            if p in self._files:
                self._files.remove(p)
        elif kind == "folder":
            for i in range(item.childCount()):
                cp = item.child(i).data(0, Qt.UserRole)
                if cp in self._files:
                    self._files.remove(cp)

        if save_temp:
            self._update_count()
            self._auto_save_temp()

    def _remove_selected(self):
        selected = self.file_tree.selectedItems()
        if not selected:
            return
        for item in selected:
            self._delete_tree_item(item, save_temp=False)
        self._update_count()
        self._auto_load_preview()
        self._auto_save_temp()

    def _clear_all(self):
        self._crop_index = None
        self.file_tree.clear()
        self._files.clear()
        self._crop_data.clear()
        self._lut_per_image_data.clear()
        self._preview_cache.clear()
        self._clear_viewport()
        self._update_count()
        self._auto_save_temp()

    def _update_count(self):
        count = len(self._get_all_file_items())
        if count == 0:
            self.count_label.setText(self.i18n("no_files"))
        else:
            self.count_label.setText(f"{count} {self.i18n('files_in_list')}")

    def _auto_load_preview(self):
        all_items = self._get_all_file_items()
        if all_items and not self.file_tree.currentItem():
            self.file_tree.setCurrentItem(all_items[0])

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, self.i18n("save_to"))
        if folder:
            self.output_dir.setText(folder)

    # ---- Crop helpers ----

    def _crop_go_prev(self):
        all_items = self._get_all_file_items()
        row = self._get_current_file_index()
        if row > 0:
            self._crop_save_current_settings()
            self.file_tree.setCurrentItem(all_items[row - 1])

    def _crop_go_next(self):
        all_items = self._get_all_file_items()
        row = self._get_current_file_index()
        if 0 <= row < len(all_items) - 1:
            self._crop_save_current_settings()
            self.file_tree.setCurrentItem(all_items[row + 1])

    def _crop_save_current_settings(self):
        row = self._get_current_file_index()
        if row < 0:
            return
        self._crop_data[row] = {
            "x": self.crop_x.value(), "y": self.crop_y.value(),
            "w": self.crop_w.value(), "h": self.crop_h.value(),
            "skip": self.crop_skip_check.isChecked(),
        }

    def _crop_load_image(self, index: int, retain_zoom: bool = False):
        all_items = self._get_all_file_items()
        total = len(all_items)
        if index < 0 or index >= total:
            return
        if self._crop_index is not None and 0 <= self._crop_index < total:
            self._crop_data[self._crop_index] = {
                "x": self.crop_x.value(), "y": self.crop_y.value(),
                "w": self.crop_w.value(), "h": self.crop_h.value(),
                "skip": self.crop_skip_check.isChecked(),
            }
        self._crop_index = index
        self._update_crop_nav_label()
        self.crop_prev_btn.setEnabled(index > 0)
        self.crop_next_btn.setEnabled(index < total - 1)
        try:
            path = all_items[index].data(0, Qt.UserRole)
            if not path:
                return
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
            row = self._get_current_file_index()
            pil_img = self._get_preview_image(path)
            lut_obj, intensity = self._get_active_lut(row)
            if lut_obj:
                pil_img = apply_lut(pil_img, lut_obj, intensity)
            self.crop_same_view.load_image(pil_img, retain_zoom=retain_zoom)
            self._crop_same_update_view()
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    def _update_crop_nav_label(self):
        row = self._get_current_file_index()
        total = len(self._get_all_file_items())
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
        all_file_items = self._get_all_file_items()
        total_files = len(all_file_items)
        if total_files == 0:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_files"))
            return
        out_dir = self.output_dir.text().strip()
        if not out_dir:
            QMessageBox.warning(self, self.i18n("error_title"), self.i18n("error_no_output"))
            return

        if self._crop_mode == self.CROP_MANUAL:
            self._crop_save_current_settings()

        fmt       = self.conv_format.currentText()
        quality   = self.conv_quality_slider.value()
        ext_out   = EXT_MAP.get(fmt, ".png")
        w         = self.conv_width.value() or None
        h         = self.conv_height.value() or None
        scale_pct = self.conv_scale.value() or None
        scale     = (scale_pct / 100) if scale_pct else None

        crop_mode      = self._crop_mode
        is_crop_same   = (crop_mode == self.CROP_SAME)
        is_crop_manual = (crop_mode == self.CROP_MANUAL)

        same_w      = self.crop_same_w.value()
        same_h      = self.crop_same_h.value()
        anchor_map  = {
            0: "center",
            1: "top-left",
            2: "top-right",
            3: "bottom-left",
            4: "bottom-right",
            5: "top-center",
            6: "bottom-center"
        }
        anchor_idx  = self.crop_anchor.currentIndex()
        anchor      = anchor_map.get(anchor_idx, "center")

        crop_data = dict(self._crop_data)
        out_path  = Path(out_dir)

        lut_mode = self._lut_mode
        lut_same_obj = self._lut_same_obj
        lut_same_intensity = self._lut_same_intensity
        lut_per_image_data = dict(self._lut_per_image_data)

        custom_raw = self.output_filename_edit.text().strip()
        if custom_raw:
            if custom_raw.lower().endswith(ext_out.lower()):
                custom_base = custom_raw[:-len(ext_out)]
            else:
                custom_base = Path(custom_raw).stem or custom_raw
        else:
            custom_base = None

        root = self.file_tree.invisibleRootItem()
        top_count = root.childCount()

        # Pre-plan destination paths for all outputs to check for file overwrites
        dest_map = {}  # item or (item, idx) -> Path
        all_destinations = []
        top_file_items = [root.child(i) for i in range(top_count) if root.child(i).data(0, Qt.UserRole + 1) == "file"]
        top_file_counter = 0

        for top_idx in range(top_count):
            top_item = root.child(top_idx)
            kind = top_item.data(0, Qt.UserRole + 1)

            if kind == "file":
                fpath = top_item.data(0, Qt.UserRole)
                if not fpath:
                    continue
                src_path = Path(fpath)
                top_file_counter += 1
                if custom_base:
                    if len(top_file_items) == 1 and top_count == 1:
                        dest_name = f"{custom_base}{ext_out}"
                    else:
                        dest_name = f"{custom_base}_{top_file_counter}{ext_out}"
                else:
                    dest_name = f"{src_path.stem}{ext_out}"
                
                dst = out_path / dest_name
                dest_map[top_item] = dst
                all_destinations.append(dst)

            elif kind == "folder":
                folder_name = top_item.data(0, Qt.UserRole + 2) or "Folder"
                folder_exp = top_item.data(0, Qt.UserRole + 4) or "separate"
                child_count = top_item.childCount()

                if folder_exp == "single_image":
                    if custom_base and top_count == 1:
                        dest_name = f"{custom_base}{ext_out}"
                    else:
                        dest_name = f"{folder_name}{ext_out}"
                    dst = out_path / dest_name
                    dest_map[top_item] = dst
                    all_destinations.append(dst)
                else:
                    sub_out = out_path / folder_name
                    for c_idx in range(child_count):
                        c_item = top_item.child(c_idx)
                        fpath = c_item.data(0, Qt.UserRole)
                        if not fpath:
                            continue
                        src_path = Path(fpath)
                        if custom_base:
                            dest_name = f"{custom_base}_{c_idx + 1}{ext_out}"
                        else:
                            dest_name = f"{src_path.stem}{ext_out}"
                        dst = sub_out / dest_name
                        dest_map[(top_item, c_idx)] = dst
                        all_destinations.append(dst)

        # Overwrite confirmation popup
        existing_files = [p for p in all_destinations if p.exists()]
        if existing_files:
            num_existing = len(existing_files)
            sample_names = [p.name for p in existing_files[:5]]
            if num_existing > 5:
                sample_str = "\n".join(f"• {name}" for name in sample_names) + f"\n• ... and {num_existing - 5} more"
            else:
                sample_str = "\n".join(f"• {name}" for name in sample_names)
            
            msg = self.i18n("overwrite_warning_msg", count=num_existing, files=sample_str)
            reply = QMessageBox.question(
                self,
                self.i18n("overwrite_warning_title"),
                msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        def process_image(src_path: Path, file_idx: int) -> Optional[Image.Image]:
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
                settings = crop_data.get(file_idx)
                if settings:
                    cx, cy = settings["x"], settings["y"]
                    cw, ch = settings["w"], settings["h"]
                    if cw > 0 and ch > 0:
                        img = do_crop(img, cx, cy, cw, ch)

            if lut_mode == self.LUT_SAME and lut_same_obj:
                img = apply_lut(img, lut_same_obj, lut_same_intensity)
            elif lut_mode == self.LUT_MANUAL:
                l_data = lut_per_image_data.get(file_idx)
                if l_data and l_data.get("obj"):
                    img = apply_lut(img, l_data["obj"], l_data.get("intensity", 1.0))
            return img

        def task():
            ok, err, skipped = 0, 0, 0
            self._signals.progress.emit(0)
            self._log(f"{self.i18n('log_arrow')}  {total_files} {self.i18n('log_files_found')}", "inf")

            processed_count = 0

            for top_idx in range(top_count):
                top_item = root.child(top_idx)
                kind = top_item.data(0, Qt.UserRole + 1)

                if kind == "file":
                    fpath = top_item.data(0, Qt.UserRole)
                    if not fpath:
                        continue
                    src_path = Path(fpath)
                    dst = dest_map.get(top_item, out_path / (src_path.stem + ext_out))
                    try:
                        file_idx = all_file_items.index(top_item)
                        if is_crop_manual:
                            s = crop_data.get(file_idx)
                            if s and s.get("skip"):
                                skipped += 1
                                processed_count += 1
                                self._signals.progress.emit(int(processed_count / total_files * 100))
                                continue

                        img = process_image(src_path, file_idx)
                        if img:
                            save_image(img, dst, quality=quality, fmt_override=fmt)
                            self._log(f"{self.i18n('log_success')}  {src_path.name} -> {dst.name}", "ok")
                            ok += 1
                    except Exception as e:
                        self._log(f"{self.i18n('log_error')}  {src_path.name}: {e}", "err")
                        traceback.print_exc()
                        err += 1
                    processed_count += 1
                    self._signals.progress.emit(int(processed_count / total_files * 100))

                elif kind == "folder":
                    folder_name = top_item.data(0, Qt.UserRole + 2) or "Folder"
                    folder_exp = top_item.data(0, Qt.UserRole + 4) or "separate"
                    merge_layout = top_item.data(0, Qt.UserRole + 5) or "vertical"
                    f_lut_state = top_item.data(0, Qt.UserRole + 6) or {}
                    f_crop_state = top_item.data(0, Qt.UserRole + 7) or {}

                    f_lut_enabled = f_lut_state.get("lut_enabled", f_lut_state.get("lut_mode", 0) != 0)
                    f_lut_mode = f_lut_state.get("lut_mode", lut_mode)
                    f_lut_same_obj = f_lut_state.get("lut_same_obj", lut_same_obj)
                    f_lut_same_intensity = f_lut_state.get("lut_same_intensity", lut_same_intensity)
                    f_lut_per_image_data = f_lut_state.get("lut_per_image_data", lut_per_image_data)

                    f_crop_enabled = f_crop_state.get("crop_enabled", f_crop_state.get("crop_mode", 0) != 0)
                    f_crop_mode = f_crop_state.get("crop_mode", crop_mode)
                    f_is_crop_same = (f_crop_mode == self.CROP_SAME)
                    f_is_crop_manual = (f_crop_mode == self.CROP_MANUAL)
                    f_same_w = f_crop_state.get("crop_same_w", same_w)
                    f_same_h = f_crop_state.get("crop_same_h", same_h)
                    f_anchor_idx = f_crop_state.get("crop_anchor", 0)
                    f_anchor = anchor_map.get(f_anchor_idx, "center")
                    f_crop_data = f_crop_state.get("crop_data", crop_data)

                    child_items = [top_item.child(c) for c in range(top_item.childCount())]

                    def process_folder_image(src_path: Path, c_idx: int) -> Optional[Image.Image]:
                        is_svg = src_path.suffix.lower() == ".svg"
                        if is_svg:
                            img = open_image(src_path, svg_width=w, svg_height=h, svg_scale=scale)
                        else:
                            img = open_image(src_path)
                            if w or h or scale:
                                img = do_resize(img, width=w, height=h, scale=scale)

                        if f_crop_enabled:
                            if f_is_crop_same:
                                img = do_center_crop(img, f_same_w, f_same_h, f_anchor)
                            elif f_is_crop_manual:
                                settings = f_crop_data.get(c_idx)
                                if settings:
                                    cx, cy = settings["x"], settings["y"]
                                    cw, ch = settings["w"], settings["h"]
                                    if cw > 0 and ch > 0:
                                        img = do_crop(img, cx, cy, cw, ch)

                        if f_lut_enabled:
                            if f_lut_mode == self.LUT_SAME and f_lut_same_obj:
                                img = apply_lut(img, f_lut_same_obj, f_lut_same_intensity)
                            elif f_lut_mode == self.LUT_MANUAL:
                                l_data = f_lut_per_image_data.get(c_idx)
                                if l_data and l_data.get("obj"):
                                    img = apply_lut(img, l_data["obj"], l_data.get("intensity", 1.0))
                        return img

                    if folder_exp == "single_image":
                        folder_imgs = []
                        for c_idx, c_item in enumerate(child_items):
                            fpath = c_item.data(0, Qt.UserRole)
                            if not fpath:
                                continue
                            try:
                                img = process_folder_image(Path(fpath), c_idx)
                                if img:
                                    folder_imgs.append(img)
                            except Exception as e:
                                self._log(f"{self.i18n('log_error')}  Layer {Path(fpath).name}: {e}", "err")
                            processed_count += 1
                            self._signals.progress.emit(int(processed_count / total_files * 100))

                        if folder_imgs:
                            try:
                                merged = composite_folder_images(folder_imgs, layout=merge_layout)
                                dst = dest_map.get(top_item, out_path / (folder_name + ext_out))
                                save_image(merged, dst, quality=quality, fmt_override=fmt)
                                self._log(f"{self.i18n('log_success')}  Merged Folder [{folder_name}] -> {dst.name}", "ok")
                                ok += 1
                            except Exception as e:
                                self._log(f"{self.i18n('log_error')}  Merging folder [{folder_name}]: {e}", "err")
                                err += 1
                    else:
                        for c_idx, c_item in enumerate(child_items):
                            fpath = c_item.data(0, Qt.UserRole)
                            if not fpath:
                                continue
                            src_path = Path(fpath)
                            dst = dest_map.get((top_item, c_idx), out_path / folder_name / (src_path.stem + ext_out))
                            try:
                                img = process_folder_image(src_path, c_idx)
                                if img:
                                    save_image(img, dst, quality=quality, fmt_override=fmt)
                                    self._log(f"{self.i18n('log_success')}  {folder_name}/{src_path.name} -> {dst.name}", "ok")
                                    ok += 1
                            except Exception as e:
                                self._log(f"{self.i18n('log_error')}  {src_path.name}: {e}", "err")
                                err += 1
                            processed_count += 1
                            self._signals.progress.emit(int(processed_count / total_files * 100))

            summary = f"{self.i18n('log_completed')} {ok} {self.i18n('log_ok_count')}, {err} {self.i18n('log_err_count')}."
            if skipped:
                summary += f" ({skipped} skipped)"
            self._log(summary, "inf")
            self._signals.finished.emit()

        self._start_progress_dialog(self.i18n("info_processing"))
        threading.Thread(target=task, daemon=True).start()

    # ---- Project management ----

    def _auto_save_temp(self):
        if getattr(self, "_importing_in_progress", False) or self._crop_updating or self._lut_updating:
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
        curr_folder = self._get_folder_node_for_item(self.file_tree.currentItem())
        if curr_folder:
            self._save_folder_state(curr_folder)

        tree_structure = []
        root = self.file_tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            kind = item.data(0, Qt.UserRole + 1)
            if kind == "file":
                p = item.data(0, Qt.UserRole)
                if p:
                    tree_structure.append({"type": "file", "path": p})
            elif kind == "folder":
                f_name = item.data(0, Qt.UserRole + 2) or "Folder"
                f_mode = item.data(0, Qt.UserRole + 3) or "same"
                f_exp = item.data(0, Qt.UserRole + 4) or "separate"
                f_layout = item.data(0, Qt.UserRole + 5) or "vertical"
                f_lut = dict(item.data(0, Qt.UserRole + 6) or {})
                f_crop = dict(item.data(0, Qt.UserRole + 7) or {})

                if "lut_same_obj" in f_lut:
                    del f_lut["lut_same_obj"]

                children = []
                for c in range(item.childCount()):
                    child = item.child(c)
                    cp = child.data(0, Qt.UserRole)
                    if cp:
                        children.append({"type": "file", "path": cp})
                tree_structure.append({
                    "type": "folder",
                    "name": f_name,
                    "mode": f_mode,
                    "export_mode": f_exp,
                    "merge_layout": f_layout,
                    "lut_state": f_lut,
                    "crop_state": f_crop,
                    "children": children
                })

        return {
            "version": "1.4",
            "files": self._get_all_file_paths(),
            "tree_structure": tree_structure,
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
                "custom_filename": self.output_filename_edit.text(),
                "output_dir":      self.output_dir.text(),
                "convert_width":   self.conv_width.value(),
                "convert_height":  self.conv_height.value(),
                "crop_enabled":    self.crop_enable_check.isChecked(),
                "lut_enabled":     self.lut_enable_check.isChecked(),
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

        tree_struct = state.get("tree_structure")
        missing_files = []

        if tree_struct:
            for node in tree_struct:
                if node.get("type") == "file":
                    p = node.get("path")
                    if p and Path(p).exists():
                        item = self._create_file_tree_item(p)
                        self.file_tree.addTopLevelItem(item)
                        self._files.append(p)
                    elif p:
                        missing_files.append(p)
                elif node.get("type") == "folder":
                    f_item = QTreeWidgetItem()
                    f_item.setData(0, Qt.UserRole + 1, "folder")
                    f_item.setData(0, Qt.UserRole + 2, node.get("name", "Folder"))
                    f_item.setData(0, Qt.UserRole + 3, node.get("mode", "same"))
                    f_item.setData(0, Qt.UserRole + 4, node.get("export_mode", "separate"))
                    f_item.setData(0, Qt.UserRole + 5, node.get("merge_layout", "vertical"))

                    f_lut = node.get("lut_state", {})
                    if f_lut.get("lut_same_file") and Path(f_lut["lut_same_file"]).exists():
                        try: f_lut["lut_same_obj"] = load_lut_file(f_lut["lut_same_file"])
                        except Exception: pass
                    elif f_lut.get("lut_same_preset") and f_lut["lut_same_preset"] in PRESET_LUT_SETTINGS:
                        f_lut["lut_same_obj"] = get_preset_lut(f_lut["lut_same_preset"])
                    elif f_lut.get("lut_same_settings"):
                        s = dict(f_lut["lut_same_settings"])
                        f_lut["lut_same_obj"] = generate_lut_from_settings(**s)

                    f_item.setData(0, Qt.UserRole + 6, f_lut)
                    f_item.setData(0, Qt.UserRole + 7, node.get("crop_state", {}))

                    for child in node.get("children", []):
                        cp = child.get("path")
                        if cp and Path(cp).exists():
                            c_item = self._create_file_tree_item(cp)
                            f_item.addChild(c_item)
                            self._files.append(cp)
                        elif cp:
                            missing_files.append(cp)
                    self._update_folder_item_display(f_item)
                    self.file_tree.addTopLevelItem(f_item)
                    f_item.setExpanded(True)
        else:
            for f in state.get("files", []):
                if Path(f).exists():
                    item = self._create_file_tree_item(f)
                    self.file_tree.addTopLevelItem(item)
                    self._files.append(f)
                else:
                    missing_files.append(f)

        self._update_count()
        self._auto_load_preview()
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

        settings = state.get("settings", {})
        if "convert_format"  in settings: self.conv_format.setCurrentText(settings["convert_format"])
        if "convert_quality" in settings: self.conv_quality_slider.setValue(settings["convert_quality"])

        if "custom_filename" in settings:
            self.output_filename_edit.setText(settings["custom_filename"])

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

        crop_enabled = settings.get("crop_enabled", settings.get("crop_mode", 0) != 0)
        self.crop_enable_check.setChecked(crop_enabled)

        lut_enabled = settings.get("lut_enabled", settings.get("lut_mode", 0) != 0)
        self.lut_enable_check.setChecked(lut_enabled)

        if "crop_same_w" in settings: self.crop_same_w.setValue(settings["crop_same_w"])
        if "crop_same_h" in settings: self.crop_same_h.setValue(settings["crop_same_h"])
        if "crop_anchor" in settings: self.crop_anchor.setCurrentIndex(settings["crop_anchor"])
        if "crop_aspect" in settings: self.crop_aspect.setCurrentIndex(settings["crop_aspect"])

        self._crop_updating = False
        self._lut_updating = False
        self._update_crop_visibility()
        self._update_lut_visibility()

        if missing_files:
            QMessageBox.warning(
                self,
                self.i18n("project_missing_images_title"),
                self.i18n("project_missing_images", paths="\n".join(missing_files))
            )
            for f in missing_files:
                self._log(f"{self.i18n('log_error')} File not found: {f}", "err")

    def _save_project(self):
        if self._crop_mode == self.CROP_MANUAL:
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
