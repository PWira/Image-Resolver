"""
Theme configuration for Image Resolver.

╔══════════════════════════════════════════════════════════════╗
║  EDIT THIS FILE TO CHANGE THE ENTIRE APP'S LOOK AND FEEL   ║
║  Just change the color values below and restart the app.    ║
╚══════════════════════════════════════════════════════════════╝
"""

# ── Base Colors ──────────────────────────────────────────────
# These three colors define the entire palette. Change them freely.

WHITE       = "#FFFFFF"       # Primary text, highlights
BLACK_MATTE = "#1A1A1A"       # Dark surfaces, cards
GOLD        = "#C9A84C"       # Accent buttons, active elements

# ── Derived Colors ───────────────────────────────────────────
# These are computed from the base colors. You can override them too.

DARK_BG      = "#121212"      # Deepest background (window)
CARD_BG      = "#1E1E1E"      # Panel / card background
BORDER       = "#2A2A2A"      # Subtle borders between sections
TEXT_PRIMARY = WHITE           # Main text color
TEXT_DIM     = "#888888"       # Hint text, disabled labels
GOLD_HOVER   = "#D4B65A"      # Button hover state
GOLD_PRESSED = "#B8963F"      # Button pressed state
SUCCESS      = "#4CAF50"      # Success log entries
ERROR        = "#E53935"      # Error log entries
INFO         = "#64B5F6"      # Info log entries

# ── Fonts ────────────────────────────────────────────────────

FONT_FAMILY  = "Segoe UI"
FONT_SIZE    = 11             # Base font size in points
FONT_SIZE_SM = 9              # Small labels / hints
FONT_SIZE_LG = 14             # Section headers

# ── Dimensions ───────────────────────────────────────────────

BORDER_RADIUS = 6             # Rounded corner radius in pixels
SPACING       = 8             # Default spacing between elements
ICON_SIZE     = 18            # Toolbar icon size


