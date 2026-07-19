"""
Reusable Qt UI components for Quick Image Formatting.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFrame, QSizePolicy,
    QGraphicsView, QGraphicsScene, QSpinBox,
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QRectF, QPointF, QSizeF
from PySide6.QtGui import QPixmap, QImage, QPen, QBrush, QColor, QPainter

from src.constants import INPUT_EXTS
import src.theme as theme


def create_checkerboard_brush(size=16):
    """Create a checkerboard brush (transparent grid) based on the active theme."""
    is_light = (getattr(theme, "current_palette_name", "gold") == "light")
    if is_light:
        color1 = QColor("#FFFFFF")
        color2 = QColor("#EAEAEA")
    else:
        color1 = QColor("#181818")
        color2 = QColor("#222222")
    pixmap = QPixmap(size, size)
    pixmap.fill(color1)
    painter = QPainter(pixmap)
    painter.fillRect(0, 0, size // 2, size // 2, color2)
    painter.fillRect(size // 2, size // 2, size // 2, size // 2, color2)
    painter.end()
    return QBrush(pixmap)



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

    def setTitle(self, title: str):
        """Set a new title for the collapsible panel."""
        self._title = title
        if self._is_expanded:
            self._toggle_btn.setText(f"▼  {title}")
        else:
            self._toggle_btn.setText(f"▶  {title}")


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
        self._sx = 1.0
        self._sy = 1.0
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

    def drawBackground(self, painter, rect):
        """Draw a checkerboard transparent grid only within the scene (image canvas) bounds."""
        painter.fillRect(rect, QColor("#000000"))
        sr = self.sceneRect()
        if not sr.isNull() and self._pm_item:
            painter.fillRect(sr, create_checkerboard_brush())

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
        self._sx = pm.width() / iw if iw > 0 else self._scale
        self._sy = pm.height() / ih if ih > 0 else self._scale
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
        self._sx = 1.0
        self._sy = 1.0

    def set_crop_rect(self, x, y, w, h):
        """Set crop rectangle from image-pixel coordinates (external sync)."""
        if self._locked or self._sx <= 0 or self._sy <= 0:
            return
        self._locked = True
        self._crop = QRectF(x * self._sx, y * self._sy, w * self._sx, h * self._sy)
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
        if self._sx <= 0 or self._sy <= 0:
            return 0, 0, 0, 0
        iw, ih = self._img_sz
        x = max(0, round(self._crop.x() / self._sx))
        y = max(0, round(self._crop.y() / self._sy))
        w = max(1, min(round(self._crop.width() / self._sx), iw - x))
        h = max(1, min(round(self._crop.height() / self._sy), ih - y))
        return x, y, w, h

    def _emit(self):
        if self._locked:
            return
        self._locked = True
        self.cropChanged.emit(*self._to_img())
        self._locked = False

    def _clamp(self):
        if self._sx <= 0 or self._sy <= 0:
            return

        # 1. Map to image space coordinates (as integers)
        x = round(self._crop.x() / self._sx)
        y = round(self._crop.y() / self._sy)
        w = round(self._crop.width() / self._sx)
        h = round(self._crop.height() / self._sy)

        # 2. Bound checks against the original image dimensions
        iw, ih = self._img_sz

        # Ensure minimum size is at least 1 image pixel
        min_pixels_w = max(1, round(self._MIN / self._sx))
        min_pixels_h = max(1, round(self._MIN / self._sy))

        w = max(min_pixels_w, w)
        h = max(min_pixels_h, h)

        # Ensure we fit within the image bounds
        if x < 0:
            x = 0
        if y < 0:
            y = 0
        if x + w > iw:
            w = iw - x
            if w < min_pixels_w:
                x = max(0, iw - min_pixels_w)
                w = iw - x
        if y + h > ih:
            h = ih - y
            if h < min_pixels_h:
                y = max(0, ih - min_pixels_h)
                h = ih - y

        # 3. Save snapped scene coordinates
        self._crop = QRectF(x * self._sx, y * self._sy, w * self._sx, h * self._sy)

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

        border_pen = QPen(QColor(theme.GOLD), 1, Qt.SolidLine)
        border_pen.setCosmetic(True)
        self._gfx_border = self._scene.addRect(cr, border_pen)

        hs = self._HD
        hp, hb = QPen(QColor("#000000"), 1), QBrush(QColor(theme.GOLD))
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
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() != Qt.LeftButton or not self._pm_item:
            return super().mousePressEvent(event)
        pos = self.mapToScene(event.pos())

        h = self._hit(pos)
        if h:
            self._st, self._hid = 3, h
        elif self._bounds.contains(pos):
            if self._crop.contains(pos) and self._can_move:
                self._st = 2
            else:
                self._st = 1
                self._crop = QRectF(pos, QSizeF(0, 0))
        else:
            return

        self._m0 = pos
        self._r0 = QRectF(self._crop)
        event.accept()

    def mouseMoveEvent(self, event):
        if getattr(self, "_panning", False):
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

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
        if event.button() == Qt.MiddleButton and getattr(self, "_panning", False):
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._st:
            if self._crop.width() < self._MIN or self._crop.height() < self._MIN:
                self._crop = QRectF(self._bounds)
            self._st = 0
            self._clamp()
            self._redraw()
            self._emit()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resetTransform()
            event.accept()

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        old_pos = self.mapToScene(pos)

        angle = event.angleDelta().y()
        transform = self.transform()
        current_zoom = transform.m11()

        if angle > 0:
            if current_zoom < 50.0:
                self.scale(zoom_in_factor, zoom_in_factor)
        elif angle < 0:
            if current_zoom > 0.1:
                self.scale(zoom_out_factor, zoom_out_factor)
        else:
            return

        new_pos = self.mapToScene(pos)
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())


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


class FittedImageView(QGraphicsView):
    """
    A QGraphicsView that simply displays an image scaled to fit the viewport.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._pil_img = None
        self._pm_item = None

    def drawBackground(self, painter, rect):
        """Draw a checkerboard transparent grid only within the scene (image canvas) bounds."""
        painter.fillRect(rect, QColor("#000000"))
        sr = self.sceneRect()
        if not sr.isNull() and self._pm_item:
            painter.fillRect(sr, create_checkerboard_brush())

    def load_image(self, pil_img):
        self.resetTransform()
        self._pil_img = pil_img
        self._scene.clear()
        self._pm_item = None
        if not pil_img:
            return
        iw, ih = pil_img.size
        rgba = pil_img.convert("RGBA") if pil_img.mode != "RGBA" else pil_img
        raw = rgba.tobytes("raw", "RGBA")
        qimg = QImage(raw, iw, ih, 4 * iw, QImage.Format_RGBA8888)
        full = QPixmap.fromImage(qimg)
        vw = self.viewport().width() or 380
        vh = self.viewport().height() or 240
        scale = min(vw / iw, vh / ih, 1.0)
        pm = full.scaled(
            int(iw * scale), int(ih * scale),
            Qt.KeepAspectRatio, Qt.SmoothTransformation,
        )
        self._pm_item = self._scene.addPixmap(pm)
        self._scene.setSceneRect(QRectF(pm.rect()))

    def clear_image(self):
        self._pil_img = None
        self._scene.clear()
        self._pm_item = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if getattr(self, "_panning", False):
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and getattr(self, "_panning", False):
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.resetTransform()
            event.accept()

    def wheelEvent(self, event):
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        old_pos = self.mapToScene(pos)

        angle = event.angleDelta().y()
        transform = self.transform()
        current_zoom = transform.m11()

        if angle > 0:
            if current_zoom < 50.0:
                self.scale(zoom_in_factor, zoom_in_factor)
        elif angle < 0:
            if current_zoom > 0.1:
                self.scale(zoom_out_factor, zoom_out_factor)
        else:
            return

        new_pos = self.mapToScene(pos)
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._pil_img:
            self.load_image(self._pil_img)


