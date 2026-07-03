"""
Komponen dan utilitas GUI untuk Image Resolver.
"""

from typing import Optional
import tkinter as tk

from src.constants import INPUT_EXTS, EXT_MAP


class Tooltip:
    """Tooltip widget yang muncul saat hover pada elemen."""
    
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _):
        """Tampilkan tooltip."""
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=self.text, background="#fffde7", relief="solid",
            borderwidth=1, font=("Segoe UI", 9), padx=6, pady=3
        ).pack()

    def hide(self, _):
        """Sembunyikan tooltip."""
        if self.tip:
            self.tip.destroy()
            self.tip = None


def int_or_none(val: str) -> Optional[int]:
    """
    Parse string ke integer atau return None jika invalid/tidak positif.
    
    Args:
        val: String untuk diparse
    
    Returns:
        Integer (positif) atau None
    """
    try:
        v = int(val.strip())
        return v if v > 0 else None
    except (ValueError, AttributeError):
        return None


def float_or_none(val: str) -> Optional[float]:
    """
    Parse string ke float atau return None jika invalid/tidak positif.
    
    Args:
        val: String untuk diparse
    
    Returns:
        Float (positif) atau None
    """
    try:
        v = float(val.strip())
        return v if v > 0 else None
    except (ValueError, AttributeError):
        return None


def filetypes_input(i18n=None):
    """
    Return list filetypes untuk file dialog input.
    
    Args:
        i18n: Optional localization function for label translation
    
    Returns:
        List tuple (format_name, pattern)
    """
    exts = " ".join(f"*{e}" for e in sorted(INPUT_EXTS))
    lbl_images = i18n("all_images") if i18n else "All images"
    lbl_files = i18n("all_files") if i18n else "All files"
    return [(lbl_images, exts), (lbl_files, "*.*")]
