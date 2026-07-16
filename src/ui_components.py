"""
Reusable Qt UI components for Quick Image Formatting.
"""

from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy,
    QGraphicsView, QGraphicsScene,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, Property, QRectF, QPointF, QSizeF
from PySide6.QtGui import QIcon, QPixmap, QImage, QPen, QBrush, QColor, QPainter
from PIL import Image

from src.constants import INPUT_EXTS
from src.theme import GOLD


def int_or_none(val: str) -> Optional[int]:
    """
    Parse string to integer or return None if invalid/not positive.

    Args:
        val: String to parse

    Returns:
        Positive integer or None
    """
    try:
        v = int(val.strip())
        return v if v > 0 else None
    except (ValueError, AttributeError):
        return None


def float_or_none(val: str) -> Optional[float]:
    """
    Parse string to float or return None if invalid/not positive.

    Args:
        val: String to parse

    Returns:
        Positive float or None
    """
    try:
        v = float(val.strip())
        return v if v > 0 else None
    except (ValueError, AttributeError):
        return None


def file_filter_string(i18n=None) -> str:
    """
    Return file dialog filter string for supported input images.

    Args:
        i18n: Optional localization function

    Returns:
        Filter string for QFileDialog
    """
    lbl_images = i18n("all_images") if i18n else "All images"
    lbl_files = i18n("all_files") if i18n else "All files"
    exts = " ".join(f"*{e}" for e in sorted(INPUT_EXTS))
    return f"{lbl_images} ({exts});;{lbl_files} (*.*)"


class CollapsibleSection(QWidget):
    """
    A collapsible panel that expands/collapses its content with a toggle button.
    Used for the optional 'Change Size' section.
    """

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self._is_expanded = False

        # Toggle button
        self._toggle_btn = QPushButton(f"▶  {title}")
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(False)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                text-align: left;
                border: none;
                padding: 8px 12px;
                font-weight: bold;
                background: transparent;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.05);
                border-radius: 6px;
            }
        """)
        self._toggle_btn.clicked.connect(self._toggle)
        self._title = title

        # Content area
        self._content = QWidget()
        self._content.setMaximumHeight(0)
        self._content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 8, 12, 8)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toggle_btn)
        layout.addWidget(self._content)

    def content_layout(self) -> QVBoxLayout:
        """Get the layout to add child widgets into."""
        return self._content_layout

    def _toggle(self):
        self._is_expanded = self._toggle_btn.isChecked()
        if self._is_expanded:
            self._toggle_btn.setText(f"▼  {self._title}")
            # Expand: measure the content height and animate
            self._content.setMaximumHeight(0)
            self._content.adjustSize()
            target = self._content_layout.sizeHint().height() + 20
            anim = QPropertyAnimation(self._content, b"maximumHeight", self)
            anim.setDuration(200)
            anim.setStartValue(0)
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            anim.start()
            self._anim = anim  # prevent garbage collection
        else:
            self._toggle_btn.setText(f"▶  {self._title}")
            anim = QPropertyAnimation(self._content, b"maximumHeight", self)
            anim.setDuration(200)
            anim.setStartValue(self._content.height())
            anim.setEndValue(0)
            anim.setEasingCurve(QEasingCurve.InCubic)
            anim.start()
            self._anim = anim

    def set_expanded(self, expanded: bool):
        """Programmatically expand/collapse."""
        if expanded != self._is_expanded:
            self._toggle_btn.setChecked(expanded)
            self._toggle()


class Separator(QFrame):
    """A thin horizontal line separator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Plain)
        self.setFixedHeight(1)