class PlusMinusSpinBox(QWidget):
    valueChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.btn_minus = QPushButton("-")
        self.btn_minus.setObjectName("flatArrowBtn")
        self.btn_minus.setFixedWidth(24)
        self.btn_minus.setFixedHeight(28)

        self.spin = QSpinBox()

        self.btn_plus = QPushButton("+")
        self.btn_plus.setObjectName("flatArrowBtn")
        self.btn_plus.setFixedWidth(24)
        self.btn_plus.setFixedHeight(28)

        layout.addWidget(self.btn_minus)
        layout.addWidget(self.spin, 1)
        layout.addWidget(self.btn_plus)

        self.btn_minus.clicked.connect(self._on_minus)
        self.btn_plus.clicked.connect(self._on_plus)
        self.spin.valueChanged.connect(self.valueChanged.emit)

    def value(self) -> int:
        return self.spin.value()

    def setValue(self, val: int):
        self.spin.setValue(val)

    def setRange(self, min_val: int, max_val: int):
        self.spin.setRange(min_val, max_val)

    def setSuffix(self, text: str):
        self.spin.setSuffix(text)

    def setSpecialValueText(self, text: str):
        self.spin.setSpecialValueText(text)

    def setSingleStep(self, step: int):
        self.spin.setSingleStep(step)

    def singleStep(self) -> int:
        return self.spin.singleStep()

    def _on_minus(self):
        self.spin.setValue(self.spin.value() - self.spin.singleStep())

    def _on_plus(self):
        self.spin.setValue(self.spin.value() + self.spin.singleStep())


