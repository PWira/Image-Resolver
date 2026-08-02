"""
Fungsi-fungsi core untuk pemrosesan gambar.
"""

import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from src.constants import (
    SVG_EXT, PDF_EXT, NEEDS_RGB, NEEDS_RGBA, QUALITY_FMT
)


def open_image(
    path: Path,
    page: int = 0,
    svg_width: Optional[int] = None,
    svg_height: Optional[int] = None,
    svg_scale: Optional[float] = None
) -> Image.Image:
    """
    Membuka gambar dari berbagai format termasuk SVG dan PDF.
    
    Args:
        path: Path ke file gambar
        page: Halaman untuk PDF (default: 0)
        svg_width: Lebar custom untuk SVG
        svg_height: Tinggi custom untuk SVG
        svg_scale: Skala untuk SVG
    
    Returns:
        PIL Image object
    """
    ext = path.suffix.lower()

    if ext in SVG_EXT:
        try:
            import cairosvg
        except ImportError:
            raise ImportError("cairosvg belum terinstal: pip install cairosvg")
        from io import BytesIO
        kwargs = {}
        if svg_width:
            kwargs["output_width"] = svg_width
        if svg_height:
            kwargs["output_height"] = svg_height
        if svg_scale and not svg_width and not svg_height:
            kwargs["scale"] = svg_scale
        png_bytes = cairosvg.svg2png(url=str(path), **kwargs)
        return Image.open(BytesIO(png_bytes)).convert("RGBA")

    if ext in PDF_EXT:
        try:
            import fitz
        except ImportError:
            raise ImportError("pymupdf belum terinstal: pip install pymupdf")
        from io import BytesIO
        with fitz.open(str(path)) as doc:
            pix = doc[page].get_pixmap(dpi=150)
            return Image.open(BytesIO(pix.tobytes("png")))

    return Image.open(path)


def save_image(
    img: Image.Image,
    dest: Path,
    quality: int = 90,
    fmt_override: Optional[str] = None
) -> None:
    """
    Menyimpan gambar dengan konversi mode otomatis sesuai format.
    
    Args:
        img: PIL Image object
        dest: Path tujuan
        quality: Kualitas kompresi (1-100)
        fmt_override: Override format output
    """
    fmt = fmt_override or dest.suffix.lstrip(".").upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt in ("JP2", "J2K", "JPC", "JPF", "JPX"):
        fmt = "JPEG2000"

    dest.parent.mkdir(parents=True, exist_ok=True)

    # Konversi mode gambar sesuai kebutuhan format
    if fmt in NEEDS_RGB and img.mode not in ("RGB", "L"):
        if img.mode == "P":
            img = img.convert("RGBA")
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
    elif fmt in NEEDS_RGBA and img.mode != "RGBA":
        img = img.convert("RGBA")

    kwargs = {}
    if fmt in QUALITY_FMT:
        kwargs["quality"] = quality
        kwargs["optimize"] = True
    if fmt == "PNG":
        kwargs["optimize"] = True

    img.save(str(dest), format=fmt, **kwargs)


def do_resize(
    img: Image.Image,
    width=None,
    height=None,
    scale=None,
    max_w=None,
    max_h=None,
    mode="fit"
) -> Image.Image:
    """
    Resize gambar dengan berbagai mode.
    
    Args:
        img: PIL Image object
        width: Target lebar
        height: Target tinggi
        scale: Faktor scale (0.5 = 50%)
        max_w: Lebar maksimal
        max_h: Tinggi maksimal
        mode: "fit"=proporsional, "exact"=tepat, "thumbnail"=crop
    
    Returns:
        PIL Image object (resized)
    """
    ow, oh = img.size
    
    if scale:
        return img.resize((int(ow * scale), int(oh * scale)), Image.LANCZOS)
    
    if max_w or max_h:
        tw, th = ow, oh
        if max_w and tw > max_w:
            th = int(th * max_w / tw)
            tw = max_w
        if max_h and th > max_h:
            tw = int(tw * max_h / th)
            th = max_h
        return img.resize((tw, th), Image.LANCZOS)
    
    if width and height:
        if mode == "exact":
            return img.resize((width, height), Image.LANCZOS)
        if mode == "thumbnail":
            return ImageOps.fit(img, (width, height), Image.LANCZOS)
        r = min(width / ow, height / oh)
        return img.resize((int(ow * r), int(oh * r)), Image.LANCZOS)
    
    if width:
        return img.resize((width, int(oh * width / ow)), Image.LANCZOS)
    
    if height:
        return img.resize((int(ow * height / oh), height), Image.LANCZOS)
    
    return img


