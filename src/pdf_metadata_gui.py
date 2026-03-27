#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enhanced PDF Metadata Extractor GUI with integrated metadata display fields."""

import threading
import os
import logging
from typing import List, Optional, Dict
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk
from tkinter import filedialog, messagebox, simpledialog

import sys
from datetime import datetime
import json

# Prefer package-relative imports when running as package; fall back to script imports
try:
    from .pdf_processor import PDFProcessor
    from .metadata_extractor import MetadataExtractor
    from .excel_exporter import ExcelExporter
    from .config import get_poppler_path, TESSERACT_CMD, OCR_LANG, OCR_ENGINE
    from .post_processing import get_post_processor
except Exception:
    # Running as a loose script; adjust sys.path to include src directory and import
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    from pdf_processor import PDFProcessor
    from metadata_extractor import MetadataExtractor
    from excel_exporter import ExcelExporter
    from config import get_poppler_path, TESSERACT_CMD, OCR_LANG, OCR_ENGINE
    from post_processing import get_post_processor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PDFMetadataGUI(ctk.CTk):
    """GUI for extracting metadata from PDFs with integrated metadata display fields.
    
    Features:
    - Sidebar layout for controls.
    - Tabview for Live Data (Treeview) and Logs.
    - Real-time metadata preview.
    """

    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        self.title("PDF Metadata Extractor Pro")
        self.geometry("1100x700")

        # Data & State
        self.input_paths: List[str] = []
        self.output_path: Optional[str] = None
        self.processing = False
        self.stop_requested = False
        self.current_thread: Optional[threading.Thread] = None
        self.metadata_results: Dict[str, Dict] = {} # Store results for each file
        self.post_processor = None
        threading.Thread(target=self._init_post_processor, daemon=True).start()
        
        # Pause/Resume State
        self.pause_event = threading.Event()
        self.pause_event.set() # Initially not paused
        self.is_paused = False
        
        # New Settings
        self.auto_correct_var = tk.BooleanVar(value=False)
        self.hide_editor_var = tk.BooleanVar(value=False)

        # Grid layout 1x2 (Sidebar, Main)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._create_sidebar()
        self._create_main_area()
        
        # Post-processor loading handles this now
        # self.post_processor.load_deep_learning_model()

    def _init_post_processor(self):
        """Initialize post-processor and models in background."""
        try:
            self.post_processor = get_post_processor()
            self.post_processor.load_deep_learning_model()
            self.lbl_info.configure(text="AI Engine Ready", text_color="#00E5FF")
        except Exception as e:
            logger.error(f"Post-processor backend init failed: {e}")
            self.lbl_info.configure(text="AI Engine Error", text_color="#C0392B")

    def _create_sidebar(self):
        """Create the enhanced hitech sidebar."""
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#1E1E2E")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(14, weight=1) # Spacer

        # Logo/Title
        lbl_logo = ctk.CTkLabel(self.sidebar_frame, text="SHBM", font=ctk.CTkFont(size=24, weight="bold"), text_color="#00E5FF")
        lbl_logo.grid(row=0, column=0, padx=20, pady=(30, 5))
        
        lbl_subtitle = ctk.CTkLabel(self.sidebar_frame, text="Metadata AI Pro", font=ctk.CTkFont(size=12, slant="italic"), text_color="gray")
        lbl_subtitle.grid(row=1, column=0, padx=20, pady=(0, 20))

        # --- Section: INPUT ---
        lbl_sec_input = ctk.CTkLabel(self.sidebar_frame, text="DATA INPUT", font=ctk.CTkFont(size=10, weight="bold"), text_color="#555555")
        lbl_sec_input.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")

        self.btn_select_files = ctk.CTkButton(self.sidebar_frame, text="📄 Select Files", command=self._select_input_files, fg_color="transparent", border_width=1, hover_color="#2D2D44")
        self.btn_select_files.grid(row=3, column=0, padx=20, pady=5)

        self.btn_select_dir = ctk.CTkButton(self.sidebar_frame, text="📁 Select Folder", command=self._select_input_directory, fg_color="transparent", border_width=1, hover_color="#2D2D44")
        self.btn_select_dir.grid(row=4, column=0, padx=20, pady=5)

        # --- Section: CONFIG ---
        lbl_sec_cfg = ctk.CTkLabel(self.sidebar_frame, text="CONFIGURATION", font=ctk.CTkFont(size=10, weight="bold"), text_color="#555555")
        lbl_sec_cfg.grid(row=5, column=0, padx=20, pady=(15, 5), sticky="w")

        self.ocr_engine_var = tk.StringVar(value=OCR_ENGINE)
        self.ocr_optionmenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["windows", "tesseract"], variable=self.ocr_engine_var, fg_color="#2D2D44", button_color="#3D3D55")
        self.ocr_optionmenu.grid(row=6, column=0, padx=20, pady=5)

        self.sw_auto_correct = ctk.CTkSwitch(self.sidebar_frame, text="AI Correction", variable=self.auto_correct_var, progress_color="#00E5FF")
        self.sw_auto_correct.grid(row=7, column=0, padx=20, pady=5, sticky="w")

        # --- Section: EXECUTION ---
        lbl_sec_exe = ctk.CTkLabel(self.sidebar_frame, text="EXECUTION", font=ctk.CTkFont(size=10, weight="bold"), text_color="#555555")
        lbl_sec_exe.grid(row=8, column=0, padx=20, pady=(15, 5), sticky="w")

        self.btn_start = ctk.CTkButton(self.sidebar_frame, text="START ENGINE", command=self._start_processing, fg_color="#2CC985", hover_color="#27AE60", text_color="white", font=ctk.CTkFont(weight="bold"), height=40)
        self.btn_start.grid(row=9, column=0, padx=20, pady=10)

        self.btn_stop = ctk.CTkButton(self.sidebar_frame, text="EMERGENCY STOP", command=self._request_stop, fg_color="#C0392B", hover_color="#A93226", text_color="white", state="disabled")
        self.btn_stop.grid(row=10, column=0, padx=20, pady=(5, 10))

        self.btn_pause = ctk.CTkButton(self.sidebar_frame, text="⏸ PAUSE ENGINE", command=self._toggle_pause, fg_color="#3D3D55", hover_color="#2D2D44", state="disabled")
        self.btn_pause.grid(row=11, column=0, padx=20, pady=5)

        self.btn_resume = ctk.CTkButton(self.sidebar_frame, text="▶ RESUME ENGINE", command=self._toggle_resume, fg_color="#00E5FF", hover_color="#00B8CC", text_color="#11111B", state="disabled")
        self.btn_resume.grid(row=11, column=0, padx=20, pady=5)
        self.btn_resume.grid_remove() # Hide resume by default

        # Output Selection - Stylized as a button but for path
        self.btn_select_out = ctk.CTkButton(self.sidebar_frame, text="📤 Set Output", command=self._select_output_file, fg_color="transparent", border_width=1, text_color="silver")
        self.btn_select_out.grid(row=11, column=0, padx=20, pady=20)

        # System Monitor Placeholder
        self.monitor_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#161625", corner_radius=10)
        self.monitor_frame.grid(row=15, column=0, padx=15, pady=20, sticky="ew")
        
        self.lbl_info = ctk.CTkLabel(self.monitor_frame, text="Idle", text_color="#00E5FF", font=ctk.CTkFont(size=11))
        self.lbl_info.pack(pady=10)

        self.btn_exit = ctk.CTkButton(self.sidebar_frame, text="EXIT", command=self._exit_app, fg_color="transparent", text_color="#555555", hover_color="#2D2D44")
        self.btn_exit.grid(row=16, column=0, padx=20, pady=(0, 20))

    def _create_main_area(self):
        """Create the hitech main area with card layout."""
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#11111B")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Card: Header/Status
        self.header_card = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color="#1E1E2E", height=70)
        self.header_card.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.header_card.grid_propagate(False)
        
        self.lbl_status = ctk.CTkLabel(self.header_card, text="SYSTEM STATUS: OPTIMAL", anchor="w", font=ctk.CTkFont(size=14, weight="bold"), text_color="#2CC985")
        self.lbl_status.pack(side="left", padx=20)
        
        self.progress_bar = ctk.CTkProgressBar(self.header_card, width=400, height=12, progress_color="#00E5FF", fg_color="#2D2D44")
        self.progress_bar.pack(side="right", padx=20)
        self.progress_bar.set(0)

        # Card: Live Data Display
        self.data_card = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color="#1E1E2E")
        self.data_card.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        
        self.tabview = ctk.CTkTabview(self.data_card, fg_color="transparent", segmented_button_fg_color="#1E1E2E", segmented_button_selected_color="#00E5FF", segmented_button_selected_hover_color="#00B8CC")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        self.tabview.add("LIVE STREAM")
        self.tabview.add("SYSTEM LOGS")
        
        # LOGS TAB
        self.log_box = ctk.CTkTextbox(self.tabview.tab("SYSTEM LOGS"), fg_color="#161625", text_color="#A9B1D6", font=ctk.CTkFont(family="Consolas", size=11))
        self.log_box.pack(fill="both", expand=True, padx=5, pady=5)

        # LIVE DATA TAB
        self.tree_frame = ctk.CTkFrame(self.tabview.tab("LIVE STREAM"), fg_color="transparent")
        self.tree_frame.pack(fill="both", expand=True)
        
        # Treeview Styles handled below in the same method or __init__
        cols = ("file", "status", "so_van_ban", "ky_hieu_van_ban", "co_quan_ban_hanh", "ngay", "nguoi_ky", "trich_yeu", "hop_so", "nhiem_ky")
        self.tree = ttk.Treeview(self.tree_frame, columns=cols, show='headings', selectmode="browse")
        
        # Headers/Columns setup remains similar but we'll polish style
        self.tree.heading("file", text="SOURCE")
        self.tree.heading("status", text="STATE")
        self.tree.heading("so_van_ban", text="ID")
        self.tree.heading("ky_hieu_van_ban", text="SYMBOL")
        self.tree.heading("co_quan_ban_hanh", text="AGENCY")
        self.tree.heading("ngay", text="DATE")
        self.tree.heading("nguoi_ky", text="SIGNER")
        self.tree.heading("trich_yeu", text="SUMMARY")
        self.tree.heading("hop_so", text="BOX")
        self.tree.heading("nhiem_ky", text="TENURE")
        
        for col in cols:
            self.tree.column(col, anchor="center")
        self.tree.column("file", width=180, anchor="w")
        self.tree.column("co_quan_ban_hanh", width=150, anchor="w")
        self.tree.column("trich_yeu", width=250, anchor="w")
        self.tree.column("hop_so", width=60)
        self.tree.column("nhiem_ky", width=100)

        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Card: Metadata Editor (Glassmorphism look)
        self.editor_card = ctk.CTkFrame(self.main_frame, corner_radius=15, fg_color="#1E1E2E", height=280)
        self.editor_card.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        
        lbl_editor_title = ctk.CTkLabel(self.editor_card, text="METADATA INTELLIGENCE UNIT", font=ctk.CTkFont(size=12, weight="bold"), text_color="#555555")
        lbl_editor_title.pack(pady=(10, 5), padx=20, anchor="w")

        self.edit_fields_frame = ctk.CTkFrame(self.editor_card, fg_color="transparent")
        self.edit_fields_frame.pack(fill="both", expand=True, padx=20, pady=5)
        
        # Define some common fields to edit
        self.entries = {}
        fields = [
            ("Ref ID", "so_van_ban"),
            ("Sym Code", "ky_hieu_van_ban"),
            ("Release Date", "ngay_ban_hanh"),
            ("Authority", "co_quan_ban_hanh"),
            ("Authorized by", "nguoi_ky"),
            ("Box #", "hop_so"),
            ("Tenure", "nhiem_ky"),
            ("Doc Type", "the_loai_van_ban"),
            ("Dossier", "so_ho_so"),
            ("Digest / Summary", "trich_yeu_noi_dung")
        ]
        
        for i, (label, key) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2
            
            lbl = ctk.CTkLabel(self.edit_fields_frame, text=label.upper()+":", font=ctk.CTkFont(size=10, weight="bold"), text_color="#555555")
            lbl.grid(row=row, column=col, padx=(5, 10), pady=4, sticky="e")
            
            if key == "trich_yeu_noi_dung":
                entry = ctk.CTkTextbox(self.edit_fields_frame, height=70, width=400, fg_color="#161625", border_color="#2D2D44", border_width=1)
                entry.grid(row=row, column=col+1, padx=5, pady=4, sticky="w", columnspan=3)
                entry.bind("<KeyRelease>", lambda e, k=key: self._on_text_change(e, k))
            else:
                entry = ctk.CTkEntry(self.edit_fields_frame, width=220, height=28, fg_color="#161625", border_color="#2D2D44", border_width=1)
                entry.grid(row=row, column=col+1, padx=5, pady=4, sticky="w")
                entry.bind("<KeyRelease>", lambda e, k=key: self._on_field_change(e, k))
            
            self.entries[key] = entry

        # Floating action buttons in editor
        self.editor_actions = ctk.CTkFrame(self.editor_card, fg_color="transparent")
        self.editor_actions.pack(fill="x", side="bottom", padx=20, pady=(0, 15))

        self.btn_save_edit = ctk.CTkButton(self.editor_actions, text="APPLY CHANGES", command=self._save_metadata_changes, width=150, height=32, fg_color="#00E5FF", hover_color="#00B8CC", text_color="#11111B", font=ctk.CTkFont(weight="bold"))
        self.btn_save_edit.pack(side="right")
        
        # AI Status (Glow effect text)
        self.ai_status_frame = ctk.CTkFrame(self.editor_actions, fg_color="transparent")
        self.ai_status_frame.pack(side="left", fill="x", expand=True)
        
        lbl_ai_tag = ctk.CTkLabel(self.ai_status_frame, text="AI CORE STATUS:", font=ctk.CTkFont(size=9, weight="bold"), text_color="#2CC985")
        lbl_ai_tag.pack(side="left", padx=(0, 10))
        
        self.p_status_box = ctk.CTkLabel(self.ai_status_frame, text="Operational. Monitoring documents...", text_color="#A9B1D6", font=ctk.CTkFont(size=11, slant="italic"))
        self.p_status_box.pack(side="left")
        
        # Style Treeview with premium dark look
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", 
                        background="#1E1E2E", 
                        foreground="#A9B1D6", 
                        fieldbackground="#1E1E2E", 
                        bordercolor="#11111B", 
                        borderwidth=0,
                        rowheight=30,
                        font=('Segoe UI Variable Display', 10))
        style.map('Treeview', background=[('selected', '#2D2D44')], foreground=[('selected', '#00E5FF')])
        style.configure("Treeview.Heading", 
                        background="#161625", 
                        foreground="#555555", 
                        relief="flat",
                        font=('Segoe UI Variable Display', 10, 'bold'))
        style.map("Treeview.Heading", background=[('active', '#1E1E2E')], foreground=[('active', '#00E5FF')])

    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)
        # Update Treeview colors based on mode if needed (omitted for brevity, defaulting to dark style above)

    def _log(self, msg: str):
        self.log_box.insert("end", f"{msg}\n")
        self.log_box.see("end")
        
    def _select_input_files(self):
        files = filedialog.askopenfilenames(title="Chọn file PDF", filetypes=[("PDF files", "*.pdf")])
        if files:
            self.input_paths = list(files)
            self.lbl_info.configure(text=f"Đã chọn {len(files)} file")
            self._propose_output(self.input_paths[0])

    def _select_input_directory(self):
        path = filedialog.askdirectory()
        if path:
            pdfs = []
            for root, _, files in os.walk(path):
                for f in files:
                    if f.lower().endswith('.pdf'):
                        pdfs.append(os.path.join(root, f))
            if not pdfs:
                messagebox.showwarning("Warning", "Không tìm thấy PDF nào!")
                return
            
            # Limit dialog
            try:
                limit = simpledialog.askinteger("Limit", f"Tìm thấy {len(pdfs)} file. Nhập số lượng muốn xử lý (để trống hoặc 0 = tất cả):")
            except:
                limit = 0
            
            if limit and limit > 0:
                pdfs = pdfs[:limit]
            
            self.input_paths = pdfs
            self.lbl_info.configure(text=f"Đã chọn {len(pdfs)} file từ thư mục")
            self._propose_output(path, is_dir=True)

    def _propose_output(self, path: str, is_dir=False):
        if self.output_path: 
            return # already set
        if is_dir:
            self.output_path = os.path.join(path, "metadata_output.xlsx")
        else:
            base = os.path.splitext(path)[0]
            self.output_path = base + "_metadata.xlsx"
        self._log(f"Output mặc định: {self.output_path}")

    def _select_output_file(self):
        f = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if f:
            self.output_path = f
            self._log(f"Output đã chọn: {self.output_path}")

    def _exit_app(self):
        """Exit the application."""
        if self.processing:
            if not messagebox.askyesno("Confirm", "Đang xử lý. Bạn có chắc muốn thoát?"):
                return
            self.stop_requested = True
        self.quit()
        self.destroy()

    def _start_processing(self):
        if self.processing: return
        if not self.input_paths:
            messagebox.showerror("Error", "Chưa chọn input files!")
            return
        if not self.output_path:
            messagebox.showerror("Error", "Chưa chọn output path!")
            return

        self.processing = True
        self.stop_requested = False
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_pause.configure(state="normal")
        self.btn_resume.configure(state="disabled")
        self.tabview.set("LIVE STREAM") # Switch to data view
        
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.current_thread = threading.Thread(target=self._run_extraction, daemon=True)
        self.current_thread.start()

    def _request_stop(self):
        if self.processing:
            if messagebox.askyesno("Confirm", "Bạn có chắc muốn dừng xử lý?"):
                self.lbl_status.configure(text="Trạng thái: Đang dừng...", text_color="#C0392B")
                self.pause_event.set() # Ensure loop progresses to check stop flag
                self.is_paused = False
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="disabled")

    def _toggle_pause(self):
        """Pause the engine."""
        self.is_paused = True
        self.pause_event.clear()
        self.btn_pause.grid_remove()
        self.btn_resume.grid()
        self.btn_resume.configure(state="normal")
        self.lbl_status.configure(text="SYSTEM PAUSED", text_color="#F1C40F")
        self._log("Engine paused.")

    def _toggle_resume(self):
        """Resume the engine."""
        self.is_paused = False
        self.pause_event.set()
        self.btn_resume.grid_remove()
        self.btn_pause.grid()
        self.btn_pause.configure(state="normal")
        self.lbl_status.configure(text="SYSTEM STATUS: OPTIMAL", text_color="#2CC985")
        self._log("Engine resumed.")

    def _run_extraction(self):
        try:
            self._log("Bắt đầu xử lý...")
            pdfp = PDFProcessor(
                poppler_path=get_poppler_path(), 
                ocr_enabled=True, 
                tesseract_cmd=TESSERACT_CMD,
                ocr_engine=self.ocr_engine_var.get()
            )
            extractor = MetadataExtractor()
            
            total = len(self.input_paths)
            processed_count = 0
            
            # For final export, we need all text mapping if using extract_from_directory logic
            # But for live view, we extract one by one.
            # To allow final export to work efficiently with grouping, we can accumulate data.
            all_texts_pages = {} 
            all_styles_map = {} # Accumulate styles for final export
            all_metadata = []

            for idx, fpath in enumerate(self.input_paths):
                # Check for pause
                self.pause_event.wait()
                
                if self.stop_requested:
                    self._log("Đã dừng bởi người dùng.")
                    break
                
                fname = os.path.basename(fpath)
                self.lbl_status.configure(text=f"Đang xử lý [{idx+1}/{total}]: {fname}")
                self._log(f"Processing {fname}...")
                
                # Insert row into tree for live status
                # Match the expanded columns: ("file", "status", "so_van_ban", "ky_hieu_van_ban", "co_quan_ban_hanh", "ngay", "nguoi_ky", "trich_yeu")
                node_id = self.tree.insert("", "end", values=(fname, "Đang xử lý...", "", "", "", "", "", ""))
                self.tree.see(node_id)
                self.update_idletasks() # Refresh UI
                
                try:
                    # 1. Extract Text
                    # force_ocr=False ensures we try native first, then fallback to OCR if empty
                    fpath_ret, pages = pdfp.process_pdf(fpath, force_ocr=False)
                    all_texts_pages[fpath] = pages
                    full_text = "\n".join(pages)
                    
                    # 2. Extract Styles (Bold/Uppercase) for better extraction
                    # Need to flatten per-page styles into a single set for the simple API
                    bold_set = set()
                    upper_set = set()
                    try:
                        bold_dict = pdfp.extract_bold_lines(fpath) or {}
                        upper_dict = pdfp.extract_uppercase_titles(fpath) or {}
                        
                        # Merge into a style dict for finalize (page_idx -> list)
                        style_merged = {}
                        all_pages = set(list(bold_dict.keys()) + list(upper_dict.keys()))
                        for p in all_pages:
                            lines_p = []
                            if p in bold_dict: lines_p.extend(bold_dict[p])
                            if p in upper_dict: lines_p.extend([t for t, _ in upper_dict[p]])
                            style_merged[p] = lines_p
                            
                            # Also populate sets for immediate usage
                            # (Heuristic: usually first 2 pages are enough for metadata)
                            if p < 2:
                                for l in bold_dict.get(p, []):
                                    bold_set.add(' '.join(l.split()))
                                for t, _ in upper_dict.get(p, []):
                                    upper_set.add(' '.join(t.split()))
                        
                        all_styles_map[fpath] = style_merged
                    except Exception as e:
                        logger.warning(f"Style extraction failed for {fname}: {e}")



                    processed_count += 1
                    self.progress_bar.set(processed_count / total)
                    
                    metadata = extractor.extract_from_text(full_text, bold_lines=bold_set, uppercase_titles=upper_set)
                    metadata['duong_dan_file'] = fpath
                    
                    # 3. AUTO CORRECT (New Feature)
                    if self.auto_correct_var.get() and self.post_processor:
                        self._log(f"Auto-correcting {fname}...")
                        for key in ['co_quan_ban_hanh', 'nguoi_ky', 'trich_yeu_noi_dung']:
                            if key in metadata and metadata[key]:
                                if key == 'trich_yeu_noi_dung':
                                    metadata[key] = self.post_processor.correct_text(metadata[key])
                                else:
                                    metadata[key] = self.post_processor.correct_word(metadata[key])

                    # Ensure so_ho_so is present (even if empty)
                    if 'so_ho_so' not in metadata:
                        metadata['so_ho_so'] = ""
                    self.metadata_results[fpath] = metadata
                    
                    # Update Treeview status
                    # ("file", "status", "so_van_ban", "ky_hieu_van_ban", "co_quan_ban_hanh", "ngay", "nguoi_ky", "trich_yeu")
                    self.tree.item(node_id, values=(
                        fname, 
                        "Hoàn tất", 
                        metadata.get('so_van_ban', ""),
                        metadata.get('ky_hieu_van_ban', ""),
                        metadata.get('co_quan_ban_hanh', ""),
                        metadata.get('ngay_ban_hanh', ""),
                        metadata.get('nguoi_ky', ""),
                        metadata.get('trich_yeu_noi_dung', ""),
                        metadata.get('hop_so', ""),
                        metadata.get('nhiem_ky', "")
                    ))
                    
                except Exception as e:
                    self._log(f"Lỗi file {fname}: {e}")
                    logger.error(f"Error processing {fpath}", exc_info=True)

            # Export
            if not self.stop_requested and all_texts_pages:
                self.lbl_status.configure(text="Đang xuất Excel...")
                self._log("Đang tổng hợp và xuất Excel...")
                
                # Use the extractor's batch method to handle grouping correctly
                base_dir = os.path.dirname(self.input_paths[0])
                final_meta = extractor.extract_from_directory(all_texts_pages, base_dir=base_dir, all_styles=all_styles_map)
                
                # Update hyperlinks to be relative to the OUTPUT EXCEL path, not the input base_dir
                output_dir = os.path.dirname(os.path.abspath(self.output_path))
                for item in final_meta:
                    if item.get('dia_chi_tai_lieu_goc'):
                        abs_path = os.path.abspath(item['dia_chi_tai_lieu_goc'])
                        try:
                            # Calculate relative path from Output Dir to PDF File
                            rel_path = os.path.relpath(abs_path, output_dir)
                            item['xem_file'] = f'=HYPERLINK("{rel_path}", "Xem")'
                        except ValueError:
                            # Paths on different drives on Windows? Keep absolute or original.
                            pass

                exporter = ExcelExporter()
                exporter.export(final_meta, self.output_path)
                
                messagebox.showinfo("Success", f"Hoàn tất! Đã xuất ra {self.output_path}")
                self._log(f"Xong. File: {self.output_path}")
                self.lbl_status.configure(text="Hoàn tất.")
                
                # Ask to open file
                if messagebox.askyesno("Mở file", "Bạn có muốn mở file Excel vừa tạo không?"):
                    try:
                        os.startfile(self.output_path)
                    except Exception as e:
                        messagebox.showerror("Lỗi", f"Không thể mở file: {e}")
            elif self.stop_requested and all_texts_pages:
                 # Partial export option?
                 if messagebox.askyesno("Saved Partial", "Đã dừng. Bạn có muốn lưu kết quả các file đã xong không?"):
                    base_dir = os.path.dirname(self.input_paths[0])
                    final_meta = extractor.extract_from_directory(all_texts_pages, base_dir=base_dir, all_styles=all_styles_map)
                    
                    # Update hyperlinks relative to output
                    output_dir = os.path.dirname(os.path.abspath(self.output_path))
                    for item in final_meta:
                        if item.get('dia_chi_tai_lieu_goc'):
                             abs_path = os.path.abspath(item['dia_chi_tai_lieu_goc'])
                             try:
                                 rel_path = os.path.relpath(abs_path, output_dir)
                                 item['xem_file'] = f'=HYPERLINK("{rel_path}", "Xem")'
                             except ValueError:
                                 pass

                    exporter = ExcelExporter()
                    exporter.export(final_meta, self.output_path)
                    self._log(f"Đã lưu kết quả một phần: {self.output_path}")

                    # Ask to open file (Partial)
                    if messagebox.askyesno("Mở file", "Bạn có muốn mở file Excel vừa tạo không?"):
                        try:
                            os.startfile(self.output_path)
                        except Exception as e:
                            messagebox.showerror("Lỗi", f"Không thể mở file: {e}")

        except Exception as e:
            self._log(f"Critical Error: {e}")
            messagebox.showerror("Error", str(e))
        finally:
            self.processing = False
            self.btn_start.configure(state="normal")
            self.btn_stop.configure(state="disabled")
            self.btn_pause.configure(state="disabled")
            self.btn_resume.configure(state="disabled")
            self.btn_resume.grid_remove()
            self.btn_pause.grid()

    def _on_tree_select(self, event):
        """Update editor when a file is selected in Treeview."""
        selected = self.tree.selection()
        if not selected: return
        
        item = self.tree.item(selected[0])
        fname = item['values'][0]
        
        # Find absolute path
        fpath = None
        for p in self.input_paths:
            if os.path.basename(p) == fname:
                fpath = p
                break
        
        if fpath and fpath in self.metadata_results:
            meta = self.metadata_results[fpath]
            for key, entry in self.entries.items():
                val = meta.get(key, "")
                if isinstance(entry, ctk.CTkTextbox):
                    entry.delete("1.0", "end")
                    entry.insert("1.0", val)
                else:
                    entry.delete(0, "end")
                    entry.insert(0, val)

    def _on_field_change(self, event, key):
        pass

    def _on_text_change(self, event, key):
        """Reserved for future interactive correction."""
        pass

    def _save_metadata_changes(self):
        selected = self.tree.selection()
        if not selected: return
        
        item = self.tree.item(selected[0])
        fname = item['values'][0]
        fpath = None
        for p in self.input_paths:
            if os.path.basename(p) == fname:
                fpath = p
                break
        
        if fpath and fpath in self.metadata_results:
            meta = self.metadata_results[fpath]
            for key, entry in self.entries.items():
                if isinstance(entry, ctk.CTkTextbox):
                    meta[key] = entry.get("1.0", "end-1c").strip()
                else:
                    meta[key] = entry.get().strip()
            
            # Update Treeview with new changes
            self.tree.item(selected[0], values=(
                fname, 
                "Đã sửa", 
                meta.get('so_van_ban', ""),
                meta.get('ky_hieu_van_ban', ""),
                meta.get('co_quan_ban_hanh', ""),
                meta.get('ngay_ban_hanh', ""),
                meta.get('nguoi_ky', ""),
                meta.get('trich_yeu_noi_dung', ""),
                meta.get('hop_so', ""),
                meta.get('nhiem_ky', "")
            ))
            
            messagebox.showinfo("Info", "Đã cập nhật metadata tạm thời.")

    def _toggle_editor_view(self):
        """Hide/Show the metadata editor based on switch."""
        if self.hide_editor_var.get():
            self.editor_frame.pack_forget()
        else:
            self.editor_frame.pack(fill="x", side="bottom", padx=5, pady=5)

if __name__ == "__main__":
    app = PDFMetadataGUI()
    app.mainloop()
