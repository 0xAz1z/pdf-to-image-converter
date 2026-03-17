"""
PDF to Image Converter — Offline Desktop App
Requirements: pip install pdf2image Pillow
Also needs: poppler-utils (Linux/Mac: brew install poppler | apt install poppler-utils)
             Windows: download poppler from https://github.com/oschwartz10612/poppler-windows/releases
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
from pathlib import Path

# ── Dependency check ────────────────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
    from pdf2image.exceptions import PDFInfoNotInstalledError, PDFPageCountError
    from PIL import Image
except ImportError as e:
    import subprocess
    root = tk.Tk(); root.withdraw()
    messagebox.showerror(
        "Missing Dependencies",
        f"Please install required packages:\n\n  pip install pdf2image Pillow\n\n"
        f"Also install poppler:\n"
        f"  macOS  : brew install poppler\n"
        f"  Linux  : sudo apt install poppler-utils\n"
        f"  Windows: see https://github.com/oschwartz10612/poppler-windows\n\n"
        f"Error: {e}"
    )
    sys.exit(1)


# ── Color palette ────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
SURFACE  = "#2a2a3e"
ACCENT   = "#7c6af7"
ACCENT2  = "#a78bfa"
TEXT     = "#e2e8f0"
SUBTEXT  = "#94a3b8"
SUCCESS  = "#4ade80"
ERROR    = "#f87171"
BORDER   = "#3d3d55"


class PDFConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PDF → Image Converter")
        self.geometry("680x600")
        self.resizable(False, False)
        self.configure(bg=BG)
        self._set_icon()

        self.pdf_path     = tk.StringVar()
        self.output_dir   = tk.StringVar()
        self.fmt          = tk.StringVar(value="PNG")
        self.dpi          = tk.IntVar(value=150)
        self.quality      = tk.IntVar(value=90)
        self.page_range   = tk.StringVar(value="all")
        self.first_page   = tk.StringVar(value="1")
        self.last_page    = tk.StringVar(value="")
        self.grayscale    = tk.BooleanVar(value=False)
        self.transparent  = tk.BooleanVar(value=False)
        self._converting  = False

        self._build_ui()

    # ── Icon (drawn with canvas so no external file needed) ──────────────────
    def _set_icon(self):
        try:
            icon = tk.PhotoImage(width=32, height=32)
            for y in range(32):
                for x in range(32):
                    icon.put("#7c6af7", (x, y))
            self.iconphoto(True, icon)
        except Exception:
            pass

    # ── UI construction ──────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=ACCENT, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="📄  PDF → Image Converter",
                 font=("Segoe UI", 15, "bold"),
                 fg="white", bg=ACCENT).pack(side="left", padx=20)
        tk.Label(hdr, text="Offline • No internet needed",
                 font=("Segoe UI", 9), fg="#d4c8ff", bg=ACCENT).pack(side="right", padx=20)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=16)

        # ── PDF File ──
        self._section(body, "Input PDF File")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(0, 12))
        entry = self._entry(row, self.pdf_path, "Click Browse to select a PDF…")
        entry.pack(side="left", fill="x", expand=True)
        self._btn(row, "Browse", self._browse_pdf, ACCENT).pack(side="left", padx=(8, 0))

        # ── Output Folder ──
        self._section(body, "Output Folder")
        row2 = tk.Frame(body, bg=BG)
        row2.pack(fill="x", pady=(0, 12))
        entry2 = self._entry(row2, self.output_dir, "Same folder as PDF (default)")
        entry2.pack(side="left", fill="x", expand=True)
        self._btn(row2, "Browse", self._browse_dir, ACCENT).pack(side="left", padx=(8, 0))

        # ── Format + DPI ──
        self._section(body, "Settings")
        cfg = tk.Frame(body, bg=BG)
        cfg.pack(fill="x", pady=(0, 8))

        # Format
        fl = tk.Frame(cfg, bg=BG); fl.pack(side="left")
        tk.Label(fl, text="Format", font=("Segoe UI", 9), fg=SUBTEXT, bg=BG).pack(anchor="w")
        fmt_cb = ttk.Combobox(fl, textvariable=self.fmt, width=7,
                              values=["PNG","JPEG","TIFF","BMP","WEBP"],
                              state="readonly", font=("Segoe UI", 10))
        fmt_cb.pack(pady=(2, 0))
        fmt_cb.bind("<<ComboboxSelected>>", self._on_fmt_change)
        self._style_combo(fmt_cb)

        # DPI
        dl = tk.Frame(cfg, bg=BG); dl.pack(side="left", padx=24)
        tk.Label(dl, text="DPI  (72–600)", font=("Segoe UI", 9), fg=SUBTEXT, bg=BG).pack(anchor="w")
        dpi_spin = tk.Spinbox(dl, from_=72, to=600, increment=50,
                              textvariable=self.dpi, width=6,
                              font=("Segoe UI", 10),
                              bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                              buttonbackground=SURFACE,
                              relief="flat", highlightthickness=1,
                              highlightbackground=BORDER,
                              highlightcolor=ACCENT)
        dpi_spin.pack(pady=(2, 0))

        # JPEG quality (shown only for JPEG/WEBP)
        self._ql = tk.Frame(cfg, bg=BG)
        self._ql.pack(side="left")
        tk.Label(self._ql, text="Quality (1–100)", font=("Segoe UI", 9), fg=SUBTEXT, bg=BG).pack(anchor="w")
        self._q_spin = tk.Spinbox(self._ql, from_=1, to=100, increment=5,
                                   textvariable=self.quality, width=5,
                                   font=("Segoe UI", 10),
                                   bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                                   buttonbackground=SURFACE,
                                   relief="flat", highlightthickness=1,
                                   highlightbackground=BORDER,
                                   highlightcolor=ACCENT)
        self._q_spin.pack(pady=(2, 0))
        self._on_fmt_change()   # init visibility

        # ── Page range ──
        pr = tk.Frame(body, bg=BG)
        pr.pack(fill="x", pady=(0, 12))

        tk.Label(pr, text="Pages:", font=("Segoe UI", 9), fg=SUBTEXT, bg=BG).pack(side="left")
        for val, label in [("all", "All"), ("range", "Range")]:
            rb = tk.Radiobutton(pr, text=label, variable=self.page_range, value=val,
                                command=self._toggle_range,
                                font=("Segoe UI", 10), fg=TEXT, bg=BG,
                                selectcolor=SURFACE, activebackground=BG,
                                activeforeground=ACCENT2,
                                relief="flat", bd=0)
            rb.pack(side="left", padx=8)

        self._range_fr = tk.Frame(pr, bg=BG)
        self._range_fr.pack(side="left", padx=8)
        tk.Label(self._range_fr, text="From", font=("Segoe UI", 9), fg=SUBTEXT, bg=BG).pack(side="left")
        tk.Entry(self._range_fr, textvariable=self.first_page, width=5,
                 font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", padx=(4, 8))
        tk.Label(self._range_fr, text="To", font=("Segoe UI", 9), fg=SUBTEXT, bg=BG).pack(side="left")
        tk.Entry(self._range_fr, textvariable=self.last_page, width=5,
                 font=("Segoe UI", 10), bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat",
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", padx=4)
        self._toggle_range()

        # ── Checkboxes ──
        chk_fr = tk.Frame(body, bg=BG)
        chk_fr.pack(fill="x", pady=(0, 16))
        for var, label in [(self.grayscale, "Grayscale"), (self.transparent, "Transparent bg (PNG only)")]:
            tk.Checkbutton(chk_fr, text=label, variable=var,
                           font=("Segoe UI", 10), fg=TEXT, bg=BG,
                           selectcolor=SURFACE, activebackground=BG,
                           activeforeground=ACCENT2,
                           relief="flat", bd=0).pack(side="left", padx=(0, 20))

        # ── Convert button ──
        self.convert_btn = self._btn(body, "⚡  Convert PDF", self._start_convert,
                                     ACCENT, width=22, pady=10)
        self.convert_btn.pack(pady=(0, 12))

        # ── Progress ──
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(body, variable=self.progress_var,
                                            maximum=100, length=580, mode="determinate")
        self.progress_bar.pack(pady=(0, 8))

        # ── Status log ──
        log_fr = tk.Frame(body, bg=SURFACE, bd=0,
                          highlightthickness=1, highlightbackground=BORDER)
        log_fr.pack(fill="both", expand=True)
        self.log = tk.Text(log_fr, height=6, bg=SURFACE, fg=TEXT,
                           font=("Courier New", 9), relief="flat",
                           state="disabled", wrap="word",
                           insertbackground=TEXT,
                           selectbackground=ACCENT)
        sb = ttk.Scrollbar(log_fr, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True, padx=8, pady=6)
        self.log.tag_config("ok",  foreground=SUCCESS)
        self.log.tag_config("err", foreground=ERROR)
        self.log.tag_config("info",foreground=ACCENT2)

        self._log("Ready. Select a PDF and press Convert.", "info")

    # ── Helpers ─────────────────────────────────────────────────────────────
    def _section(self, parent, text):
        f = tk.Frame(parent, bg=BG); f.pack(fill="x", pady=(4, 4))
        tk.Label(f, text=text, font=("Segoe UI", 10, "bold"),
                 fg=ACCENT2, bg=BG).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(side="left", fill="x",
                                               expand=True, padx=(8, 0), pady=8)

    def _entry(self, parent, var, placeholder=""):
        e = tk.Entry(parent, textvariable=var, font=("Segoe UI", 10),
                     bg=SURFACE, fg=TEXT, insertbackground=TEXT,
                     relief="flat", highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT)
        if placeholder and not var.get():
            e.insert(0, placeholder)
            e.config(fg=SUBTEXT)
            def on_focus_in(ev):
                if e.get() == placeholder:
                    e.delete(0, "end"); e.config(fg=TEXT)
            def on_focus_out(ev):
                if not e.get():
                    e.insert(0, placeholder); e.config(fg=SUBTEXT)
            e.bind("<FocusIn>", on_focus_in)
            e.bind("<FocusOut>", on_focus_out)
        return e

    def _btn(self, parent, text, cmd, color, width=10, pady=6):
        b = tk.Button(parent, text=text, command=cmd,
                      font=("Segoe UI", 10, "bold"),
                      bg=color, fg="white", relief="flat",
                      activebackground=ACCENT2, activeforeground="white",
                      cursor="hand2", padx=14, pady=pady, width=width)
        b.bind("<Enter>", lambda e: b.config(bg=ACCENT2))
        b.bind("<Leave>", lambda e: b.config(bg=color))
        return b

    def _style_combo(self, cb):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=SURFACE, background=SURFACE,
                        foreground=TEXT, selectbackground=ACCENT,
                        selectforeground="white", bordercolor=BORDER)

    def _log(self, msg, tag=""):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    # ── Events ───────────────────────────────────────────────────────────────
    def _browse_pdf(self):
        path = filedialog.askopenfilename(
            title="Select PDF", filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if path:
            self.pdf_path.set(path)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(path).parent))

    def _browse_dir(self):
        d = filedialog.askdirectory(title="Select Output Folder")
        if d:
            self.output_dir.set(d)

    def _on_fmt_change(self, *_):
        fmt = self.fmt.get()
        if fmt in ("JPEG", "WEBP"):
            self._ql.pack(side="left")
        else:
            self._ql.pack_forget()

    def _toggle_range(self):
        state = "normal" if self.page_range.get() == "range" else "disabled"
        for w in self._range_fr.winfo_children():
            try: w.config(state=state)
            except Exception: pass

    # ── Conversion ───────────────────────────────────────────────────────────
    def _start_convert(self):
        if self._converting:
            return
        pdf = self.pdf_path.get().strip()
        out = self.output_dir.get().strip()

        if not pdf or not os.path.isfile(pdf):
            messagebox.showerror("Error", "Please select a valid PDF file.")
            return
        if not out:
            out = str(Path(pdf).parent)
            self.output_dir.set(out)
        os.makedirs(out, exist_ok=True)

        self._converting = True
        self.convert_btn.config(state="disabled", text="Converting…")
        self.progress_var.set(0)
        threading.Thread(target=self._convert_worker,
                         args=(pdf, out), daemon=True).start()

    def _convert_worker(self, pdf_path, out_dir):
        try:
            fmt     = self.fmt.get()
            dpi     = self.dpi.get()
            gray    = self.grayscale.get()
            transp  = self.transparent.get() and fmt == "PNG"
            quality = self.quality.get() if fmt in ("JPEG", "WEBP") else None

            kwargs = dict(dpi=dpi, grayscale=gray, transparent=transp,
                          use_pdftocairo=True)

            if self.page_range.get() == "range":
                fp = int(self.first_page.get() or 1)
                lp = self.last_page.get().strip()
                kwargs["first_page"] = fp
                if lp:
                    kwargs["last_page"] = int(lp)

            self._log(f"Converting: {Path(pdf_path).name}", "info")
            self._log(f"Format={fmt}  DPI={dpi}  Gray={gray}  Transparent={transp}", "info")

            images = convert_from_path(pdf_path, **kwargs)
            total  = len(images)
            stem   = Path(pdf_path).stem
            ext    = fmt.lower()
            if fmt == "JPEG": ext = "jpg"

            save_kwargs = {}
            if quality:
                save_kwargs["quality"] = quality

            for i, img in enumerate(images, 1):
                fname = f"{stem}_page{i:04d}.{ext}"
                fpath = os.path.join(out_dir, fname)

                if fmt == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")

                img.save(fpath, fmt, **save_kwargs)
                pct = (i / total) * 100
                self.after(0, self.progress_var.set, pct)
                self._log(f"  ✓ Saved {fname}", "ok")

            self.after(0, self._on_done, total, out_dir)

        except PDFInfoNotInstalledError:
            msg = ("Poppler is not installed or not in PATH.\n\n"
                   "  macOS  : brew install poppler\n"
                   "  Linux  : sudo apt install poppler-utils\n"
                   "  Windows: download from github.com/oschwartz10612/poppler-windows")
            self._log("ERROR: " + msg.split('\n')[0], "err")
            self.after(0, messagebox.showerror, "Poppler Missing", msg)
            self.after(0, self._reset_btn)

        except Exception as exc:
            self._log(f"ERROR: {exc}", "err")
            self.after(0, messagebox.showerror, "Conversion Failed", str(exc))
            self.after(0, self._reset_btn)

    def _on_done(self, count, out_dir):
        self._log(f"\n✅ Done! {count} image(s) saved to:\n   {out_dir}", "ok")
        self._reset_btn()
        if messagebox.askyesno("Complete",
                               f"{count} image(s) saved.\n\nOpen output folder?"):
            self._open_folder(out_dir)

    def _reset_btn(self):
        self._converting = False
        self.convert_btn.config(state="normal", text="⚡  Convert PDF")

    @staticmethod
    def _open_folder(path):
        import subprocess, platform
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(path)
            elif system == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


if __name__ == "__main__":
    app = PDFConverterApp()
    app.mainloop()
