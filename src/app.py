"""
Main application window for Image Resolver (PySide6 / Qt).

Two tabs:
  1. Convert Images — unified single + batch workflow
  2. Crop Images — batch same-size or manual one-by-one crop
"""

import traceback
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
    QSplitter, QScrollArea, QDialog,
)
from PySide6.QtCore import Qt, Signal, QObject, QRectF, QPointF, QTimer
from PySide6.QtGui import (
    QPixmap, QImage, QPen, QBrush, QColor, QIcon, QPainter, QCursor,
)
from PIL import Image, ImageQt

from src.constants import OUTPUT_FORMATS, EXT_MAP, INPUT_EXTS
from src.image_processor import open_image, save_image, do_resize, do_crop, do_center_crop
from src.ui_components import int_or_none, float_or_none, file_filter_string, CollapsibleSection, Separator, InteractiveCropView
from src.localization import get_i18n, set_language
from src.theme import get_stylesheet, GOLD, SUCCESS, ERROR, INFO, TEXT_DIM, DARK_BG, CARD_BG, BORDER

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
        self.i18n = get_i18n()
        self.setWindowTitle(self.i18n("title"))
        self.setMinimumSize(720, 620)
        self.resize(760, 660)
        self._set_icon()

        # Apply theme stylesheet
        self.setStyleSheet(get_stylesheet())

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # Tab widget
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs, stretch=1)

        # Build tabs
        self._build_convert_tab()
        self._build_crop_tab()

        # Log area
        self._build_log_area(root_layout)

        # Progress bar
        self._build_progress_bar(root_layout)

        # Worker signals
        self._signals = _WorkerSignals()
        self._signals.log.connect(self._append_log)
        self._signals.progress.connect(self._set_progress)
        self._signals.finished.connect(self._on_finished)

        # Menu bar for language
        self._build_menu()

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

    def _build_menu(self):
        """Build menu bar with language selector and about."""
        menu = self.menuBar()
        lang_menu = menu.addMenu("Language")
        lang_menu.addAction("English", lambda: self._change_language("en"))
        lang_menu.addAction("Bahasa Indonesia", lambda: self._change_language("id"))

        about_menu = menu.addMenu("About")
        about_menu.addAction("About QIF", self._show_about)

    def _change_language(self, lang: str):
        """Change language and rebuild UI."""
        set_language(lang)
        self.i18n = get_i18n()
        # Update tab titles
        self.tabs.setTabText(0, f"  {self.i18n('tab_convert')}  ")
        self.tabs.setTabText(1, f"  {self.i18n('tab_crop')}  ")
        self.setWindowTitle(self.i18n("title"))
        # Update log header
        self._log_label.setText(self.i18n("log"))

    # ── About dialog ─────────────────────────────────────────

    def _show_about(self):
        """Show the About dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle("About QIF")
        dlg.setFixedSize(420, 340)
        dlg.setStyleSheet(f"""
            QDialog {{
                background-color: {CARD_BG};
            }}
            QLabel {{
                color: #CCCCCC;
            }}
            QLabel#aboutTitle {{
                color: {GOLD};
                font-size: 18pt;
                font-weight: bold;
            }}
            QLabel#aboutSubtitle {{
                color: #AAAAAA;
                font-size: 10pt;
            }}
            QLabel#aboutLink {{
                color: {GOLD};
                font-size: 10pt;
            }}
            QPushButton {{
                background-color: {GOLD};
                color: #1A1A1A;
                border: none;
                border-radius: 6px;
                padding: 8px 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #D4B65A;
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

        title = QLabel("QIF — Quick Image Formatting")
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

        link = QLabel(
            '<a style="color: #C9A84C;" '
            'href="https://github.com/PWira/Image-Resolver">'
            'github.com/PWira/Image-Resolver</a>'
        )
        link.setObjectName("aboutLink")
        link.setAlignment(Qt.AlignCenter)
        link.setOpenExternalLinks(True)
        layout.addWidget(link)

        license_lbl = QLabel("Licensed under the MIT License")
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
        color_map = {"ok": SUCCESS, "err": ERROR, "inf": INFO}
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

    # ══════════════════════════════════════════════════════════
    #  TAB 1: CONVERT IMAGES (Merged single + batch)
    # ══════════════════════════════════════════════════════════

    def _build_convert_tab(self):
        """Build the unified Convert Images tab."""
        tab = QWidget()
        self.tabs.addTab(tab, f"  {self.i18n('tab_convert')}  ")
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # ── Top pane: File selection list ──────────────────
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        # ── File list section ────────────────────────────────
        file_header = QHBoxLayout()
        lbl = QLabel(self.i18n("pick_images"))
        lbl.setObjectName("headerLabel")
        file_header.addWidget(lbl)
        file_header.addStretch()

        btn_add_files = QPushButton(self.i18n("add_files"))
        btn_add_files.clicked.connect(self._conv_add_files)
        btn_add_folder = QPushButton(self.i18n("add_folder"))
        btn_add_folder.clicked.connect(self._conv_add_folder)
        btn_remove = QPushButton(self.i18n("remove_selected"))
        btn_remove.clicked.connect(self._conv_remove_selected)
        btn_clear = QPushButton(self.i18n("clear_all"))
        btn_clear.clicked.connect(self._conv_clear_all)

        file_header.addWidget(btn_add_files)
        file_header.addWidget(btn_add_folder)
        file_header.addWidget(btn_remove)
        file_header.addWidget(btn_clear)
        top_layout.addLayout(file_header)

        # File list widget
        self.conv_file_list = QListWidget()
        self.conv_file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.conv_file_list.setMinimumHeight(120)
        top_layout.addWidget(self.conv_file_list)

        # File count label
        self.conv_count_label = QLabel(self.i18n("no_files"))
        self.conv_count_label.setObjectName("dimLabel")
        top_layout.addWidget(self.conv_count_label)

        splitter.addWidget(top_container)

        # ── Bottom pane: Settings inside scroll area ─────
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setMinimumHeight(100)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(12)

        bottom_layout.addWidget(Separator())

        # ── Output settings ──────────────────────────────────
        output_grid = QGridLayout()
        output_grid.setHorizontalSpacing(12)
        output_grid.setVerticalSpacing(8)

        # Save As (format)
        output_grid.addWidget(QLabel(self.i18n("save_as")), 0, 0)
        self.conv_format = QComboBox()
        self.conv_format.addItems(OUTPUT_FORMATS)
        self.conv_format.setCurrentText("PNG")
        output_grid.addWidget(self.conv_format, 0, 1)

        # Picture Quality
        output_grid.addWidget(QLabel(self.i18n("picture_quality")), 0, 2)
        self.conv_quality_slider = QSlider(Qt.Horizontal)
        self.conv_quality_slider.setRange(1, 100)
        self.conv_quality_slider.setValue(85)
        self.conv_quality_slider.setFixedWidth(140)
        self.conv_quality_label = QLabel("85")
        self.conv_quality_label.setFixedWidth(24)
        self.conv_quality_slider.valueChanged.connect(
            lambda v: self.conv_quality_label.setText(str(v))
        )
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.conv_quality_slider)
        quality_row.addWidget(self.conv_quality_label)
        output_grid.addLayout(quality_row, 0, 3)

        # Save To (output directory)
        output_grid.addWidget(QLabel(self.i18n("save_to")), 1, 0)
        self.conv_output_dir = QLineEdit()
        self.conv_output_dir.setPlaceholderText(self.i18n("browse"))
        output_grid.addWidget(self.conv_output_dir, 1, 1, 1, 2)
        btn_browse_out = QPushButton(self.i18n("browse"))
        btn_browse_out.clicked.connect(self._conv_browse_output)
        output_grid.addWidget(btn_browse_out, 1, 3)

        bottom_layout.addLayout(output_grid)

        # ── Optional resize (collapsible) ────────────────────
        self.conv_resize_section = CollapsibleSection(self.i18n("change_size"))
        resize_layout = self.conv_resize_section.content_layout()

        resize_grid = QGridLayout()
        resize_grid.setHorizontalSpacing(12)
        resize_grid.setVerticalSpacing(8)

        resize_grid.addWidget(QLabel(self.i18n("width")), 0, 0)
        self.conv_width = QSpinBox()
        self.conv_width.setRange(0, 99999)
        self.conv_width.setSpecialValueText("—")
        self.conv_width.setSuffix(" px")
        resize_grid.addWidget(self.conv_width, 0, 1)

        resize_grid.addWidget(QLabel(self.i18n("height")), 0, 2)
        self.conv_height = QSpinBox()
        self.conv_height.setRange(0, 99999)
        self.conv_height.setSpecialValueText("—")
        self.conv_height.setSuffix(" px")
        resize_grid.addWidget(self.conv_height, 0, 3)

        resize_grid.addWidget(QLabel(self.i18n("resize_percent")), 1, 0)
        self.conv_scale = QSpinBox()
        self.conv_scale.setRange(0, 10000)
        self.conv_scale.setSpecialValueText("—")
        self.conv_scale.setSuffix(" %")
        resize_grid.addWidget(self.conv_scale, 1, 1)

        self.conv_subfolder_check = QCheckBox(self.i18n("include_subfolders"))
        resize_grid.addWidget(self.conv_subfolder_check, 1, 2, 1, 2)

        resize_layout.addLayout(resize_grid)
        bottom_layout.addWidget(self.conv_resize_section)

        # ── Convert button ───────────────────────────────────
        btn_convert = QPushButton(f"★  {self.i18n('convert_now')}")
        btn_convert.setObjectName("primaryBtn")
        btn_convert.clicked.connect(self._run_convert)
        bottom_layout.addWidget(btn_convert, alignment=Qt.AlignCenter)

        scroll_area.setWidget(bottom_widget)
        splitter.addWidget(scroll_area)
        splitter.setSizes([200, 300])

    # ── Convert tab: file management ─────────────────────────

    def _conv_add_files(self):
        """Open file dialog to add individual images."""
        files, _ = QFileDialog.getOpenFileNames(
            self, self.i18n("add_files"), "",
            file_filter_string(self.i18n),
        )
        for f in files:
            self._conv_add_path(f)
        self._conv_update_count()

    def _conv_add_folder(self):
        """Open folder dialog and add all images from it."""
        folder = QFileDialog.getExistingDirectory(self, self.i18n("add_folder"))
        if not folder:
            return
        recursive = self.conv_subfolder_check.isChecked()
        pattern = "**/*" if recursive else "*"
        folder_path = Path(folder)
        for f in sorted(folder_path.glob(pattern)):
            if f.is_file() and f.suffix.lower() in INPUT_EXTS:
                self._conv_add_path(str(f))
        self._conv_update_count()

    def _conv_add_path(self, path: str):
        """Add a single file path to the list (no duplicates)."""
        # Check for duplicates
        for i in range(self.conv_file_list.count()):
            if self.conv_file_list.item(i).data(Qt.UserRole) == path:
                return
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
        self.conv_file_list.addItem(item)

    def _conv_remove_selected(self):
        """Remove selected items from the file list."""
        for item in self.conv_file_list.selectedItems():
            self.conv_file_list.takeItem(self.conv_file_list.row(item))
        self._conv_update_count()

    def _conv_clear_all(self):
        """Clear all items from the file list."""
        self.conv_file_list.clear()
        self._conv_update_count()

    def _conv_update_count(self):
        """Update the file count label."""
        count = self.conv_file_list.count()
        if count == 0:
            self.conv_count_label.setText(self.i18n("no_files"))
        else:
            self.conv_count_label.setText(f"{count} {self.i18n('files_in_list')}")

    def _conv_browse_output(self):
        """Browse for output directory."""
        folder = QFileDialog.getExistingDirectory(self, self.i18n("save_to"))
        if folder:
            self.conv_output_dir.setText(folder)

    # ── Convert tab: run conversion ──────────────────────────

    def _run_convert(self):
        """Run the conversion in a background thread."""
        count = self.conv_file_list.count()
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
            files.append(self.conv_file_list.item(i).data(Qt.UserRole))

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

    # ══════════════════════════════════════════════════════════
    #  TAB 2: CROP IMAGES
    # ══════════════════════════════════════════════════════════

    def _build_crop_tab(self):
        """Build the Crop Images tab with two modes."""
        tab = QWidget()
        self.tabs.addTab(tab, f"  {self.i18n('tab_crop')}  ")
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # ── Top pane: File selection list ──────────────────
        top_container = QWidget()
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        file_header = QHBoxLayout()
        lbl = QLabel(self.i18n("pick_images"))
        lbl.setObjectName("headerLabel")
        file_header.addWidget(lbl)
        file_header.addStretch()

        btn_add_files = QPushButton(self.i18n("add_files"))
        btn_add_files.clicked.connect(self._crop_add_files)
        btn_add_folder = QPushButton(self.i18n("add_folder"))
        btn_add_folder.clicked.connect(self._crop_add_folder)
        btn_clear = QPushButton(self.i18n("clear_all"))
        btn_clear.clicked.connect(self._crop_clear_all)

        file_header.addWidget(btn_add_files)
        file_header.addWidget(btn_add_folder)
        file_header.addWidget(btn_clear)
        top_layout.addLayout(file_header)

        self.crop_file_list = QListWidget()
        self.crop_file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.crop_file_list.setMinimumHeight(80)
        top_layout.addWidget(self.crop_file_list)

        self.crop_count_label = QLabel(self.i18n("no_files"))
        self.crop_count_label.setObjectName("dimLabel")
        top_layout.addWidget(self.crop_count_label)

        splitter.addWidget(top_container)

        # ── Bottom pane: Crop settings inside scroll area ────
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setMinimumHeight(100)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(12)

        bottom_layout.addWidget(Separator())

        # ── Mode selection ───────────────────────────────────
        mode_label = QLabel(self.i18n("crop_mode"))
        mode_label.setObjectName("headerLabel")
        bottom_layout.addWidget(mode_label)

        self.crop_mode_group = QButtonGroup(self)
        self.crop_radio_same = QRadioButton(self.i18n("crop_same_size"))
        self.crop_radio_manual = QRadioButton(self.i18n("crop_one_by_one"))
        self.crop_radio_same.setChecked(True)
        self.crop_mode_group.addButton(self.crop_radio_same, 0)
        self.crop_mode_group.addButton(self.crop_radio_manual, 1)
        self.crop_mode_group.idToggled.connect(self._crop_mode_changed)

        mode_row = QHBoxLayout()
        mode_row.addWidget(self.crop_radio_same)
        mode_row.addWidget(self.crop_radio_manual)
        mode_row.addStretch()
        bottom_layout.addLayout(mode_row)

        # ── Same-size panel ──────────────────────────────────
        self.crop_same_panel = QWidget()
        same_outer = QVBoxLayout(self.crop_same_panel)
        same_outer.setContentsMargins(0, 0, 0, 0)
        same_outer.setSpacing(8)

        same_grid = QGridLayout()
        same_grid.setHorizontalSpacing(12)
        same_grid.setVerticalSpacing(8)

        same_grid.addWidget(QLabel(self.i18n("crop_width")), 0, 0)
        self.crop_same_w = QSpinBox()
        self.crop_same_w.setRange(1, 99999)
        self.crop_same_w.setValue(800)
        self.crop_same_w.setSuffix(" px")
        same_grid.addWidget(self.crop_same_w, 0, 1)

        same_grid.addWidget(QLabel(self.i18n("crop_height")), 0, 2)
        self.crop_same_h = QSpinBox()
        self.crop_same_h.setRange(1, 99999)
        self.crop_same_h.setValue(600)
        self.crop_same_h.setSuffix(" px")
        same_grid.addWidget(self.crop_same_h, 0, 3)

        same_grid.addWidget(QLabel(self.i18n("crop_from")), 1, 0)
        self.crop_anchor = QComboBox()
        self.crop_anchor.addItems([self.i18n("crop_center"), self.i18n("crop_top_left")])
        same_grid.addWidget(self.crop_anchor, 1, 1)

        same_outer.addLayout(same_grid)

        # Interactive preview for same-size mode
        self.crop_same_view = InteractiveCropView()
        self.crop_same_view.setMinimumSize(380, 200)
        self.crop_same_view.setMaximumHeight(220)
        same_outer.addWidget(self.crop_same_view)

        bottom_layout.addWidget(self.crop_same_panel)

        # ── One-by-one panel ─────────────────────────────────
        self.crop_manual_panel = QWidget()
        manual_layout = QVBoxLayout(self.crop_manual_panel)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(8)

        # Canvas + controls side by side
        canvas_row = QHBoxLayout()

        # Interactive graphics view for image preview
        self.crop_manual_view = InteractiveCropView()
        self.crop_manual_view.setMinimumSize(380, 240)
        self.crop_manual_view.setMaximumHeight(260)
        canvas_row.addWidget(self.crop_manual_view, stretch=1)

        # Side controls for crop coordinates
        side = QVBoxLayout()
        side.setSpacing(6)

        crop_grid = QGridLayout()
        crop_grid.setHorizontalSpacing(8)
        crop_grid.setVerticalSpacing(6)

        crop_grid.addWidget(QLabel(self.i18n("crop_x")), 0, 0)
        self.crop_x = QSpinBox()
        self.crop_x.setRange(0, 99999)
        crop_grid.addWidget(self.crop_x, 0, 1)

        crop_grid.addWidget(QLabel(self.i18n("crop_y")), 1, 0)
        self.crop_y = QSpinBox()
        self.crop_y.setRange(0, 99999)
        crop_grid.addWidget(self.crop_y, 1, 1)

        crop_grid.addWidget(QLabel(self.i18n("crop_width")), 2, 0)
        self.crop_w = QSpinBox()
        self.crop_w.setRange(1, 99999)
        self.crop_w.setValue(800)
        crop_grid.addWidget(self.crop_w, 2, 1)

        crop_grid.addWidget(QLabel(self.i18n("crop_height")), 3, 0)
        self.crop_h = QSpinBox()
        self.crop_h.setRange(1, 99999)
        self.crop_h.setValue(600)
        crop_grid.addWidget(self.crop_h, 3, 1)

        crop_grid.addWidget(QLabel(self.i18n("crop_shape")), 4, 0)
        self.crop_aspect = QComboBox()
        self.crop_aspect.addItems([
            self.i18n("crop_free"), "1:1", "4:3", "3:2", "16:9", "9:16", "3:4", "2:3",
        ])
        crop_grid.addWidget(self.crop_aspect, 4, 1)

        side.addLayout(crop_grid)

        self.crop_skip_check = QCheckBox(self.i18n("crop_skip"))
        side.addWidget(self.crop_skip_check)

        hint = QLabel(self.i18n("crop_hint"))
        hint.setObjectName("dimLabel")
        hint.setWordWrap(True)
        hint.setMaximumWidth(160)
        side.addWidget(hint)
        side.addStretch()

        canvas_row.addLayout(side)
        manual_layout.addLayout(canvas_row)

        # Navigation bar
        nav_row = QHBoxLayout()
        self.crop_prev_btn = QPushButton(f"◀  {self.i18n('crop_previous')}")
        self.crop_prev_btn.clicked.connect(self._crop_go_prev)
        self.crop_nav_label = QLabel("")
        self.crop_nav_label.setAlignment(Qt.AlignCenter)
        self.crop_next_btn = QPushButton(f"{self.i18n('crop_next')}  ▶")
        self.crop_next_btn.clicked.connect(self._crop_go_next)
        nav_row.addWidget(self.crop_prev_btn)
        nav_row.addStretch()
        nav_row.addWidget(self.crop_nav_label)
        nav_row.addStretch()
        nav_row.addWidget(self.crop_next_btn)
        manual_layout.addLayout(nav_row)

        self.crop_manual_panel.setVisible(False)  # hidden by default
        bottom_layout.addWidget(self.crop_manual_panel)

        bottom_layout.addWidget(Separator())

        # ── Output settings ──────────────────────────────────
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel(self.i18n("save_as")))
        self.crop_format = QComboBox()
        self.crop_format.addItems(OUTPUT_FORMATS)
        self.crop_format.setCurrentText("PNG")
        out_row.addWidget(self.crop_format)

        out_row.addWidget(QLabel(self.i18n("save_to")))
        self.crop_output_dir = QLineEdit()
        self.crop_output_dir.setPlaceholderText(self.i18n("browse"))
        out_row.addWidget(self.crop_output_dir, stretch=1)
        btn_browse = QPushButton(self.i18n("browse"))
        btn_browse.clicked.connect(self._crop_browse_output)
        out_row.addWidget(btn_browse)

        bottom_layout.addLayout(out_row)

        # ── Crop button ──────────────────────────────────────
        btn_crop = QPushButton(f"★  {self.i18n('crop_save_all')}")
        btn_crop.setObjectName("primaryBtn")
        btn_crop.clicked.connect(self._run_crop)
        bottom_layout.addWidget(btn_crop, alignment=Qt.AlignCenter)

        scroll_area.setWidget(bottom_widget)
        splitter.addWidget(scroll_area)
        splitter.setSizes([200, 400])

        # ── Internal crop state ──────────────────────────────
        self._crop_files: List[str] = []
        self._crop_index = 0
        self._crop_data: Dict[int, dict] = {}  # per-image crop settings
        self._crop_updating = False  # prevent spinbox ↔ view signal loops

        # ── Connect interactive crop signals ─────────────────
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

    # ── Crop tab: file management ────────────────────────────

    def _crop_add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, self.i18n("add_files"), "",
            file_filter_string(self.i18n),
        )
        for f in files:
            self._crop_add_path(f)
        self._crop_update_count()
        self._crop_auto_load_preview()

    def _crop_add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self.i18n("add_folder"))
        if not folder:
            return
        for f in sorted(Path(folder).glob("*")):
            if f.is_file() and f.suffix.lower() in INPUT_EXTS:
                self._crop_add_path(str(f))
        self._crop_update_count()
        self._crop_auto_load_preview()

    def _crop_add_path(self, path: str):
        if path not in self._crop_files:
            self._crop_files.append(path)
            p = Path(path)
            item = QListWidgetItem(p.name)
            item.setData(Qt.UserRole, path)
            self.crop_file_list.addItem(item)

    def _crop_clear_all(self):
        self.crop_file_list.clear()
        self._crop_files.clear()
        self._crop_data.clear()
        self._crop_index = 0
        self.crop_same_view.clear_image()
        self.crop_manual_view.clear_image()
        self._crop_update_count()

    def _crop_update_count(self):
        count = len(self._crop_files)
        if count == 0:
            self.crop_count_label.setText(self.i18n("no_files"))
        else:
            self.crop_count_label.setText(f"{count} {self.i18n('files_in_list')}")

    def _crop_browse_output(self):
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
        if self._crop_files:
            if is_manual:
                self._crop_load_image(self._crop_index)
            else:
                self._crop_same_load_preview(self._crop_files[0])

    # ── Crop tab: one-by-one navigation ──────────────────────

    def _crop_go_prev(self):
        if self._crop_files and self._crop_index > 0:
            self._crop_save_current_settings()
            self._crop_index -= 1
            self._crop_load_image(self._crop_index)

    def _crop_go_next(self):
        if self._crop_files and self._crop_index < len(self._crop_files) - 1:
            self._crop_save_current_settings()
            self._crop_index += 1
            self._crop_load_image(self._crop_index)

    def _crop_save_current_settings(self):
        """Save the current crop fields into the data dict for this image."""
        self._crop_data[self._crop_index] = {
            "x": self.crop_x.value(),
            "y": self.crop_y.value(),
            "w": self.crop_w.value(),
            "h": self.crop_h.value(),
            "skip": self.crop_skip_check.isChecked(),
        }

    def _crop_load_image(self, index: int):
        """Load image at the given index into the one-by-one interactive view."""
        if index < 0 or index >= len(self._crop_files):
            return
        self._crop_index = index

        # Update navigation label
        total = len(self._crop_files)
        self.crop_nav_label.setText(
            self.i18n("crop_image_n_of", current=index + 1, total=total)
        )
        self.crop_prev_btn.setEnabled(index > 0)
        self.crop_next_btn.setEnabled(index < total - 1)

        # Load image into the interactive view
        path = self._crop_files[index]
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

    def _crop_auto_load_preview(self):
        """Load first image into whichever crop view is active."""
        if not self._crop_files:
            return
        if self.crop_radio_manual.isChecked():
            self._crop_load_image(self._crop_index)
        else:
            self._crop_same_load_preview(self._crop_files[0])

    def _crop_same_load_preview(self, path: str):
        """Load an image into the same-size mode preview."""
        try:
            pil_img = open_image(Path(path))
            self.crop_same_view.load_image(pil_img)
            # Set crop rect based on current w/h and anchor
            self._crop_same_update_view()
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

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

    # ── Crop tab: run crop ───────────────────────────────────

    def _run_crop(self):
        """Run crop in a background thread."""
        if not self._crop_files:
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
        files = list(self._crop_files)

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