class InteractiveCropView(QGraphicsView):
    """
    A QGraphicsView that displays an image and provides interactive
    crop-rectangle drawing, moving, and resizing via mouse.

    Signals:
        cropChanged(x, y, w, h): emitted with image-pixel coordinates
                                  whenever the crop region changes.
    """

    cropChanged = Signal(int, int, int, int)

    # Handle indices (1-based): TL=1 T=2 TR=3 L=4 R=5 BL=6 B=7 BR=8
    _HR = 8          # handle hit-test radius (px)
    _HD = 4          # handle visual half-size (px)
    _MIN = 4         # minimum crop rect dimension (scene px)

    _HANDLE_CURSORS = {
        1: Qt.SizeFDiagCursor, 2: Qt.SizeVerCursor, 3: Qt.SizeBDiagCursor,
        4: Qt.SizeHorCursor,   5: Qt.SizeHorCursor,
        6: Qt.SizeBDiagCursor, 7: Qt.SizeVerCursor, 8: Qt.SizeFDiagCursor,
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setDragMode(QGraphicsView.NoDrag)

        # Image
        self._pm_item = None
        self._scale = 1.0
        self._img_sz = (0, 0)
        self._bounds = QRectF()

        # Crop rect (scene coords)
        self._crop = QRectF()

        # Overlay GFX items (rebuilt each redraw)
        self._gfx_dim = []
        self._gfx_border = None
        self._gfx_handles = []

        # Mouse state: 0=idle 1=draw 2=move 3=resize
        self._st = 0
        self._hid = 0           # active handle id (1-8)
        self._m0 = QPointF()    # drag origin
        self._r0 = QRectF()    # rect at drag start

        # Constraints
        self._aspect = 0.0
        self._can_move = True

        # Prevent signal loops
        self._locked = False

    # ── public API ────────────────────────────────────────

    def load_image(self, pil_img):
        """Display *pil_img* fitted to the viewport."""
        self._img_sz = pil_img.size
        iw, ih = pil_img.size

        rgba = pil_img.convert("RGBA") if pil_img.mode != "RGBA" else pil_img
        raw = rgba.tobytes("raw", "RGBA")
        qimg = QImage(raw, iw, ih, 4 * iw, QImage.Format_RGBA8888)
        full = QPixmap.fromImage(qimg)

        vw = self.viewport().width() or 380
        vh = self.viewport().height() or 240
        self._scale = min(vw / iw, vh / ih, 1.0)
        pm = full.scaled(
            int(iw * self._scale), int(ih * self._scale),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )

        self._scene.clear()
        self._pm_item = None
        self._gfx_border = None
        self._gfx_dim.clear()
        self._gfx_handles.clear()

        self._pm_item = self._scene.addPixmap(pm)
        self._bounds = QRectF(pm.rect())
        self._scene.setSceneRect(self._bounds)

        self._crop = QRectF(self._bounds)
        self._redraw()

    def clear_image(self):
        """Remove the loaded image and all overlays."""
        self._scene.clear()
        self._pm_item = None
        self._gfx_border = None
        self._gfx_dim.clear()
        self._gfx_handles.clear()
        self._crop = QRectF()
        self._bounds = QRectF()
        self._img_sz = (0, 0)

    def set_crop_rect(self, x, y, w, h):
        """Set crop rectangle from image-pixel coordinates (external sync)."""
        if self._locked or self._scale <= 0:
            return
        self._locked = True
        s = self._scale
        self._crop = QRectF(x * s, y * s, w * s, h * s)
        self._clamp()
        self._redraw()
        self._locked = False

    def set_aspect_ratio(self, ratio):
        """Set aspect-ratio constraint (width/height). 0 = free."""
        self._aspect = ratio

    def set_allow_move(self, allow):
        """Enable/disable moving the crop rect (set False for same-size mode)."""
        self._can_move = allow

    def image_size(self):
        """Return the original (width, height) of the loaded image."""
        return self._img_sz

    # ── coordinate helpers ────────────────────────────────

    def _to_img(self):
        """Convert current scene-crop to image-pixel coords."""
        s = self._scale
        if s <= 0:
            return 0, 0, 0, 0
        iw, ih = self._img_sz
        x = max(0, round(self._crop.x() / s))
        y = max(0, round(self._crop.y() / s))
        w = max(1, min(round(self._crop.width() / s), iw - x))
        h = max(1, min(round(self._crop.height() / s), ih - y))
        return x, y, w, h

    def _emit(self):
        if self._locked:
            return
        self._locked = True
        self.cropChanged.emit(*self._to_img())
        self._locked = False

    def _clamp(self):
        b, r = self._bounds, self._crop
        if r.width() < self._MIN:
            r.setWidth(self._MIN)
        if r.height() < self._MIN:
            r.setHeight(self._MIN)
        if r.left() < b.left():
            r.moveLeft(b.left())
        if r.top() < b.top():
            r.moveTop(b.top())
        if r.right() > b.right():
            r.moveRight(b.right())
        if r.bottom() > b.bottom():
            r.moveBottom(b.bottom())
        self._crop = r

    # ── overlay drawing ──────────────────────────────────

    def _redraw(self):
        for it in self._gfx_dim + self._gfx_handles:
            try:
                self._scene.removeItem(it)
            except RuntimeError:
                pass
        if self._gfx_border:
            try:
                self._scene.removeItem(self._gfx_border)
            except RuntimeError:
                pass
        self._gfx_dim.clear()
        self._gfx_handles.clear()
        self._gfx_border = None

        if not self._pm_item or self._crop.isNull():
            return

        cr, sb = self._crop, self._bounds
        dim = QBrush(QColor(0, 0, 0, 100))
        nop = QPen(Qt.NoPen)

        def _dim(rx, ry, rw, rh):
            if rw > 0 and rh > 0:
                self._gfx_dim.append(
                    self._scene.addRect(QRectF(rx, ry, rw, rh), nop, dim))

        _dim(sb.left(), sb.top(), sb.width(), cr.top() - sb.top())
        _dim(sb.left(), cr.bottom(), sb.width(), sb.bottom() - cr.bottom())
        _dim(sb.left(), cr.top(), cr.left() - sb.left(), cr.height())
        _dim(cr.right(), cr.top(), sb.right() - cr.right(), cr.height())

        self._gfx_border = self._scene.addRect(
            cr, QPen(QColor(GOLD), 2, Qt.DashLine))

        hs = self._HD
        hp, hb = QPen(QColor("#000000"), 1), QBrush(QColor(GOLD))
        for pt in self._hpts():
            self._gfx_handles.append(self._scene.addRect(
                QRectF(pt.x() - hs, pt.y() - hs, hs * 2, hs * 2), hp, hb))

    def _hpts(self):
        """Handle positions: TL T TR L R BL B BR."""
        c = self._crop
        mx, my = c.center().x(), c.center().y()
        return [
            c.topLeft(), QPointF(mx, c.top()), c.topRight(),
            QPointF(c.left(), my), QPointF(c.right(), my),
            c.bottomLeft(), QPointF(mx, c.bottom()), c.bottomRight(),
        ]

    def _hit(self, pos):
        """Return handle id (1-8) at *pos*, or 0."""
        r = self._HR
        for i, pt in enumerate(self._hpts(), 1):
            if abs(pos.x() - pt.x()) <= r and abs(pos.y() - pt.y()) <= r:
                return i
        return 0

    # ── mouse events ─────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self._pm_item:
            return super().mousePressEvent(event)
        pos = self.mapToScene(event.pos())
        if not self._bounds.contains(pos):
            return

        h = self._hit(pos)
        if h:
            self._st, self._hid = 3, h
        elif self._crop.contains(pos) and self._can_move:
            self._st = 2
        else:
            self._st = 1
            self._crop = QRectF(pos, QSizeF(0, 0))

        self._m0 = pos
        self._r0 = QRectF(self._crop)
        event.accept()

    def mouseMoveEvent(self, event):
        pos = self.mapToScene(event.pos())
        if self._st == 0:
            if not self._pm_item:
                return
            h = self._hit(pos)
            if h:
                self.setCursor(self._HANDLE_CURSORS.get(h, Qt.ArrowCursor))
            elif self._crop.contains(pos) and self._can_move:
                self.setCursor(Qt.SizeAllCursor)
            elif self._bounds.contains(pos):
                self.setCursor(Qt.CrossCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return

        pos = QPointF(
            max(self._bounds.left(), min(pos.x(), self._bounds.right())),
            max(self._bounds.top(), min(pos.y(), self._bounds.bottom())),
        )

        if self._st == 1:
            self._do_draw(pos)
        elif self._st == 2:
            self._do_move(pos)
        elif self._st == 3:
            self._do_resize(pos)

        self._clamp()
        self._redraw()
        self._emit()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._st:
            if self._crop.width() < self._MIN or self._crop.height() < self._MIN:
                self._crop = QRectF(self._bounds)
            self._st = 0
            self._clamp()
            self._redraw()
            self._emit()
        super().mouseReleaseEvent(event)

    # ── drag operations ──────────────────────────────────

    def _do_draw(self, pos):
        o = self._m0
        w, h = pos.x() - o.x(), pos.y() - o.y()
        if self._aspect > 0:
            aw, ah = abs(w), abs(h)
            if aw / max(ah, 1) > self._aspect:
                ah = aw / self._aspect
            else:
                aw = ah * self._aspect
            w = aw if w >= 0 else -aw
            h = ah if h >= 0 else -ah
        self._crop = QRectF(o.x(), o.y(), w, h).normalized()

    def _do_move(self, pos):
        d = pos - self._m0
        r = self._r0.translated(d)
        b = self._bounds
        if r.left() < b.left():
            r.moveLeft(b.left())
        if r.top() < b.top():
            r.moveTop(b.top())
        if r.right() > b.right():
            r.moveRight(b.right())
        if r.bottom() > b.bottom():
            r.moveBottom(b.bottom())
        self._crop = r

    def _do_resize(self, pos):
        r = QRectF(self._r0)
        d = pos - self._m0
        h = self._hid

        # Adjust edges based on which handle is dragged
        if h in (1, 4, 6):
            r.setLeft(min(self._r0.left() + d.x(), r.right() - self._MIN))
        if h in (3, 5, 8):
            r.setRight(max(self._r0.right() + d.x(), r.left() + self._MIN))
        if h in (1, 2, 3):
            r.setTop(min(self._r0.top() + d.y(), r.bottom() - self._MIN))
        if h in (6, 7, 8):
            r.setBottom(max(self._r0.bottom() + d.y(), r.top() + self._MIN))

        # Apply aspect-ratio constraint
        if self._aspect > 0:
            w = r.width()
            nh = w / self._aspect
            if h in (1,):
                r = QRectF(r.right() - w, r.bottom() - nh, w, nh)
            elif h in (2,):
                r.setTop(r.bottom() - nh)
            elif h in (3,):
                r = QRectF(r.left(), r.bottom() - nh, w, nh)
            elif h == 4:
                nw = r.height() * self._aspect
                r.setLeft(r.right() - nw)
            elif h == 5:
                nw = r.height() * self._aspect
                r.setRight(r.left() + nw)
            elif h in (6,):
                r = QRectF(r.right() - w, r.top(), w, nh)
            elif h in (7,):
                r.setBottom(r.top() + nh)
            elif h in (8,):
                r = QRectF(r.left(), r.top(), w, nh)

        if r.width() >= self._MIN and r.height() >= self._MIN:
            self._crop = r