def get_stylesheet() -> str:
    """
    Build and return the complete Qt stylesheet string.

    Every widget in the app uses this single stylesheet, so changing
    any color variable above will automatically update the entire UI.
    """
    return f"""
    /* ── Global ─────────────────────────────────────── */
    QMainWindow, QDialog {{
        background-color: {DARK_BG};
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_SIZE}pt;
    }}

    QWidget {{
        color: {TEXT_PRIMARY};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_SIZE}pt;
    }}

    /* ── Tab Bar ─────────────────────────────────────── */
    QTabWidget::pane {{
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        background-color: {CARD_BG};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: {DARK_BG};
        color: {TEXT_DIM};
        padding: 10px 28px;
        margin-right: 2px;
        border: 1px solid {BORDER};
        border-bottom: none;
        border-top-left-radius: {BORDER_RADIUS}px;
        border-top-right-radius: {BORDER_RADIUS}px;
        font-weight: bold;
    }}

    QTabBar::tab:selected {{
        background-color: {CARD_BG};
        color: {GOLD};
        border-bottom: 2px solid {GOLD};
    }}

    QTabBar::tab:hover:!selected {{
        color: {TEXT_PRIMARY};
        background-color: {BORDER};
    }}

    /* ── Buttons ──────────────────────────────────────── */
    QPushButton {{
        background-color: {BORDER};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        padding: 8px 18px;
        font-weight: bold;
    }}

    QPushButton:hover {{
        background-color: #333333;
        border-color: {TEXT_DIM};
    }}

    QPushButton:pressed {{
        background-color: #404040;
    }}

    /* Primary action buttons (gold) */
    QPushButton#primaryBtn {{
        background-color: {GOLD};
        color: {BLACK_MATTE};
        border: none;
        padding: 12px 36px;
        font-size: {FONT_SIZE_LG}pt;
        font-weight: bold;
        border-radius: {BORDER_RADIUS}px;
    }}

    QPushButton#primaryBtn:hover {{
        background-color: {GOLD_HOVER};
    }}

    QPushButton#primaryBtn:pressed {{
        background-color: {GOLD_PRESSED};
    }}

    QPushButton#primaryBtn:disabled {{
        background-color: #3A3520;
        color: {TEXT_DIM};
    }}

    /* ── Inputs ───────────────────────────────────────── */
    QLineEdit, QSpinBox, QDoubleSpinBox {{
        background-color: {DARK_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS - 2}px;
        padding: 6px 10px;
        selection-background-color: {GOLD};
        selection-color: {BLACK_MATTE};
    }}

    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
        border-color: {GOLD};
    }}

    /* ── Combo Box ────────────────────────────────────── */
    QComboBox {{
        background-color: {DARK_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS - 2}px;
        padding: 6px 10px;
        min-width: 80px;
    }}

    QComboBox:focus {{
        border-color: {GOLD};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox::down-arrow {{
        image: none;
        border-left: 5px solid transparent;
        border-right: 5px solid transparent;
        border-top: 6px solid {TEXT_DIM};
        margin-right: 8px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        selection-background-color: {GOLD};
        selection-color: {BLACK_MATTE};
        outline: none;
    }}

    /* ── Slider ───────────────────────────────────────── */
    QSlider::groove:horizontal {{
        height: 6px;
        background-color: {BORDER};
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background-color: {GOLD};
        width: 16px;
        height: 16px;
        margin: -5px 0;
        border-radius: 8px;
    }}

    QSlider::handle:horizontal:hover {{
        background-color: {GOLD_HOVER};
    }}

    QSlider::sub-page:horizontal {{
        background-color: {GOLD};
        border-radius: 3px;
    }}

    /* ── Progress Bar ─────────────────────────────────── */
    QProgressBar {{
        background-color: {BORDER};
        border: none;
        border-radius: 4px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}

    QProgressBar::chunk {{
        background-color: {GOLD};
        border-radius: 4px;
    }}

    /* ── List Widget ──────────────────────────────────── */
    QListWidget {{
        background-color: {DARK_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        padding: 4px;
        outline: none;
    }}

    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 4px;
    }}

    QListWidget::item:selected {{
        background-color: rgba(201, 168, 76, 0.2);
        color: {GOLD};
    }}

    QListWidget::item:hover:!selected {{
        background-color: rgba(255, 255, 255, 0.05);
    }}

    /* ── Scroll Bar ───────────────────────────────────── */
    QScrollBar:vertical {{
        background-color: transparent;
        width: 8px;
        margin: 0;
    }}

    QScrollBar::handle:vertical {{
        background-color: {BORDER};
        border-radius: 4px;
        min-height: 30px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {TEXT_DIM};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 8px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {BORDER};
        border-radius: 4px;
        min-width: 30px;
    }}

    /* ── Check Box ────────────────────────────────────── */
    QCheckBox {{
        spacing: 8px;
        color: {TEXT_PRIMARY};
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {TEXT_DIM};
        border-radius: 4px;
        background-color: transparent;
    }}

    QCheckBox::indicator:checked {{
        background-color: {GOLD};
        border-color: {GOLD};
    }}

    QCheckBox::indicator:hover {{
        border-color: {GOLD};
    }}

    /* ── Radio Button ─────────────────────────────────── */
    QRadioButton {{
        spacing: 8px;
        color: {TEXT_PRIMARY};
    }}

    QRadioButton::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {TEXT_DIM};
        border-radius: 10px;
        background-color: transparent;
    }}

    QRadioButton::indicator:checked {{
        background-color: {GOLD};
        border-color: {GOLD};
    }}

    QRadioButton::indicator:hover {{
        border-color: {GOLD};
    }}

    /* ── Group Box ─────────────────────────────────────── */
    QGroupBox {{
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        margin-top: 12px;
        padding-top: 16px;
        font-weight: bold;
        color: {GOLD};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {GOLD};
    }}

    /* ── Labels ────────────────────────────────────────── */
    QLabel {{
        color: {TEXT_PRIMARY};
        background-color: transparent;
    }}

    QLabel#dimLabel {{
        color: {TEXT_DIM};
        font-size: {FONT_SIZE_SM}pt;
    }}

    QLabel#headerLabel {{
        color: {GOLD};
        font-size: {FONT_SIZE_LG}pt;
        font-weight: bold;
    }}

    /* ── Text Edit (Log) ──────────────────────────────── */
    QTextEdit {{
        background-color: {DARK_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        padding: 6px;
        font-family: "Consolas", "Courier New", monospace;
        font-size: {FONT_SIZE_SM}pt;
    }}

    /* ── Separator ────────────────────────────────────── */
    QFrame[frameShape="4"] {{
        color: {BORDER};
        max-height: 1px;
    }}

    /* ── Tool Tip ─────────────────────────────────────── */
    QToolTip {{
        background-color: {CARD_BG};
        color: {TEXT_PRIMARY};
        border: 1px solid {GOLD};
        border-radius: 4px;
        padding: 6px;
        font-size: {FONT_SIZE_SM}pt;
    }}

    /* ── Splitter ─────────────────────────────────────── */
    QSplitter::handle {{
        background-color: {BORDER};
    }}
    QSplitter::handle:hover {{
        background-color: {GOLD};
    }}
    QSplitter::handle:vertical {{
        height: 6px;
    }}
    QSplitter::handle:horizontal {{
        width: 6px;
    }}

    /* ── Scroll Area ──────────────────────────────────── */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* ── Canvas (Crop Preview) ────────────────────────── */
    QGraphicsView {{
        background-color: #0D0D0D;
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
    }}
    """
