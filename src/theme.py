"""
Theme configuration for Quick Image Formatting.

╔══════════════════════════════════════════════════════════════╗
║  EDIT THIS FILE TO CHANGE THE ENTIRE APP'S LOOK AND FEEL   ║
║  Just change the color values below and restart the app.    ║
╚══════════════════════════════════════════════════════════════╝
"""

import colorsys

# ── Preset Theme Palettes ────────────────────────────────────
PALETTES = {
    "gold": {
        "WHITE": "#FFFFFF",
        "BLACK_MATTE": "#1A1A1A",
        "GOLD": "#C9A84C",
        "DARK_BG": "#121212",
        "CARD_BG": "#1E1E1E",
        "BORDER": "#2A2A2A",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_DIM": "#888888",
        "GOLD_HOVER": "#D4B65A",
        "GOLD_PRESSED": "#B8963F",
        "SUCCESS": "#4CAF50",
        "ERROR": "#E53935",
        "INFO": "#64B5F6",
    },
    "purple": {
        "WHITE": "#FFFFFF",
        "BLACK_MATTE": "#110D26",
        "GOLD": "#BD93F9",
        "DARK_BG": "#0F0C1B",
        "CARD_BG": "#1B172E",
        "BORDER": "#332B54",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_DIM": "#7F739F",
        "GOLD_HOVER": "#D6BBFF",
        "GOLD_PRESSED": "#9A66E8",
        "SUCCESS": "#50FA7B",
        "ERROR": "#FF5555",
        "INFO": "#8BE9FD",
    },
    "blue": {
        "WHITE": "#FFFFFF",
        "BLACK_MATTE": "#1C2433",
        "GOLD": "#88C0D0",
        "DARK_BG": "#171E29",
        "CARD_BG": "#232D3F",
        "BORDER": "#364560",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_DIM": "#889BB8",
        "GOLD_HOVER": "#A3D2E2",
        "GOLD_PRESSED": "#64A6BB",
        "SUCCESS": "#A3BE8C",
        "ERROR": "#BF616A",
        "INFO": "#B48EAD",
    },
    "green": {
        "WHITE": "#FFFFFF",
        "BLACK_MATTE": "#0D1A12",
        "GOLD": "#00F5D4",
        "DARK_BG": "#0A140E",
        "CARD_BG": "#13261B",
        "BORDER": "#244432",
        "TEXT_PRIMARY": "#FFFFFF",
        "TEXT_DIM": "#7AA28D",
        "GOLD_HOVER": "#46FDE6",
        "GOLD_PRESSED": "#00CCB0",
        "SUCCESS": "#50FA7B",
        "ERROR": "#FF5555",
        "INFO": "#8BE9FD",
    },
    "light": {
        "WHITE": "#1A1A1A",
        "BLACK_MATTE": "#FFFFFF",
        "GOLD": "#E65100",
        "DARK_BG": "#F4F5F7",
        "CARD_BG": "#FFFFFF",
        "BORDER": "#E1E4E8",
        "TEXT_PRIMARY": "#1A1A1A",
        "TEXT_DIM": "#6A737D",
        "GOLD_HOVER": "#FF6D00",
        "GOLD_PRESSED": "#D84315",
        "SUCCESS": "#28A745",
        "ERROR": "#D73A49",
        "INFO": "#0366D6",
    }
}

# ── Dynamic Colors State ─────────────────────────────────────
WHITE = "#FFFFFF"
BLACK_MATTE = "#1A1A1A"
GOLD = "#C9A84C"
DARK_BG = "#121212"
CARD_BG = "#1E1E1E"
BORDER = "#2A2A2A"
TEXT_PRIMARY = "#FFFFFF"
TEXT_DIM = "#888888"
GOLD_HOVER = "#D4B65A"
GOLD_PRESSED = "#B8963F"
SUCCESS = "#4CAF50"
ERROR = "#E53935"
INFO = "#64B5F6"

current_palette_name = "gold"
custom_accent_color = ""

