"""
Aplikasi utama GUI untuk Image Resolver.
Mendukung English dan Bahasa Indonesia.
"""

import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from src.constants import OUTPUT_FORMATS, EXT_MAP, INPUT_EXTS
from src.image_processor import open_image, save_image, do_resize, do_crop
from src.ui_components import Tooltip, int_or_none, float_or_none, filetypes_input
from src.localization import get_i18n, set_language

# Resolve project root for resource paths (Fix 6)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class App(tk.Tk):
    """Aplikasi GUI utama untuk konversi dan resize gambar."""
    
    def __init__(self):
        super().__init__()
        self.i18n = get_i18n()
        self.title(self.i18n("title"))
        self.resizable(False, False)
        self._set_icon()
        self._build_menu()
        self._build_ui()
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w  = self.winfo_width()
        h  = self.winfo_height()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _set_icon(self):
        """Set icon aplikasi jika monolight.png tersedia."""
        try:
            icon_path = _PROJECT_ROOT / "monolight.png"
            self.iconphoto(True, ImageTk.PhotoImage(Image.open(icon_path)))
        except Exception:
            pass

    def _build_menu(self):
        """Build menu bar dengan language selector."""
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)
        
        lang_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Language", menu=lang_menu)
        lang_menu.add_command(label="English", command=lambda: self._change_language("en"))
        lang_menu.add_command(label="Bahasa Indonesia", command=lambda: self._change_language("id"))

    def _change_language(self, lang: str):
        """Ubah bahasa dan refresh UI."""
        set_language(lang)
        self.i18n = get_i18n()
        self._rebuild_ui()

    def _rebuild_ui(self):
        """Rebuild UI dengan bahasa baru (Fix 1: also update tab titles, log frame, window title)."""
        self.title(self.i18n("title"))
        
        # Update tab titles
        self.notebook.tab(self.tab_single, text=f"  {self.i18n('tab_convert')}  ")
        self.notebook.tab(self.tab_resize, text=f"  {self.i18n('tab_resize')}  ")
        self.notebook.tab(self.tab_batch, text=f"  {self.i18n('tab_batch')}  ")
        self.notebook.tab(self.tab_crop, text=f"  {self.i18n('tab_crop')}  ")
        
        # Update log frame label
        self.log_frame.config(text=self.i18n("log"))
        
        # Clear and rebuild tab contents
        for tab in self.tab_single, self.tab_resize, self.tab_batch, self.tab_crop:
            for w in tab.winfo_children():
                w.destroy()
        
        PAD = dict(padx=10, pady=4)
        self._build_single(self.tab_single, PAD)
        self._build_resize(self.tab_resize, PAD)
        self._build_batch(self.tab_batch, PAD)
        self._build_crop(self.tab_crop, PAD)

    def _build_ui(self):
        """Build seluruh UI aplikasi."""
        PAD = dict(padx=10, pady=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        self.tab_single = ttk.Frame(self.notebook)
        self.tab_resize = ttk.Frame(self.notebook)
        self.tab_batch  = ttk.Frame(self.notebook)
        self.tab_crop   = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_single, text=f"  {self.i18n('tab_convert')}  ")
        self.notebook.add(self.tab_resize, text=f"  {self.i18n('tab_resize')}  ")
        self.notebook.add(self.tab_batch,  text=f"  {self.i18n('tab_batch')}  ")
        self.notebook.add(self.tab_crop,   text=f"  {self.i18n('tab_crop')}  ")

        self._build_single(self.tab_single, PAD)
        self._build_resize(self.tab_resize, PAD)
        self._build_batch(self.tab_batch, PAD)
        self._build_crop(self.tab_crop, PAD)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=10, pady=(8, 0))

        # Log area
        self.log_frame = ttk.LabelFrame(self, text=self.i18n("log"), padding=6)
        self.log_frame.pack(fill="both", padx=10, pady=(4, 4))

        self.log = tk.Text(
            self.log_frame, height=6, font=("Courier New", 9),
            state="disabled", wrap="word",
            background="#f8f8f8", relief="flat"
        )
        scroll = ttk.Scrollbar(self.log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)

        self.log.tag_config("ok",  foreground="#1D9E75")
        self.log.tag_config("err", foreground="#E24B4A")
        self.log.tag_config("inf", foreground="#185FA5")

        # Progress bar frame dengan label persentase
        prog_frame = ttk.Frame(self)
        prog_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.progress = ttk.Progressbar(prog_frame, mode="determinate", maximum=100, length=400)
        self.progress.pack(fill="x", side="left", expand=True)
        self.progress_label = ttk.Label(prog_frame, text="0%", width=5)
        self.progress_label.pack(side="left", padx=(4, 0))

    def _build_single(self, parent, PAD):
        """Build tab Konversi."""
        self.s_src  = tk.StringVar()
        self.s_dst  = tk.StringVar()
        self.s_fmt  = tk.StringVar(value="PNG")
        self.s_qual = tk.IntVar(value=85)
        self.s_w    = tk.StringVar()
        self.s_h    = tk.StringVar()
        self.s_mode = tk.StringVar(value=self.i18n("resize_fit"))

        f = ttk.Frame(parent, padding=8)
        f.pack(fill="both", expand=True)

        self._row(f, 0, self.i18n("file_input"), self.s_src,
                  lambda: self._pick_src(self.s_src, self.s_dst, self.s_fmt))
        self._row(f, 1, self.i18n("file_output"), self.s_dst,
                  lambda: self._save_as(self.s_dst, self.s_fmt))

        ttk.Separator(f, orient="h").grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)

        # Format output
        ttk.Label(f, text=self.i18n("format_output")).grid(row=3, column=0, sticky="w", **PAD)
        cb = ttk.Combobox(f, textvariable=self.s_fmt, values=OUTPUT_FORMATS,
                          state="readonly", width=12)
        cb.grid(row=3, column=1, sticky="w", **PAD)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_dst_ext(self.s_dst, self.s_fmt))

        # Kualitas
        ttk.Label(f, text=self.i18n("quality")).grid(row=4, column=0, sticky="w", **PAD)
        qf = ttk.Frame(f)
        qf.grid(row=4, column=1, columnspan=2, sticky="ew", **PAD)
        ttk.Scale(qf, from_=1, to=100, variable=self.s_qual, orient="horizontal", length=200,
                  command=lambda v: self.s_qual.set(int(float(v)))).pack(side="left")
        ttk.Label(qf, textvariable=self.s_qual, width=3).pack(side="left", padx=4)
        Tooltip(qf, self.i18n("tooltip_quality"))

        ttk.Separator(f, orient="h").grid(row=5, column=0, columnspan=3, sticky="ew", pady=6)
        ttk.Label(f, text=self.i18n("resize_optional"), font=("Segoe UI", 9, "bold")
                  ).grid(row=6, column=0, columnspan=3, sticky="w", **PAD)

        ttk.Label(f, text=self.i18n("width_px")).grid(row=7, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.s_w, width=12).grid(row=7, column=1, sticky="w", **PAD)
        ttk.Label(f, text=self.i18n("height_px")).grid(row=8, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.s_h, width=12).grid(row=8, column=1, sticky="w", **PAD)

        ttk.Label(f, text=self.i18n("mode_resize")).grid(row=9, column=0, sticky="w", **PAD)
        ttk.Combobox(f, textvariable=self.s_mode, state="readonly", width=20,
                     values=[self.i18n("resize_fit"), self.i18n("resize_exact"),
                             self.i18n("resize_thumbnail"), self.i18n("resize_percent")]
                     ).grid(row=9, column=1, sticky="w", **PAD)

        ttk.Button(f, text=self.i18n("btn_convert_now"), command=self._run_single
                   ).grid(row=10, column=0, columnspan=3, pady=(10, 4), ipadx=20)
        f.columnconfigure(1, weight=1)

    def _build_resize(self, parent, PAD):
        """Build tab Resize."""
        self.r_src   = tk.StringVar()
        self.r_dst   = tk.StringVar()
        self.r_w     = tk.StringVar()
        self.r_h     = tk.StringVar()
        self.r_scale = tk.StringVar()
        self.r_maxw  = tk.StringVar()
        self.r_maxh  = tk.StringVar()
        self.r_mode  = tk.StringVar(value=self.i18n("resize_fit"))
        self.r_qual  = tk.IntVar(value=90)

        f = ttk.Frame(parent, padding=8)
        f.pack(fill="both", expand=True)

        self._row(f, 0, self.i18n("file_input"), self.r_src,
                  lambda: self._pick_src(self.r_src, self.r_dst, None))
        self._row(f, 1, self.i18n("file_output"), self.r_dst,
                  lambda: self._save_as(self.r_dst, None))

        ttk.Separator(f, orient="h").grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)

        # Resize parameters
        for row, key_lbl, var, key_tip in [
            (3, "width_px",  self.r_w,    "tooltip_width"),
            (4, "height_px", self.r_h,    "tooltip_height"),
            (5, "scale_percent",   self.r_scale,"tooltip_scale"),
            (6, "max_width",  self.r_maxw, "tooltip_max_w"),
            (7, "max_height", self.r_maxh, "tooltip_max_h"),
        ]:
            ttk.Label(f, text=self.i18n(key_lbl)).grid(row=row, column=0, sticky="w", **PAD)
            e = ttk.Entry(f, textvariable=var, width=12)
            e.grid(row=row, column=1, sticky="w", **PAD)
            Tooltip(e, self.i18n(key_tip))

        ttk.Label(f, text=self.i18n("mode")).grid(row=8, column=0, sticky="w", **PAD)
        ttk.Combobox(f, textvariable=self.r_mode, state="readonly", width=20,
                     values=[self.i18n("resize_fit"), self.i18n("resize_exact"), 
                             self.i18n("resize_thumbnail")]
                     ).grid(row=8, column=1, sticky="w", **PAD)

        # Kualitas
        ttk.Label(f, text=self.i18n("quality")).grid(row=9, column=0, sticky="w", **PAD)
        qf = ttk.Frame(f)
        qf.grid(row=9, column=1, sticky="ew", **PAD)
        ttk.Scale(qf, from_=1, to=100, variable=self.r_qual, orient="horizontal", length=180,
                  command=lambda v: self.r_qual.set(int(float(v)))).pack(side="left")
        ttk.Label(qf, textvariable=self.r_qual, width=3).pack(side="left", padx=4)

        ttk.Button(f, text=self.i18n("btn_resize_now"), command=self._run_resize
                   ).grid(row=10, column=0, columnspan=3, pady=(10, 4), ipadx=20)
        f.columnconfigure(1, weight=1)

    def _build_batch(self, parent, PAD):
        """Build tab Batch."""
        self.b_indir  = tk.StringVar()
        self.b_outdir = tk.StringVar()
        self.b_fmt    = tk.StringVar(value="PNG")
        self.b_qual   = tk.IntVar(value=85)
        self.b_w      = tk.StringVar()
        self.b_h      = tk.StringVar()
        self.b_scale  = tk.StringVar()
        self.b_rec    = tk.BooleanVar(value=False)

        f = ttk.Frame(parent, padding=8)
        f.pack(fill="both", expand=True)

        # Input/output directories
        ttk.Label(f, text=self.i18n("folder_input")).grid(row=0, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.b_indir, width=30).grid(row=0, column=1, sticky="ew", **PAD)
        ttk.Button(f, text=self.i18n("select_btn"),
                   command=lambda: self.b_indir.set(filedialog.askdirectory() or self.b_indir.get())
                   ).grid(row=0, column=2, **PAD)

        ttk.Label(f, text=self.i18n("folder_output")).grid(row=1, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.b_outdir, width=30).grid(row=1, column=1, sticky="ew", **PAD)
        ttk.Button(f, text=self.i18n("select_btn"),
                   command=lambda: self.b_outdir.set(filedialog.askdirectory() or self.b_outdir.get())
                   ).grid(row=1, column=2, **PAD)

        ttk.Separator(f, orient="h").grid(row=2, column=0, columnspan=3, sticky="ew", pady=6)

        # Format dan kualitas
        ttk.Label(f, text=self.i18n("format_output")).grid(row=3, column=0, sticky="w", **PAD)
        ttk.Combobox(f, textvariable=self.b_fmt, values=OUTPUT_FORMATS,
                     state="readonly", width=12).grid(row=3, column=1, sticky="w", **PAD)

        ttk.Label(f, text=self.i18n("quality")).grid(row=4, column=0, sticky="w", **PAD)
        qf = ttk.Frame(f)
        qf.grid(row=4, column=1, sticky="ew", **PAD)
        ttk.Scale(qf, from_=1, to=100, variable=self.b_qual, orient="horizontal", length=180,
                  command=lambda v: self.b_qual.set(int(float(v)))).pack(side="left")
        ttk.Label(qf, textvariable=self.b_qual, width=3).pack(side="left", padx=4)

        ttk.Separator(f, orient="h").grid(row=5, column=0, columnspan=3, sticky="ew", pady=6)

        # Resize parameters
        ttk.Label(f, text=self.i18n("width_px")).grid(row=6, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.b_w, width=12).grid(row=6, column=1, sticky="w", **PAD)
        ttk.Label(f, text=self.i18n("height_px")).grid(row=7, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.b_h, width=12).grid(row=7, column=1, sticky="w", **PAD)
        ttk.Label(f, text=self.i18n("scale_percent")).grid(row=8, column=0, sticky="w", **PAD)
        ttk.Entry(f, textvariable=self.b_scale, width=12).grid(row=8, column=1, sticky="w", **PAD)

        # Recursive option
        ttk.Checkbutton(f, text=self.i18n("recursive"), variable=self.b_rec
                        ).grid(row=9, column=0, columnspan=3, sticky="w", **PAD)

        ttk.Button(f, text=self.i18n("btn_batch_start"), command=self._run_batch
                   ).grid(row=10, column=0, columnspan=3, pady=(10, 4), ipadx=20)
        f.columnconfigure(1, weight=1)

    def _build_crop(self, parent, PAD):
        """Build tab Crop with interactive canvas-based cropping."""
        self.c_src  = tk.StringVar()
        self.c_dst  = tk.StringVar()
        self.c_fmt  = tk.StringVar(value="PNG")
        self.c_qual = tk.IntVar(value=95)
        self.c_x    = tk.StringVar(value="0")
        self.c_y    = tk.StringVar(value="0")
        self.c_w    = tk.StringVar(value="0")
        self.c_h    = tk.StringVar(value="0")
        self.c_aspect = tk.StringVar(value=self.i18n("crop_aspect_free"))

        # Internal crop state
        self._crop_img = None        # Original PIL Image
        self._crop_preview = None    # Resized preview PIL Image
        self._crop_tk = None         # ImageTk for canvas
        self._crop_scale = 1.0       # Preview scale factor
        self._crop_rect_id = None    # Canvas rectangle item id
        self._crop_handles = []      # Canvas handle item ids
        self._crop_drag_start = None # (x, y) drag start point
        self._crop_drag_mode = None  # "draw", "move", or "resize_XX"
        self._crop_active_handle = None
        self._updating_fields = False  # Prevent recursive updates

        # Canvas dimensions
        self._canvas_w = 450
        self._canvas_h = 320

        f = ttk.Frame(parent, padding=8)
        f.pack(fill="both", expand=True)

        # Row 0: Input file
        self._row(f, 0, self.i18n("file_input"), self.c_src,
                  lambda: self._crop_pick_src())

        ttk.Separator(f, orient="h").grid(row=1, column=0, columnspan=3, sticky="ew", pady=6)

        # Row 2: Preview canvas + controls side panel
        preview_frame = ttk.Frame(f)
        preview_frame.grid(row=2, column=0, columnspan=3, sticky="nsew", **PAD)

        # Canvas for image preview
        canvas_frame = ttk.LabelFrame(preview_frame, text="Preview", padding=2)
        canvas_frame.pack(side="left", fill="both", expand=True)

        self.crop_canvas = tk.Canvas(
            canvas_frame, width=self._canvas_w, height=self._canvas_h,
            background="#e0e0e0", cursor="crosshair", relief="sunken", bd=1
        )
        self.crop_canvas.pack(fill="both", expand=True)

        # Hint label
        self._crop_hint_id = self.crop_canvas.create_text(
            self._canvas_w // 2, self._canvas_h // 2,
            text=self.i18n("crop_no_image"),
            fill="#999999", font=("Segoe UI", 11)
        )

        # Bind mouse events
        self.crop_canvas.bind("<ButtonPress-1>", self._crop_on_press)
        self.crop_canvas.bind("<B1-Motion>", self._crop_on_drag)
        self.crop_canvas.bind("<ButtonRelease-1>", self._crop_on_release)

        # Side panel for crop parameters
        side = ttk.Frame(preview_frame, padding=(10, 0, 0, 0))
        side.pack(side="left", fill="y")

        # Crop coordinate fields
        for i, (key_lbl, var) in enumerate([
            ("crop_x", self.c_x),
            ("crop_y", self.c_y),
            ("crop_width", self.c_w),
            ("crop_height", self.c_h),
        ]):
            ttk.Label(side, text=self.i18n(key_lbl)).grid(row=i, column=0, sticky="w", pady=2)
            e = ttk.Entry(side, textvariable=var, width=8)
            e.grid(row=i, column=1, sticky="w", padx=(4, 0), pady=2)
            var.trace_add("write", self._crop_fields_changed)

        ttk.Separator(side, orient="h").grid(row=4, column=0, columnspan=2, sticky="ew", pady=6)

        # Aspect ratio selector
        ttk.Label(side, text=self.i18n("crop_aspect_label")).grid(row=5, column=0, sticky="w", pady=2)
        ttk.Combobox(side, textvariable=self.c_aspect, state="readonly", width=8,
                     values=[self.i18n("crop_aspect_free"), "1:1", "4:3", "3:2", "16:9", "9:16", "3:4", "2:3"]
                     ).grid(row=5, column=1, sticky="w", padx=(4, 0), pady=2)

        ttk.Separator(side, orient="h").grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)

        # Format output
        ttk.Label(side, text=self.i18n("format_output")).grid(row=7, column=0, sticky="w", pady=2)
        cb = ttk.Combobox(side, textvariable=self.c_fmt, values=OUTPUT_FORMATS,
                          state="readonly", width=8)
        cb.grid(row=7, column=1, sticky="w", padx=(4, 0), pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_dst_ext(self.c_dst, self.c_fmt))

        # Quality
        ttk.Label(side, text=self.i18n("quality")).grid(row=8, column=0, sticky="w", pady=2)
        qf = ttk.Frame(side)
        qf.grid(row=8, column=1, sticky="w", padx=(4, 0), pady=2)
        ttk.Scale(qf, from_=1, to=100, variable=self.c_qual, orient="horizontal", length=80,
                  command=lambda v: self.c_qual.set(int(float(v)))).pack(side="left")
        ttk.Label(qf, textvariable=self.c_qual, width=3).pack(side="left")

        # Hint text
        ttk.Label(side, text=self.i18n("crop_preview_hint"),
                  wraplength=160, font=("Segoe UI", 8), foreground="#888"
                  ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Separator(f, orient="h").grid(row=3, column=0, columnspan=3, sticky="ew", pady=6)

        # Row 4: Output file
        self._row(f, 4, self.i18n("file_output"), self.c_dst,
                  lambda: self._save_as(self.c_dst, self.c_fmt))

        # Row 5: Crop button
        ttk.Button(f, text=self.i18n("btn_crop_now"), command=self._run_crop
                   ).grid(row=5, column=0, columnspan=3, pady=(10, 4), ipadx=20)
        f.columnconfigure(1, weight=1)

    # ── Crop Canvas Helpers ──────────────────────────────────────

    def _crop_pick_src(self):
        """Pick source file and load preview into canvas."""
        path = filedialog.askopenfilename(filetypes=filetypes_input(self.i18n))
        if not path:
            return
        self.c_src.set(path)
        # Auto-generate output path
        p = Path(path)
        ext = EXT_MAP.get(self.c_fmt.get(), ".png")
        self.c_dst.set(str(p.parent / (p.stem + "_cropped" + ext)))
        # Load preview
        self._crop_load_preview(path)

    def _crop_load_preview(self, path):
        """Load image into canvas preview, scaled to fit."""
        try:
            src_path = Path(path)
            is_svg = src_path.suffix.lower() == ".svg"
            if is_svg:
                self._crop_img = open_image(src_path)
            else:
                self._crop_img = open_image(src_path)
            
            iw, ih = self._crop_img.size
            # Calculate scale to fit canvas
            scale_w = self._canvas_w / iw
            scale_h = self._canvas_h / ih
            self._crop_scale = min(scale_w, scale_h, 1.0)  # Don't upscale
            
            pw = max(1, int(iw * self._crop_scale))
            ph = max(1, int(ih * self._crop_scale))
            self._crop_preview = self._crop_img.resize((pw, ph), Image.LANCZOS)
            self._crop_tk = ImageTk.PhotoImage(self._crop_preview)
            
            # Clear canvas and draw image
            self.crop_canvas.delete("all")
            # Center image on canvas
            cx = self._canvas_w // 2
            cy = self._canvas_h // 2
            self.crop_canvas.create_image(cx, cy, image=self._crop_tk, anchor="center", tags="img")
            
            # Store image offset on canvas (for coordinate mapping)
            self._img_offset_x = cx - pw // 2
            self._img_offset_y = cy - ph // 2
            
            # Initialize crop to full image
            self.c_x.set("0")
            self.c_y.set("0")
            self.c_w.set(str(iw))
            self.c_h.set(str(ih))
            
            self._crop_draw_rect()
            
        except Exception as e:
            self._log(f"{self.i18n('log_error')}  {e}", "err")

    def _crop_draw_rect(self):
        """Draw crop rectangle on canvas based on current field values."""
        if self._crop_img is None:
            return
        
        # Remove old rectangle and handles
        if self._crop_rect_id:
            self.crop_canvas.delete(self._crop_rect_id)
        for h in self._crop_handles:
            self.crop_canvas.delete(h)
        self._crop_handles.clear()
        
        # Get crop values in original image pixels
        cx = int_or_none(self.c_x.get()) or 0
        cy = int_or_none(self.c_y.get()) or 0
        cw = int_or_none(self.c_w.get()) or 0
        ch = int_or_none(self.c_h.get()) or 0
        
        if cw <= 0 or ch <= 0:
            return
        
        # Convert to canvas coordinates
        x1 = self._img_offset_x + cx * self._crop_scale
        y1 = self._img_offset_y + cy * self._crop_scale
        x2 = self._img_offset_x + (cx + cw) * self._crop_scale
        y2 = self._img_offset_y + (cy + ch) * self._crop_scale
        
        # Draw semi-transparent overlay (darken outside crop)
        # Draw rectangle outline
        self._crop_rect_id = self.crop_canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#00AAFF", width=2, dash=(4, 2), tags="crop_rect"
        )
        
        # Draw resize handles at corners and midpoints
        handle_size = 5
        handle_positions = [
            ("nw", x1, y1), ("n", (x1+x2)/2, y1), ("ne", x2, y1),
            ("w",  x1, (y1+y2)/2),                  ("e",  x2, (y1+y2)/2),
            ("sw", x1, y2), ("s", (x1+x2)/2, y2), ("se", x2, y2),
        ]
        for name, hx, hy in handle_positions:
            hid = self.crop_canvas.create_rectangle(
                hx - handle_size, hy - handle_size,
                hx + handle_size, hy + handle_size,
                fill="#00AAFF", outline="#FFFFFF", width=1,
                tags=f"handle_{name}"
            )
            self._crop_handles.append(hid)

    def _canvas_to_image(self, cx, cy):
        """Convert canvas coordinates to original image pixel coordinates."""
        if self._crop_scale == 0:
            return 0, 0
        ix = (cx - self._img_offset_x) / self._crop_scale
        iy = (cy - self._img_offset_y) / self._crop_scale
        return ix, iy

    def _get_handle_at(self, cx, cy):
        """Check if canvas position is over a resize handle. Returns handle name or None."""
        items = self.crop_canvas.find_overlapping(cx - 6, cy - 6, cx + 6, cy + 6)
        for item in items:
            tags = self.crop_canvas.gettags(item)
            for tag in tags:
                if tag.startswith("handle_"):
                    return tag.replace("handle_", "")
        return None

    def _is_inside_rect(self, cx, cy):
        """Check if canvas position is inside the crop rectangle."""
        if not self._crop_rect_id:
            return False
        coords = self.crop_canvas.coords(self._crop_rect_id)
        if len(coords) < 4:
            return False
        x1, y1, x2, y2 = coords
        return x1 <= cx <= x2 and y1 <= cy <= y2

    def _crop_on_press(self, event):
        """Handle mouse press on crop canvas."""
        if self._crop_img is None:
            return
        
        cx, cy = event.x, event.y
        
        # Check if pressing a handle
        handle = self._get_handle_at(cx, cy)
        if handle:
            self._crop_drag_mode = f"resize_{handle}"
            self._crop_drag_start = (cx, cy)
            self._crop_active_handle = handle
            return
        
        # Check if pressing inside rect (move mode)
        if self._is_inside_rect(cx, cy):
            self._crop_drag_mode = "move"
            self._crop_drag_start = (cx, cy)
            return
        
        # Otherwise, start drawing new rect
        self._crop_drag_mode = "draw"
        self._crop_drag_start = (cx, cy)

    def _crop_on_drag(self, event):
        """Handle mouse drag on crop canvas."""
        if self._crop_img is None or self._crop_drag_start is None:
            return
        
        cx, cy = event.x, event.y
        sx, sy = self._crop_drag_start
        iw, ih = self._crop_img.size
        
        if self._crop_drag_mode == "draw":
            # Convert both points to image coordinates
            ix1, iy1 = self._canvas_to_image(sx, sy)
            ix2, iy2 = self._canvas_to_image(cx, cy)
            
            # Clamp to image bounds
            ix1 = max(0, min(ix1, iw))
            iy1 = max(0, min(iy1, ih))
            ix2 = max(0, min(ix2, iw))
            iy2 = max(0, min(iy2, ih))
            
            # Normalize
            x = int(min(ix1, ix2))
            y = int(min(iy1, iy2))
            w = int(abs(ix2 - ix1))
            h = int(abs(iy2 - iy1))
            
            # Apply aspect ratio constraint
            w, h = self._apply_aspect_ratio(w, h)
            
            self._updating_fields = True
            self.c_x.set(str(x))
            self.c_y.set(str(y))
            self.c_w.set(str(w))
            self.c_h.set(str(h))
            self._updating_fields = False
            self._crop_draw_rect()
        
        elif self._crop_drag_mode == "move":
            # Move rectangle
            dx_canvas = cx - sx
            dy_canvas = cy - sy
            dx_img = dx_canvas / self._crop_scale
            dy_img = dy_canvas / self._crop_scale
            
            old_x = int_or_none(self.c_x.get()) or 0
            old_y = int_or_none(self.c_y.get()) or 0
            cw = int_or_none(self.c_w.get()) or 0
            ch = int_or_none(self.c_h.get()) or 0
            
            new_x = max(0, min(int(old_x + dx_img), iw - cw))
            new_y = max(0, min(int(old_y + dy_img), ih - ch))
            
            self._updating_fields = True
            self.c_x.set(str(new_x))
            self.c_y.set(str(new_y))
            self._updating_fields = False
            self._crop_draw_rect()
            self._crop_drag_start = (cx, cy)
        
        elif self._crop_drag_mode and self._crop_drag_mode.startswith("resize_"):
            self._crop_handle_resize(cx, cy)
            self._crop_drag_start = (cx, cy)

    def _crop_on_release(self, event):
        """Handle mouse release on crop canvas."""
        self._crop_drag_mode = None
        self._crop_drag_start = None
        self._crop_active_handle = None

    def _crop_handle_resize(self, cx, cy):
        """Resize crop rectangle by dragging a handle."""
        if self._crop_img is None:
            return
        
        iw, ih = self._crop_img.size
        handle = self._crop_active_handle
        ix, iy = self._canvas_to_image(cx, cy)
        
        # Clamp to image bounds
        ix = max(0, min(ix, iw))
        iy = max(0, min(iy, ih))
        
        old_x = int_or_none(self.c_x.get()) or 0
        old_y = int_or_none(self.c_y.get()) or 0
        old_w = int_or_none(self.c_w.get()) or 0
        old_h = int_or_none(self.c_h.get()) or 0
        old_r = old_x + old_w
        old_b = old_y + old_h
        
        new_x, new_y = old_x, old_y
        new_r, new_b = old_r, old_b
        
        # Adjust edges based on which handle is being dragged
        if "w" in handle and handle != "sw" and handle != "nw" or handle == "w":
            pass
        if handle in ("nw", "w", "sw"):
            new_x = int(ix)
        if handle in ("ne", "e", "se"):
            new_r = int(ix)
        if handle in ("nw", "n", "ne"):
            new_y = int(iy)
        if handle in ("sw", "s", "se"):
            new_b = int(iy)
        
        # Ensure minimum size
        new_w = max(1, new_r - new_x)
        new_h = max(1, new_b - new_y)
        new_x = max(0, min(new_x, iw - 1))
        new_y = max(0, min(new_y, ih - 1))
        
        # Apply aspect ratio constraint
        new_w, new_h = self._apply_aspect_ratio(new_w, new_h)
        
        self._updating_fields = True
        self.c_x.set(str(new_x))
        self.c_y.set(str(new_y))
        self.c_w.set(str(new_w))
        self.c_h.set(str(new_h))
        self._updating_fields = False
        self._crop_draw_rect()

    def _apply_aspect_ratio(self, w, h):
        """Apply aspect ratio constraint if one is selected."""
        aspect_val = self.c_aspect.get()
        free_label = self.i18n("crop_aspect_free")
        if aspect_val == free_label or ":" not in aspect_val:
            return w, h
        
        try:
            aw, ah = aspect_val.split(":")
            ratio = float(aw) / float(ah)
        except (ValueError, ZeroDivisionError):
            return w, h
        
        # Adjust height to match aspect ratio, keeping width
        new_h = int(w / ratio)
        if new_h < 1:
            new_h = 1
            w = int(new_h * ratio)
        return w, new_h

    def _crop_fields_changed(self, *args):
        """Called when crop coordinate fields are manually edited."""
        if self._updating_fields or self._crop_img is None:
            return
        self._crop_draw_rect()

    # ── Shared UI Helpers ────────────────────────────────────────

    def _row(self, parent, row, label, var, cmd):
        """Helper untuk membuat row dengan label, entry, dan button."""
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=10, pady=4)
        ttk.Entry(parent, textvariable=var, width=32).grid(row=row, column=1,
                                                            sticky="ew", padx=4, pady=4)
        ttk.Button(parent, text=self.i18n("select_btn"), command=cmd, width=8).grid(row=row, column=2,
                                                                         padx=4, pady=4)

    def _update_dst_ext(self, dst_var, fmt_var):
        """Update ekstensi file output sesuai format."""
        dst = dst_var.get()
        if dst:
            new_ext = EXT_MAP.get(fmt_var.get(), Path(dst).suffix)
            dst_var.set(str(Path(dst).with_suffix(new_ext)))

    def _pick_src(self, src_var, dst_var, fmt_var):
        """Pick file input dan auto-generate output path."""
        path = filedialog.askopenfilename(filetypes=filetypes_input(self.i18n))
        if not path:
            return
        src_var.set(path)
        if dst_var and fmt_var:
            p = Path(path)
            ext = EXT_MAP.get(fmt_var.get(), ".png")
            dst_var.set(str(p.parent / (p.stem + "_result" + ext)))
        elif dst_var:
            p = Path(path)
            dst_var.set(str(p.parent / (p.stem + "_resized" + p.suffix)))

    def _save_as(self, dst_var, fmt_var):
        """Save as dialog untuk memilih path output."""
        fmt = fmt_var.get() if fmt_var else None
        lbl_all = self.i18n("all_files")
        if fmt:
            ext = EXT_MAP.get(fmt, ".png")
            filetypes = [(fmt, f"*{ext}"), (lbl_all, "*.*")]
            defext = ext
        else:
            lbl_images = self.i18n("all_images")
            filetypes = [(lbl_images, " ".join(f"*{e}" for e in sorted(EXT_MAP.values()))),
                         (lbl_all, "*.*")]
            defext = ".png"
        path = filedialog.asksaveasfilename(filetypes=filetypes, defaultextension=defext)
        if path:
            dst_var.set(path)

    def _log(self, msg: str, tag: str = ""):
        """Tulis pesan ke log widget."""
        def _write():
            self.log.configure(state="normal")
            self.log.insert("end", msg + "\n", tag)
            self.log.see("end")
            self.log.configure(state="disabled")
        self.after(0, _write)

    def _update_progress(self, value: int):
        """Update progress bar ke nilai tertentu (0-100)."""
        def _update():
            self.progress["value"] = value
            self.progress_label.config(text=f"{value}%")
            self.update_idletasks()
        self.after(0, _update)

    def _set_progress(self, running: bool):
        """Set progress bar running atau stopped."""
        def _toggle():
            if running:
                self._update_progress(0)
            else:
                self._update_progress(100)
                self.after(500, lambda: self._update_progress(0))
        self.after(0, _toggle)

    @staticmethod
    def _mode_str(mode_label: str) -> str:
        """Convert mode label ke mode string untuk processing. (Fix 2: fixed duplicate + added percent)"""
        mode_map = {
            # English
            "Proportional (fit)": "fit",
            "Exact": "exact",
            "Thumbnail (crop)": "thumbnail",
            "Percentage (%)": "percent",
            # Indonesian
            "Proporsional (fit)": "fit",
            "Tepat (exact)": "exact",
            "Thumbnail (crop)": "thumbnail",
            "Persentase (%)": "percent",
            # Internal keys
            "fit": "fit",
            "exact": "exact",
            "thumbnail": "thumbnail",
            "percent": "percent",
        }
        return mode_map.get(mode_label, "fit")

    def _run_single(self):
        """Runner untuk konversi satu file."""
        src = self.s_src.get().strip()
        dst = self.s_dst.get().strip()
        if not src or not dst:
            messagebox.showwarning(self.i18n("error_input_missing"), 
                                  self.i18n("error_select_file"))
            return

        fmt   = self.s_fmt.get()
        qual  = self.s_qual.get()
        w     = int_or_none(self.s_w.get())
        h     = int_or_none(self.s_h.get())
        mode  = self._mode_str(self.s_mode.get())
        scale = None
        # Fix 3: properly handle percent mode
        if mode == "percent":
            scale = float_or_none(self.s_w.get())
            if scale:
                scale = scale / 100
            w = h = None

        def task():
            self._set_progress(True)
            try:
                self._update_progress(10)
                is_svg = Path(src).suffix.lower() == ".svg"
                if is_svg:
                    img = open_image(Path(src), svg_width=w, svg_height=h, svg_scale=scale)
                else:
                    img = open_image(Path(src))
                    self._update_progress(40)
                    if w or h or scale:
                        img = do_resize(img, width=w, height=h, scale=scale, mode=mode)
                self._update_progress(70)
                ext   = EXT_MAP.get(fmt, Path(dst).suffix)
                dst_p = Path(dst).with_suffix(ext)
                save_image(img, dst_p, quality=qual, fmt_override=fmt)
                self._update_progress(100)
                self._log(f"{self.i18n('log_success')}  {Path(src).name}  {self.i18n('log_arrow')}  {dst_p.name}  {img.size}", "ok")
            except Exception as e:
                self._log(f"{self.i18n('log_error')}  {e}", "err")
                traceback.print_exc()
            finally:
                self._set_progress(False)

        threading.Thread(target=task, daemon=True).start()

    def _run_resize(self):
        """Runner untuk resize file."""
        src = self.r_src.get().strip()
        dst = self.r_dst.get().strip()
        if not src or not dst:
            messagebox.showwarning(self.i18n("error_input_missing"), 
                                  self.i18n("error_select_file"))
            return

        w         = int_or_none(self.r_w.get())
        h         = int_or_none(self.r_h.get())
        maxw      = int_or_none(self.r_maxw.get())
        maxh      = int_or_none(self.r_maxh.get())
        scale_pct = float_or_none(self.r_scale.get())
        scale     = (scale_pct / 100) if scale_pct else None
        mode      = self._mode_str(self.r_mode.get())
        qual      = self.r_qual.get()

        def task():
            self._set_progress(True)
            try:
                self._update_progress(10)
                is_svg = Path(src).suffix.lower() == ".svg"
                if is_svg:
                    img = open_image(Path(src), svg_width=w, svg_height=h, svg_scale=scale)
                else:
                    img = open_image(Path(src))
                    self._update_progress(40)
                    img = do_resize(img, width=w, height=h, scale=scale,
                                    max_w=maxw, max_h=maxh, mode=mode)
                self._update_progress(70)
                save_image(img, Path(dst), quality=qual)
                self._update_progress(100)
                self._log(f"{self.i18n('log_success')}  {Path(src).name}  {self.i18n('log_arrow')}  {Path(dst).name}  {img.size}", "ok")
            except Exception as e:
                self._log(f"{self.i18n('log_error')}  {e}", "err")
            finally:
                self._set_progress(False)

        threading.Thread(target=task, daemon=True).start()

    def _run_batch(self):
        """Runner untuk batch konversi."""
        indir  = self.b_indir.get().strip()
        outdir = self.b_outdir.get().strip()
        if not indir or not outdir:
            messagebox.showwarning(self.i18n("error_input_missing"), 
                                  self.i18n("error_select_folder"))
            return

        fmt       = self.b_fmt.get()
        qual      = self.b_qual.get()
        ext_out   = EXT_MAP.get(fmt, ".png")
        w         = int_or_none(self.b_w.get())
        h         = int_or_none(self.b_h.get())
        scale_pct = float_or_none(self.b_scale.get())
        scale     = (scale_pct / 100) if scale_pct else None
        recursive = self.b_rec.get()
        pattern   = "**/*" if recursive else "*"

        def task():
            self._set_progress(True)
            ok_count = err_count = 0
            in_p  = Path(indir)
            out_p = Path(outdir)
            files = [f for f in sorted(in_p.glob(pattern))
                     if f.is_file() and f.suffix.lower() in INPUT_EXTS]
            self._log(f"{self.i18n('log_arrow')}  {len(files)} {self.i18n('info_files_found')} {indir}", "inf")
            total = len(files)
            
            # Fix 4: handle empty folder without ZeroDivisionError
            if total == 0:
                self._log(self.i18n("info_no_files"), "inf")
                self._set_progress(False)
                return
            
            for idx, f in enumerate(files, 1):
                # Fix 7: preserve subfolder structure in recursive mode
                if recursive:
                    rel = f.relative_to(in_p)
                    dst = out_p / rel.parent / (f.stem + ext_out)
                else:
                    dst = out_p / (f.stem + ext_out)
                try:
                    is_svg = f.suffix.lower() == ".svg"
                    if is_svg:
                        img = open_image(f, svg_width=w, svg_height=h, svg_scale=scale)
                    else:
                        img = open_image(f)
                        if w or h or scale:
                            img = do_resize(img, width=w, height=h, scale=scale)
                    save_image(img, dst, quality=qual, fmt_override=fmt)
                    self._log(f"{self.i18n('log_success')}  {f.name}  {self.i18n('log_arrow')}  {dst.name}  {img.size}", "ok")
                    ok_count += 1
                except Exception as e:
                    self._log(f"{self.i18n('log_error')}  {f.name}: {e}", "err")
                    err_count += 1
                progress_pct = int((idx / total) * 100)
                self._update_progress(progress_pct)
            completed_msg = f"{self.i18n('info_completed')} {ok_count} {self.i18n('info_ok')}, {err_count} {self.i18n('info_err')}."
            self._log(completed_msg, "inf")
            self._set_progress(False)

        threading.Thread(target=task, daemon=True).start()

    def _run_crop(self):
        """Runner untuk crop file."""
        src = self.c_src.get().strip()
        dst = self.c_dst.get().strip()
        if not src or not dst:
            messagebox.showwarning(self.i18n("error_input_missing"),
                                  self.i18n("error_select_file"))
            return

        cx = int_or_none(self.c_x.get())
        cy = int_or_none(self.c_y.get())
        cw = int_or_none(self.c_w.get())
        ch = int_or_none(self.c_h.get())
        
        # Allow 0 for x and y offsets
        if cx is None:
            try:
                cx = int(self.c_x.get().strip())
                if cx < 0:
                    cx = None
            except (ValueError, AttributeError):
                cx = None
        if cy is None:
            try:
                cy = int(self.c_y.get().strip())
                if cy < 0:
                    cy = None
            except (ValueError, AttributeError):
                cy = None
        
        if cx is None or cy is None or not cw or not ch:
            messagebox.showwarning(self.i18n("error_input_missing"),
                                  self.i18n("error_crop_region"))
            return

        fmt  = self.c_fmt.get()
        qual = self.c_qual.get()

        def task():
            self._set_progress(True)
            try:
                self._update_progress(10)
                img = open_image(Path(src))
                self._update_progress(30)
                cropped = do_crop(img, cx, cy, cw, ch)
                self._update_progress(60)
                ext   = EXT_MAP.get(fmt, Path(dst).suffix)
                dst_p = Path(dst).with_suffix(ext)
                save_image(cropped, dst_p, quality=qual, fmt_override=fmt)
                self._update_progress(100)
                self._log(
                    f"{self.i18n('log_success')}  {Path(src).name}  {self.i18n('log_arrow')}  "
                    f"{dst_p.name}  crop({cx},{cy},{cw},{ch}) → {cropped.size}", "ok"
                )
            except Exception as e:
                self._log(f"{self.i18n('log_error')}  {e}", "err")
                traceback.print_exc()
            finally:
                self._set_progress(False)

        threading.Thread(target=task, daemon=True).start()
