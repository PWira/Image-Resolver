"""
LUT Processing Engine for Quick Image Formatting.
Handles 3D LUT loading (.cube, .3dl), LUT generation, presets, and export to .cube format.
"""

import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from PIL import Image, ImageFilter, ImageEnhance, ImageOps


def parse_cube_file(file_path: Union[str, Path]) -> ImageFilter.Color3DLUT:
    """
    Parse Adobe .cube 3D LUT file format into a Pillow Color3DLUT.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"LUT file not found: {path}")

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    size = None
    table = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("LUT_3D_SIZE"):
            parts = line.split()
            if len(parts) >= 2:
                size = int(parts[1])
        elif line.startswith("TITLE") or line.startswith("DOMAIN_"):
            continue
        else:
            parts = line.split()
            if len(parts) == 3:
                try:
                    r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                    table.extend([r, g, b])
                except ValueError:
                    continue

    if size is None:
        # Estimate size from table count
        num_colors = len(table) // 3
        size = round(num_colors ** (1.0 / 3.0))

    if len(table) != size * size * size * 3:
        raise ValueError(f"Invalid LUT data in {path.name}: expected {size**3 * 3} values, got {len(table)}")

    return ImageFilter.Color3DLUT(size, table)


def parse_3dl_file(file_path: Union[str, Path]) -> ImageFilter.Color3DLUT:
    """
    Parse .3dl LUT file format into a Pillow Color3DLUT.
    """
    path = Path(file_path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    table = []
    max_val = 1023.0

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("<") or "3DL" in line.upper():
            continue
        parts = line.split()
        if len(parts) == 3:
            try:
                r, g, b = float(parts[0]), float(parts[1]), float(parts[2])
                if r > 255 or g > 255 or b > 255:
                    max_val = max(max_val, r, g, b)
                table.extend([r, g, b])
            except ValueError:
                continue

    num_colors = len(table) // 3
    size = round(num_colors ** (1.0 / 3.0))

    # Normalize values to 0.0 - 1.0 range
    if max_val > 1.0:
        table = [v / max_val for v in table]

    if len(table) != size * size * size * 3:
        raise ValueError(f"Invalid .3dl LUT file format in {path.name}")

    return ImageFilter.Color3DLUT(size, table)


def load_lut_file(file_path: Union[str, Path]) -> ImageFilter.Color3DLUT:
    """
    Load a LUT file (.cube or .3dl).
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext == ".cube":
        return parse_cube_file(path)
    elif ext == ".3dl":
        return parse_3dl_file(path)
    else:
        raise ValueError(f"Unsupported LUT format: {ext}")