def adjust_color_lightness(hex_color: str, factor: float) -> str:
    """Adjust lightness of a hex color using HSL conversion."""
    hex_color = hex_color.lstrip('#')
    try:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    except ValueError:
        return "#C9A84C"
    
    h, l, s = colorsys.rgb_to_hls(r/255.0, g/255.0, b/255.0)
    l = max(0.0, min(1.0, l * factor))
    nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
    return f"#{int(nr*255):02X}{int(ng*255):02X}{int(nb*255):02X}"

def set_active_palette(name: str):
    """Set preset palette variables globally."""
    global current_palette_name, custom_accent_color
    if name not in PALETTES:
        return
    current_palette_name = name
    custom_accent_color = ""
    _apply_palette(PALETTES[name])

def set_custom_accent(hex_color: str):
    """Derive custom accent colors and apply them on a dark slate background."""
    global current_palette_name, custom_accent_color
    current_palette_name = "custom"
    custom_accent_color = hex_color
    
    # Base custom color on Gold Dust dark mode background
    base = dict(PALETTES["gold"])
    base["GOLD"] = hex_color
    base["GOLD_HOVER"] = adjust_color_lightness(hex_color, 1.15)
    base["GOLD_PRESSED"] = adjust_color_lightness(hex_color, 0.85)
    _apply_palette(base)

def _apply_palette(palette: dict):
    global WHITE, BLACK_MATTE, GOLD, DARK_BG, CARD_BG, BORDER
    global TEXT_PRIMARY, TEXT_DIM, GOLD_HOVER, GOLD_PRESSED
    global SUCCESS, ERROR, INFO
    
    WHITE = palette["WHITE"]
    BLACK_MATTE = palette["BLACK_MATTE"]
    GOLD = palette["GOLD"]
    DARK_BG = palette["DARK_BG"]
    CARD_BG = palette["CARD_BG"]
    BORDER = palette["BORDER"]
    TEXT_PRIMARY = palette["TEXT_PRIMARY"]
    TEXT_DIM = palette["TEXT_DIM"]
    GOLD_HOVER = palette["GOLD_HOVER"]
    GOLD_PRESSED = palette["GOLD_PRESSED"]
    SUCCESS = palette["SUCCESS"]
    ERROR = palette["ERROR"]
    INFO = palette["INFO"]


# ── Fonts ────────────────────────────────────────────────────

FONT_FAMILY  = "Asta Sans, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
FONT_SIZE    = 10             # Base font size in points
FONT_SIZE_SM = 8              # Small labels / hints
FONT_SIZE_LG = 12             # Section headers

# ── Dimensions ───────────────────────────────────────────────