def do_crop(
    img: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int
) -> Image.Image:
    """
    Crop gambar ke region tertentu.
    
    Args:
        img: PIL Image object
        x: Posisi X kiri atas crop
        y: Posisi Y kiri atas crop
        width: Lebar area crop
        height: Tinggi area crop
    
    Returns:
        PIL Image object (cropped)
    
    Raises:
        ValueError: Jika region crop di luar batas gambar
    """
    iw, ih = img.size
    
    # Clamp values to image bounds
    x = max(0, min(x, iw))
    y = max(0, min(y, ih))
    right = max(0, min(x + width, iw))
    bottom = max(0, min(y + height, ih))
    
    if right <= x or bottom <= y:
        raise ValueError(f"Invalid crop region: ({x}, {y}, {right}, {bottom})")
    
    return img.crop((x, y, right, bottom))


def do_center_crop(
    img: Image.Image,
    width: int,
    height: int,
    anchor: str = "center"
) -> Image.Image:
    """
    Crop gambar ke ukuran tertentu dari posisi anchor.
    
    Args:
        img: PIL Image object
        width: Lebar area crop
        height: Tinggi area crop
        anchor: Posisi anchor ("center" atau "top-left")
    
    Returns:
        PIL Image object (cropped)
    
    Raises:
        ValueError: Jika ukuran crop lebih besar dari gambar
    """
    iw, ih = img.size
    
    # Clamp to image size
    width = min(width, iw)
    height = min(height, ih)
    
    anchor = (anchor or "center").lower()
    if anchor == "top-left":
        x, y = 0, 0
    elif anchor == "top-right":
        x, y = max(0, iw - width), 0
    elif anchor == "bottom-left":
        x, y = 0, max(0, ih - height)
    elif anchor == "bottom-right":
        x, y = max(0, iw - width), max(0, ih - height)
    elif anchor == "top-center":
        x, y = max(0, (iw - width) // 2), 0
    elif anchor == "bottom-center":
        x, y = max(0, (iw - width) // 2), max(0, ih - height)
    else:  # center
        x = max(0, (iw - width) // 2)
        y = max(0, (ih - height) // 2)
    
    return img.crop((x, y, x + width, y + height))


def composite_folder_images(images: list[Image.Image], layout: str = "vertical") -> Image.Image:
    """
    Combine multiple PIL Image layers into a single merged image file.

    Args:
        images: List of PIL Image objects
        layout: "vertical", "horizontal", "grid", or "overlay"

    Returns:
        Merged PIL Image object
    """
    if not images:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    if len(images) == 1:
        return images[0].copy()

    # Convert all images to RGBA for consistent compositing
    rgba_imgs = [img.convert("RGBA") for img in images]
    max_w = max(img.width for img in rgba_imgs)
    max_h = max(img.height for img in rgba_imgs)

    layout = (layout or "vertical").lower()

    if layout == "horizontal":
        total_w = sum(img.width for img in rgba_imgs)
        canvas = Image.new("RGBA", (total_w, max_h), (0, 0, 0, 0))
        cur_x = 0
        for img in rgba_imgs:
            y_off = (max_h - img.height) // 2
            canvas.alpha_composite(img, (cur_x, y_off))
            cur_x += img.width
        return canvas

    elif layout == "grid":
        import math
        n = len(rgba_imgs)
        cols = int(math.ceil(math.sqrt(n)))
        rows = int(math.ceil(n / cols))
        canvas = Image.new("RGBA", (cols * max_w, rows * max_h), (0, 0, 0, 0))
        for idx, img in enumerate(rgba_imgs):
            c = idx % cols
            r = idx // cols
            x_off = c * max_w + (max_w - img.width) // 2
            y_off = r * max_h + (max_h - img.height) // 2
            canvas.alpha_composite(img, (x_off, y_off))
        return canvas

    elif layout == "overlay":
        canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
        for img in rgba_imgs:
            x_off = (max_w - img.width) // 2
            y_off = (max_h - img.height) // 2
            canvas.alpha_composite(img, (x_off, y_off))
        return canvas

    else:  # "vertical"
        total_h = sum(img.height for img in rgba_imgs)
        canvas = Image.new("RGBA", (max_w, total_h), (0, 0, 0, 0))
        cur_y = 0
        for img in rgba_imgs:
            x_off = (max_w - img.width) // 2
            canvas.alpha_composite(img, (cur_y, x_off) if False else (x_off, cur_y))
            cur_y += img.height
        return canvas