def rgb_to_hsv(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Convert RGB float (0..1) to HSV float (H: 0..360, S: 0..1, V: 0..1)."""
    maxc = max(r, g, b)
    minc = min(r, g, b)
    v = maxc
    if maxc == minc:
        return 0.0, 0.0, v
    d = maxc - minc
    s = d / maxc
    rc = (maxc - r) / d
    gc = (maxc - g) / d
    bc = (maxc - b) / d
    if r == maxc:
        h = bc - gc
    elif g == maxc:
        h = 2.0 + rc - bc
    else:
        h = 4.0 + gc - rc
    h = (h / 6.0) % 1.0
    return h * 360.0, s, v


def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[float, float, float]:
    """Convert HSV float (H: 0..360, S: 0..1, V: 0..1) to RGB float (0..1)."""
    if s == 0.0:
        return v, v, v
    h = (h % 360.0) / 60.0
    i = int(math.floor(h))
    f = h - i
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))
    if i == 0:
        return v, t, p
    elif i == 1:
        return q, v, p
    elif i == 2:
        return p, v, t
    elif i == 3:
        return p, q, v
    elif i == 4:
        return t, p, v
    else:
        return v, p, q


import numpy as np


def generate_lut_table_data(
    brightness: float = 0.0,     # -100 to +100
    contrast: float = 0.0,       # -100 to +100
    saturation: float = 0.0,     # -100 to +100
    temperature: float = 0.0,    # -100 to +100
    tint: float = 0.0,           # -100 to +100
    gamma: float = 1.0,          # 0.2 to 2.5
    hue_shift: float = 0.0,      # -180 to +180
    r_gain: float = 1.0,         # 0.0 to 2.0
    g_gain: float = 1.0,         # 0.0 to 2.0
    b_gain: float = 1.0,         # 0.0 to 2.0
    size: int = 17
) -> List[float]:
    """
    Generate flattened RGB float array for a 3D LUT of size `size` using NumPy vectorization.
    """
    idx = np.linspace(0.0, 1.0, size, dtype=np.float32)
    b_grid, g_grid, r_grid = np.meshgrid(idx, idx, idx, indexing="ij")

    b_offset = brightness / 100.0 * 0.5
    c_factor = (255.0 + contrast * 2.55) / 255.0 if contrast >= 0 else (255.0 + contrast * 1.5) / 255.0
    c_factor = max(0.01, c_factor)
    sat_factor = max(0.0, 1.0 + saturation / 100.0)
    temp_r = 1.0 + (temperature / 100.0) * 0.2
    temp_b = 1.0 - (temperature / 100.0) * 0.2
    tint_g = 1.0 + (tint / 100.0) * 0.2
    inv_gamma = 1.0 / max(0.1, gamma)

    r = r_grid * (r_gain * temp_r)
    g = g_grid * (g_gain * tint_g)
    b = b_grid * (b_gain * temp_b)

    r = (r - 0.5) * c_factor + 0.5 + b_offset
    g = (g - 0.5) * c_factor + 0.5 + b_offset
    b = (b - 0.5) * c_factor + 0.5 + b_offset

    r = np.clip(r, 0.0, 1.0)
    g = np.clip(g, 0.0, 1.0)
    b = np.clip(b, 0.0, 1.0)

    if inv_gamma != 1.0:
        r = r ** inv_gamma
        g = g ** inv_gamma
        b = b ** inv_gamma

    if sat_factor != 1.0 or hue_shift != 0.0:
        gray = 0.299 * r + 0.587 * g + 0.114 * b
        r = np.clip(gray + (r - gray) * sat_factor, 0.0, 1.0)
        g = np.clip(gray + (g - gray) * sat_factor, 0.0, 1.0)
        b = np.clip(gray + (b - gray) * sat_factor, 0.0, 1.0)

    table = np.stack([r, g, b], axis=-1).astype(np.float32).reshape(-1).tolist()
    return table


def generate_lut_from_settings(
    brightness: float = 0.0,
    contrast: float = 0.0,
    saturation: float = 0.0,
    temperature: float = 0.0,
    tint: float = 0.0,
    gamma: float = 1.0,
    hue_shift: float = 0.0,
    r_gain: float = 1.0,
    g_gain: float = 1.0,
    b_gain: float = 1.0,
    size: int = 17
) -> ImageFilter.Color3DLUT:
    """Generate ImageFilter.Color3DLUT from color parameters."""
    table = generate_lut_table_data(
        brightness=brightness, contrast=contrast, saturation=saturation,
        temperature=temperature, tint=tint, gamma=gamma, hue_shift=hue_shift,
        r_gain=r_gain, g_gain=g_gain, b_gain=b_gain, size=size
    )
    return ImageFilter.Color3DLUT(size, table)


def export_lut_to_cube(
    file_path: Union[str, Path],
    brightness: float = 0.0,
    contrast: float = 0.0,
    saturation: float = 0.0,
    temperature: float = 0.0,
    tint: float = 0.0,
    gamma: float = 1.0,
    hue_shift: float = 0.0,
    r_gain: float = 1.0,
    g_gain: float = 1.0,
    b_gain: float = 1.0,
    title: str = "Custom LUT",
    size: int = 33
) -> None:
    """Export LUT settings as a standard Adobe .cube 3D LUT file."""
    table = generate_lut_table_data(
        brightness=brightness, contrast=contrast, saturation=saturation,
        temperature=temperature, tint=tint, gamma=gamma, hue_shift=hue_shift,
        r_gain=r_gain, g_gain=g_gain, b_gain=b_gain, size=size
    )

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f'TITLE "{title}"',
        f"LUT_3D_SIZE {size}",
        "# Created with Quick Image Formatting",
    ]

    for i in range(0, len(table), 3):
        r, g, b = table[i], table[i + 1], table[i + 2]
        lines.append(f"{r:.6f} {g:.6f} {b:.6f}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# Built-in presets dictionary with parameter definitions
PRESET_LUT_SETTINGS: Dict[str, dict] = {
    "Cinematic": {
        "brightness": -3, "contrast": 18, "saturation": 12, "temperature": 8,
        "tint": -5, "gamma": 1.08, "hue_shift": 0, "r_gain": 1.05, "g_gain": 0.98, "b_gain": 0.92
    },
    "Vintage Film": {
        "brightness": 4, "contrast": -10, "saturation": -25, "temperature": 15,
        "tint": 8, "gamma": 0.92, "hue_shift": 0, "r_gain": 1.10, "g_gain": 1.02, "b_gain": 0.85
    },
    "Warm Sunset": {
        "brightness": 2, "contrast": 10, "saturation": 20, "temperature": 35,
        "tint": 5, "gamma": 1.0, "hue_shift": 0, "r_gain": 1.15, "g_gain": 1.0, "b_gain": 0.80
    },
    "Cool Ocean": {
        "brightness": 0, "contrast": 8, "saturation": 10, "temperature": -30,
        "tint": -8, "gamma": 1.05, "hue_shift": 0, "r_gain": 0.85, "g_gain": 1.0, "b_gain": 1.18
    },
    "Sepia": {
        "brightness": 5, "contrast": 5, "saturation": -60, "temperature": 40,
        "tint": 15, "gamma": 0.95, "hue_shift": 0, "r_gain": 1.20, "g_gain": 1.0, "b_gain": 0.70
    },
    "High Contrast B&W": {
        "brightness": 0, "contrast": 45, "saturation": -100, "temperature": 0,
        "tint": 0, "gamma": 1.1, "hue_shift": 0, "r_gain": 1.0, "g_gain": 1.0, "b_gain": 1.0
    },
    "Teal & Orange": {
        "brightness": -2, "contrast": 25, "saturation": 15, "temperature": 10,
        "tint": -15, "gamma": 1.05, "hue_shift": 0, "r_gain": 1.12, "g_gain": 0.92, "b_gain": 1.08
    },
    "Cyberpunk": {
        "brightness": 5, "contrast": 30, "saturation": 35, "temperature": -20,
        "tint": 25, "gamma": 1.15, "hue_shift": 15, "r_gain": 1.15, "g_gain": 0.85, "b_gain": 1.25
    },
    "Drama": {
        "brightness": -10, "contrast": 35, "saturation": -15, "temperature": -5,
        "tint": 0, "gamma": 1.2, "hue_shift": 0, "r_gain": 0.95, "g_gain": 0.95, "b_gain": 1.05
    },
    "Soft Pastel": {
        "brightness": 12, "contrast": -18, "saturation": -15, "temperature": 10,
        "tint": 5, "gamma": 0.88, "hue_shift": 0, "r_gain": 1.05, "g_gain": 1.02, "b_gain": 1.05
    },
}


def get_preset_lut(name: str, size: int = 17) -> Optional[ImageFilter.Color3DLUT]:
    """Get preset LUT object by name."""
    if name not in PRESET_LUT_SETTINGS:
        return None
    params = PRESET_LUT_SETTINGS[name]
    return generate_lut_from_settings(**params, size=size)


def apply_lut(img: Image.Image, lut: ImageFilter.Color3DLUT, intensity: float = 1.0) -> Image.Image:
    """
    Apply 3D LUT to image with blend intensity (0.0 to 1.0).
    """
    if lut is None or intensity <= 0.0:
        return img

    intensity = max(0.0, min(1.0, intensity))

    # Keep track of original mode
    orig_mode = img.mode
    has_alpha = orig_mode in ("RGBA", "LA") or (orig_mode == "P" and "transparency" in img.info)

    if orig_mode not in ("RGB", "RGBA"):
        work_img = img.convert("RGBA" if has_alpha else "RGB")
    else:
        work_img = img.copy()

    # Filter with LUT (Pillow applies LUT to RGB channels)
    filtered = work_img.filter(lut)

    if intensity >= 1.0:
        out_img = filtered
    else:
        out_img = Image.blend(work_img, filtered, intensity)

    if out_img.mode != orig_mode and orig_mode in ("RGB", "RGBA"):
        out_img = out_img.convert(orig_mode)

    return out_img