BORDER_RADIUS = 4             # Rounded corner radius in pixels
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
        background-color: rgba(255, 255, 255, 0.05);
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        padding: 6px 14px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: rgba(255, 255, 255, 0.1);
        border-color: {GOLD};
    }}

    QPushButton:pressed {{
        background-color: rgba(255, 255, 255, 0.03);
    }}

    QPushButton:disabled {{
        background-color: transparent;
        color: {TEXT_DIM};
        border: 1px solid {BORDER};
    }}

    /* Primary action buttons (gold) */
    QPushButton#primaryBtn {{
        background-color: {GOLD};
        color: {BLACK_MATTE};
        border: none;
        padding: 10px 24px;
        font-size: {FONT_SIZE}pt;
        font-weight: 600;
        border-radius: {BORDER_RADIUS}px;
    }}

    QPushButton#primaryBtn:hover {{
        background-color: {GOLD_HOVER};
    }}

    QPushButton#primaryBtn:pressed {{
        background-color: {GOLD_PRESSED};
    }}

    QPushButton#primaryBtn:disabled {{
        background-color: rgba(255, 255, 255, 0.02);
        color: {TEXT_DIM};
        border: 1px solid {BORDER};
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

    QSpinBox::up-button, QSpinBox::down-button {{
        width: 0px;
        border: none;
        background: transparent;
    }}

    QPushButton#flatArrowBtn {{
        background-color: transparent;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
        padding: 0;
        font-weight: bold;
        font-size: 11pt;
    }}

    QPushButton#flatArrowBtn:hover {{
        background-color: rgba(255, 255, 255, 0.05);
        border-color: {GOLD};
    }}

    QPushButton#flatArrowBtn:pressed {{
        background-color: rgba(255, 255, 255, 0.02);
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
        background-color: {DARK_BG};
    }}
    QSplitter::handle:hover {{
        background-color: {GOLD};
    }}
    QSplitter::handle:vertical {{
        height: 3px;
    }}
    QSplitter::handle:horizontal {{
        width: 3px;
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
        background-color: #000000;
        border: 1px solid {BORDER};
        border-radius: {BORDER_RADIUS}px;
    }}


    /* ── Custom Layout Restructuring Styles ───────────── */
    QFrame#headerPanel {{
        background-color: {CARD_BG};
        border: none;
        border-bottom: 1px solid {BORDER};
        border-radius: 0px;
    }}

    QPushButton#featureBtn {{
        background-color: transparent;
        color: {TEXT_DIM};
        border: 1px solid transparent;
        border-radius: 4px;
        padding: 6px 18px;
        font-weight: 500;
    }}

    QPushButton#featureBtn:hover {{
        color: {WHITE};
        background-color: rgba(255, 255, 255, 0.05);
    }}

    QPushButton#featureBtn:checked {{
        color: {GOLD};
        background-color: rgba(201, 168, 76, 0.15);
        border: 1px solid {GOLD};
    }}

    QPushButton#settingsBtn {{
        background-color: transparent;
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 6px 14px;
        font-weight: 500;
    }}

    QPushButton#settingsBtn:hover {{
        color: {GOLD};
        border-color: {GOLD};
        background-color: rgba(201, 168, 76, 0.05);
    }}

    /* ── Photoshop-Style QSliders ──────────────────────── */
    QSlider::groove:horizontal {{
        height: 4px;
        background: #333333;
        border: none;
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: #E0E0E0;
        border: 1px solid #111111;
        width: 10px;
        height: 12px;
        margin-top: -4px;
        margin-bottom: -4px;
        border-top-left-radius: 2px;
        border-top-right-radius: 2px;
        border-bottom-left-radius: 5px;
        border-bottom-right-radius: 5px;
    }}

    QSlider::handle:horizontal:hover {{
        background: #FFFFFF;
        border-color: #000000;
    }}

    QSlider::handle:horizontal:pressed {{
        background: #B0B0B0;
    }}

    QSlider#lut_gen_hue_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #FF0000, stop:0.17 #FFFF00, stop:0.33 #00FF00,
            stop:0.5 #00FFFF, stop:0.67 #0000FF, stop:0.83 #FF00FF, stop:1 #FF0000);
        border-radius: 2px;
    }}

    QSlider#lut_gen_temp_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #3A88EE, stop:0.5 #555555, stop:1 #EE983A);
        border-radius: 2px;
    }}

    QSlider#lut_gen_tint_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #3AEE68, stop:0.5 #555555, stop:1 #EE3AE3);
        border-radius: 2px;
    }}

    QSlider#lut_gen_b_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #111111, stop:0.5 #666666, stop:1 #EEEEEE);
        border-radius: 2px;
    }}

    QSlider#lut_gen_s_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #555555, stop:1 #FF3B3B);
        border-radius: 2px;
    }}

    QSlider#lut_gen_r_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #222222, stop:1 #FF4444);
        border-radius: 2px;
    }}

    QSlider#lut_gen_g_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #222222, stop:1 #44FF44);
        border-radius: 2px;
    }}

    QSlider#lut_gen_b_gain_slider::groove:horizontal {{
        height: 4px;
        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
            stop:0 #222222, stop:1 #4488FF);
        border-radius: 2px;
    }}

    QPushButton#settingsBtn::menu-indicator {{
        image: none;
        width: 0;
    }}
    """
