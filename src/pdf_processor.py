# pdf_processor.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
import pickle
import re
import unicodedata
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from tqdm import tqdm

try:
    from .metadata_extractor import extract_metadata
except ImportError:
    from metadata_extractor import extract_metadata

logger = logging.getLogger(__name__)

# ===== TEXT CLEANING HELPERS =====





# rest of the application can still run (we'll log a helpful message).
try:
    from PyPDF2 import PdfReader, PdfWriter, PdfMerger
except Exception:
    PdfReader = None
    PdfWriter = None
    PdfMerger = None
    logger.warning(
        "PyPDF2 is not installed or could not be imported. PDF text extraction "
        "will be disabled. Install with: pip install PyPDF2"
    )

class PDFProcessor:
    def __init__(self, poppler_path: str = None, ocr_enabled: bool = True,
                 tesseract_cmd: Optional[str] = None, ocr_dpi: int = 300,
                 ocr_lang: Optional[str] = 'vie', use_cache: bool = True,
                 ocr_engine: str = 'tesseract'):
        """Initialize PDF processor

        Args:
            poppler_path: Optional path to poppler binaries (for pdf2image)
            ocr_enabled: If True (default), enable OCR fallback for scanned PDFs when text extraction yields no text.
            tesseract_cmd: Optional explicit tesseract executable path to set for pytesseract.
            ocr_dpi: DPI to render PDF pages for OCR.
            ocr_lang: Optional language code for pytesseract (e.g., 'vie' or 'eng').
            use_cache: Whether to use caching for OCR results
            ocr_engine: OCR engine to use ('tesseract' or 'windows')
        """
        self.poppler_path = poppler_path
        self.ocr_enabled = bool(ocr_enabled)
        self.tesseract_cmd = tesseract_cmd
        self.ocr_dpi = int(ocr_dpi)
        self.ocr_lang = ocr_lang
        self.ocr_engine = ocr_engine.lower()
        
        # Cache system
        self._cache = {}
        # Store cache in a dedicated cache directory
        cache_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        self._cache_file = os.path.join(cache_dir, 'ocr_cache')
        self._use_cache = use_cache
        if use_cache:
            self._load_cache()
            
    def _load_cache(self):
        """Load OCR cache from disk"""
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'rb') as f:
                    self._cache = pickle.load(f)
        except Exception as e:
            logger.warning(f"Could not load OCR cache: {e}")
            self._cache = {}
            
    def _save_cache(self):
        """Save OCR cache to disk"""
        try:
            with open(self._cache_file, 'wb') as f:
                pickle.dump(self._cache, f)
        except Exception as e:
            logger.warning(f"Could not save OCR cache: {e}")

    def extract_styles(self, pdf_path: str, max_pages: int = 3) -> Dict[str, set]:
        """Extract both bold and uppercase lines in a single pass using pdfplumber.
        
        Returns a dict with:
        - 'bold': set of strings
        - 'uppercase': set of strings
        """
        try:
            import pdfplumber
        except Exception:
            logger.debug('pdfplumber not available; cannot extract styles')
            return {'bold': set(), 'uppercase': set()}

        bold_lines = set()
        uppercase_lines = set()
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages_to_check = min(len(pdf.pages), max_pages)
                for p_idx in range(pages_to_check):
                    page = pdf.pages[p_idx]
                    try:
                        # Extract words with font info
                        words = page.extract_words(extra_attrs=['fontname', 'size'])
                    except Exception:
                        continue

                    # Group words into lines by 'top' coordinate
                    buckets = {}
                    for w in words:
                        top = int(round(w.get('top', 0)))
                        buckets.setdefault(top, []).append(w)

                    for top in sorted(buckets.keys()):
                        parts = buckets[top]
                        line_text = ' '.join(p.get('text', '') for p in parts).strip()
                        if not line_text:
                            continue
                        
                        # Check bold
                        is_bold = any('Bold' in (p.get('fontname') or '') or 'BD' in (p.get('fontname') or '').upper() for p in parts)
                        
                        # Check uppercase
                        is_upper = line_text == line_text.upper() and any(c.isalpha() for c in line_text)
                        
                        # Check size (for titles)
                        sizes = [float(p.get('size') or p.get('fontsize') or 0) for p in parts if (p.get('size') or p.get('fontsize'))]
                        avg_size = sum(sizes) / len(sizes) if sizes else 0
                        
                        norm_text = ' '.join(line_text.split())
                        if is_bold:
                            bold_lines.add(norm_text)
                        if is_upper and (avg_size >= 13.5 or len(norm_text) < 100): # heuristic for titles
                            uppercase_lines.add(norm_text)

        except Exception as e:
            logger.warning(f"Failed to extract styles from {pdf_path}: {e}")

        return {'bold': bold_lines, 'uppercase': uppercase_lines}

    def extract_bold_lines(self, pdf_path: str, max_pages: int = 3) -> Dict[int, List[str]]:
        """Deprecated: Use extract_styles instead."""
        styles = self.extract_styles(pdf_path, max_pages)
        # Convert set back to dict-of-list for backward compatibility if needed, 
        # but internal usage handles sets now.
        return {0: list(styles['bold'])}

    def extract_uppercase_titles(self, pdf_path: str, min_size: float = 14.0, max_size: float = 16.0, size_tolerance: float = 0.5, max_pages: int = 3) -> Dict[int, List[tuple]]:
        """Deprecated: Use extract_styles instead."""
        styles = self.extract_styles(pdf_path, max_pages)
        return {0: [(t, 0.0) for t in styles['uppercase']]}


    def extract_text_from_pdf(self, pdf_path: str, progress_callback=None, force_ocr: bool = False, max_ocr_pages: int = 5) -> List[str]:
        """Trích xuất văn bản thuần từ file PDF, mỗi phần tử là text của một trang.

        If PyPDF2 is present we attempt native text extraction first. If that
        returns no pages (or `force_ocr` is True) and OCR is enabled on this
        processor instance, we will attempt an image->OCR fallback using
        pdf2image + pytesseract.
        
        Args:
            max_ocr_pages: Maximum number of pages to OCR (optimization: usually metadata is on first few pages)
        """
        page_texts: List[str] = []
        total_pages: int = 0
        if PdfReader is None:
            logger.error("PyPDF2 unavailable: cannot extract text from PDF (native): %s", pdf_path)
        else:
            try:
                with open(pdf_path, "rb") as f:
                    reader = PdfReader(f)
                    total_pages = len(reader.pages)
                    # OPTIMIZATION: limit pages for faster processing
                    pages_to_check = min(total_pages, max_ocr_pages) if not force_ocr else total_pages
                    
                    for page_number, page in enumerate(reader.pages[:pages_to_check], start=1):
                        try:
                            text = page.extract_text()
                            if text:
                                page_texts.append(text.strip())
                            else:
                                # keep placeholder to preserve page count
                                page_texts.append("")
                                logger.debug(f"[{pdf_path}] Trang {page_number} không có text (native extraction).")
                            # report per-page progress if callback provided
                            if callable(progress_callback):
                                try:
                                    progress_callback({
                                        'type': 'page_progress',
                                        'file': pdf_path,
                                        'page': page_number,
                                        'total_pages': total_pages
                                    })
                                except Exception:
                                    # never allow callback errors to break extraction
                                    logger.exception("Progress callback raised an exception")
                        except Exception as e:
                            logger.error(f"Lỗi đọc trang {page_number} của {pdf_path}: {e}")
                    
                    # Pad remaining pages as empty (don't try to read them)
                    if pages_to_check < total_pages and not force_ocr:
                        page_texts.extend([""] * (total_pages - pages_to_check))
                        
            except Exception as e:
                logger.error(f"Lỗi mở file PDF {pdf_path}: {e}")

        # If no text was recovered (or force_ocr requested) and OCR is enabled,
        # attempt OCR as a fallback using pdf2image + pytesseract.
        should_try_ocr = (force_ocr or not any(t.strip() for t in page_texts)) and self.ocr_enabled
        if should_try_ocr:
            logger.info("[OCR] No usable text found, switching to OCR for %s (force_ocr=%s, ocr_enabled=%s)", pdf_path, force_ocr, self.ocr_enabled)
            # Nếu biết tổng số trang từ PyPDF2, ưu tiên OCR toàn bộ để chính xác hơn
            max_pages_for_ocr = total_pages if total_pages > 0 else max_ocr_pages
            ocr_texts = self._ocr_pdf(pdf_path, dpi=self.ocr_dpi, progress_callback=progress_callback, max_pages=max_pages_for_ocr)
            # If OCR returned something, prefer it. If both native and OCR exist,
            # use OCR for pages that were empty from native extraction.
            if ocr_texts:
                logger.info(f"[OCR] OCR extracted {sum(1 for t in ocr_texts if t.strip())}/{len(ocr_texts)} pages for {pdf_path}")
                if len(ocr_texts) == len(page_texts):
                    page_texts = [o or n for o, n in zip(ocr_texts, page_texts)]
                else:
                    # differing page counts: prefer OCR results
                    page_texts = ocr_texts
        else:
            logger.info(f"[OCR] Native text extraction succeeded for {pdf_path}: {sum(1 for t in page_texts if t.strip())}/{len(page_texts)} pages")

        return page_texts

    def _ocr_pdf(self, pdf_path: str, dpi: int = 300, progress_callback=None, max_pages: int = 5) -> List[str]:
        """Perform OCR on first N pages of a PDF using pdf2image + pytesseract.

        Returns a list of page texts (empty strings for pages that failed OCR).
        
        Args:
            max_pages: Maximum number of pages to OCR (optimization)
        """
        page_texts: List[str] = []
        try:
            from pdf2image import convert_from_path
        except Exception:
            logger.error("pdf2image is not available; install pdf2image to enable OCR fallback.")
            return page_texts

        try:
            from PIL import Image, ImageOps
        except Exception:
            logger.error("Pillow is not available; install pillow to enable OCR preprocessing.")
            return page_texts

        try:
            import pytesseract
            if self.tesseract_cmd:
                # pytesseract exposes pytesseract.pytesseract.tesseract_cmd
                try:
                    pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
                except Exception:
                    # best-effort only
                    logger.debug("Could not set pytesseract.tesseract_cmd")
        except Exception:
            logger.error("pytesseract is not available; install pytesseract to enable OCR fallback.")
            return page_texts

        try:
            # Với max_pages lớn hơn số trang thực tế, pdf2image sẽ tự dừng lại.
            # Không thay đổi DPI, chỉ tăng số trang OCR để nâng độ chính xác.
            images = convert_from_path(pdf_path, dpi=dpi, poppler_path=self.poppler_path, first_page=1, last_page=max_pages)
        except Exception as e:
            logger.exception("pdf2image failed to render PDF %s: %s", pdf_path, e)
            return page_texts

        total_pages = len(images)
        for idx, img in enumerate(images, start=1):
            try:
                # Cache check: use file hash + page number as key
                cache_key = f"{pdf_path}:page:{idx}"
                if cache_key in self._cache:
                    page_texts.append(self._cache[cache_key])
                    if callable(progress_callback):
                        try:
                            progress_callback({'type': 'page_ocr', 'file': pdf_path, 'page': idx, 'total_pages': total_pages, 'cached': True})
                        except Exception:
                            pass
                    continue
                
                # Tiền xử lý ưu tiên độ chính xác: giữ ảnh xám + autocontrast,
                # không nhị phân quá mạnh để tránh mất nét chữ.
                gray = img.convert("L")
                enhanced = ImageOps.autocontrast(gray)

                # For the first page, use block-based OCR to separate header columns
                if idx == 1:
                    text = self._ocr_with_blocks(enhanced)
                elif self.ocr_engine == 'windows':
                    import asyncio
                    try:
                        import winocr
                        # Map lang code 'vie' to Windows 'vi-VN'
                        win_lang = 'vi-VN' if 'vie' in (self.ocr_lang or '').lower() else 'en-US'
                        # winocr allows passing PIL image directly
                        result = asyncio.run(winocr.recognize_pil(enhanced, lang=win_lang))
                        text = result.text
                    except (ImportError, Exception) as e:
                        logger.error(f"Windows OCR error (falling back to Tesseract if possible): {e}")
                        # Fallback to Tesseract if Windows OCR fails
                        if self.ocr_lang:
                            text = pytesseract.image_to_string(enhanced, lang=self.ocr_lang, config="--psm 3")
                        else:
                            text = pytesseract.image_to_string(enhanced, config="--psm 3")
                else:
                    if self.ocr_lang:
                        text = pytesseract.image_to_string(enhanced, lang=self.ocr_lang, config="--psm 3")
                    else:
                        text = pytesseract.image_to_string(enhanced, config="--psm 3")

                text = text.strip()
                page_texts.append(text)
                
                # Cache the result
                if self._use_cache:
                    self._cache[cache_key] = text
                
                if callable(progress_callback):
                    try:
                        progress_callback({'type': 'page_ocr', 'file': pdf_path, 'page': idx, 'total_pages': total_pages})
                    except Exception:
                        logger.exception("Progress callback raised during OCR page callback")
            except Exception as e:
                logger.exception("Error OCRing page %d of %s: %s", idx, pdf_path, e)
                page_texts.append("")

        # Save cache after batch OCR
        if self._use_cache:
            self._save_cache()
        
        return page_texts

    def _ocr_with_blocks(self, image) -> str:
        """OCR based on geometric blocks to separate left and right headers.
        
        This handles the typical Vietnamese administrative layout:
        [Agency Header (Left)] | [Motto & Date (Right)]
        -----------------------------------------------
        [Document Title & Body (Bottom)]
        """
        import pytesseract
        width, height = image.size
        
        # Define areas:
        # Header is usually in the top 25-30% of the page
        header_height = int(height * 0.28)
        
        # Left block (Agency): Left 48% (with a small gap in middle)
        left_header_box = (0, 0, int(width * 0.48), header_height)
        # Right block (Motto): Right 48%
        right_header_box = (int(width * 0.52), 0, width, header_height)
        # Body: Rest of the page
        body_box = (0, header_height, width, height)
        
        blocks = []
        
        # OCR Left Header
        left_crop = image.crop(left_header_box)
        left_text = pytesseract.image_to_string(left_crop, lang=self.ocr_lang, config="--psm 6").strip()
        if left_text:
            blocks.append("[BLOCK: HEADER_LEFT]\n" + left_text)
            
        # OCR Right Header
        right_crop = image.crop(right_header_box)
        right_text = pytesseract.image_to_string(right_crop, lang=self.ocr_lang, config="--psm 6").strip()
        if right_text:
            blocks.append("[BLOCK: HEADER_RIGHT]\n" + right_text)
            
        # OCR Body
        body_crop = image.crop(body_box)
        body_text = pytesseract.image_to_string(body_crop, lang=self.ocr_lang, config="--psm 3").strip()
        if body_text:
            blocks.append("[BLOCK: MAIN_BODY]\n" + body_text)
            
        return "\n\n".join(blocks)

    def check_text_density(self, text: str, threshold: float = 0.05) -> bool:
        """Kiểm tra mật độ văn bản để xác định xem file có cần OCR không.
        
        Args:
            text: Toàn bộ nội dung text của file.
            threshold: Tỷ lệ ký tự chữ/số trên tổng độ dài (hoặc tiêu chí khác).
                       Ở đây dùng heuristic đơn giản: nếu text quá ngắn hoặc ít ký tự alphabetic -> return False (bad text).
        """
        if not text:
            return False
            
        # Loại bỏ khoảng trắng
        clean = re.sub(r"\s+", "", text)
        if len(clean) < 50: # Quá ít ký tự -> coi như ảnh/scan
            return False
            
        # Đếm số ký tự chữ cái
        alpha = sum(1 for c in clean if c.isalnum())
        if len(clean) > 0 and (alpha / len(clean)) < threshold:
             return False # Rác hoặc mã hóa lỗi
             
        return True

    def generate_searchable_pdf(self, input_path: str, output_path: str, lang: str = 'vie+eng') -> bool:
        """Tạo file PDF có thể search được từ file gốc (OCR sandwich).
        
        Sử dụng pdf2image để convert sang ảnh, sau đó dùng pytesseract.image_to_pdf_or_hocr
        để lấy PDF data ghép lại.
        """
        try:
            from pdf2image import convert_from_path
            import pytesseract
            if self.tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        except ImportError:
            logger.error("Missing dependencies (pdf2image, pytesseract) for OCR PDF generation.")
            return False

        try:
            logger.info(f"Generating searchable PDF for: {input_path}")
            
            # Convert PDF to images
            images = convert_from_path(input_path, dpi=self.ocr_dpi, poppler_path=self.poppler_path)
            
            if not images:
                logger.warning("No images extracted from PDF.")
                return False

            if PdfMerger is None:
                logger.error("PyPDF2 missing, cannot merge pages.")
                return False

            merger = PdfMerger()
            
            # Process each page
            for i, img in enumerate(images):
                # Convert image to PDF page using Tesseract
                # 'pdf' extension tells tesseract to return a PDF byte string
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf', lang=lang, config=f"--psm 3")
                
                # Write to temp file to load with PdfReader (merger needs streams or files)
                # Or use io.BytesIO
                import io
                f = io.BytesIO(pdf_bytes)
                merger.append(f)

            # Write output
            with open(output_path, "wb") as fout:
                merger.write(fout)
            merger.close()
            
            logger.info(f"Searchable PDF saved to: {output_path}")
            return True
            
        except Exception as e:
            logger.exception(f"Failed to generate searchable PDF for {input_path}: {e}")
            return False

    def process_pdf(self, input_path: str, progress_callback=None, force_ocr: bool = False, max_ocr_pages: int = 5) -> Tuple[str, List[str]]:
        """Xử lý 1 file PDF và trả về tuple (đường dẫn, danh sách text các trang).

        Args:
            force_ocr: If True, attempt OCR even if native extraction returned text.
            max_ocr_pages: Maximum pages to OCR for speed optimization
        """
        if callable(progress_callback):
            try:
                progress_callback({'type': 'file_start', 'file': input_path})
            except Exception:
                logger.exception("Progress callback raised during file_start")

        texts = self.extract_text_from_pdf(input_path, progress_callback=progress_callback, force_ocr=force_ocr, max_ocr_pages=max_ocr_pages)

        if callable(progress_callback):
            try:
                progress_callback({'type': 'file_done', 'file': input_path, 'texts': texts})
            except Exception:
                logger.exception("Progress callback raised during file_done")
        return input_path, texts

    def extract_and_metadata(self, pdf_path: str, force_ocr: bool = False, max_ocr_pages: int = 5) -> Dict[str, str]:
        """Extract text and metadata from PDF in a single integrated pipeline.
        
        Optimized: Combined style extraction and text extraction.
        """
        logger.info(f"Starting metadata extraction pipeline for: {pdf_path}")
        
        # Step 1: Extract visual styles (Bold, Uppercase) - FAST PASS
        # Usually metadata is on the first 1-2 pages.
        styles = self.extract_styles(pdf_path, max_pages=3)
        bold_lines = styles['bold']
        uppercase_lines = styles['uppercase']

        # Step 2: Extract text from PDF
        try:
            page_texts = self.extract_text_from_pdf(
                pdf_path,
                force_ocr=force_ocr,
                max_ocr_pages=max_ocr_pages
            )
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return {}
        
        if not page_texts or all(not t.strip() for t in page_texts):
            logger.warning(f"No text extracted from {pdf_path}")
            return {}
        
        # Step 3: Apply Markdown formatting for better extraction context
        formatted_pages = []
        for p_idx, text in enumerate(page_texts):
            if not text:
                formatted_pages.append("")
                continue
            
            lines = text.splitlines()
            formatted_lines = []
            for ln in lines:
                clean_ln = ' '.join(ln.split())
                if not clean_ln:
                    formatted_lines.append("")
                    continue
                
                # Check if this line was detected as bold or uppercase title
                is_bold = clean_ln in bold_lines
                is_upper = clean_ln in uppercase_lines
                
                if is_bold and is_upper:
                    formatted_lines.append(f"# **{ln}**")
                elif is_bold:
                    formatted_lines.append(f"**{ln}**")
                elif is_upper and len(clean_ln) < 100:
                    formatted_lines.append(f"# {ln}")
                else:
                    formatted_lines.append(ln)
            formatted_pages.append("\n".join(formatted_lines))

        full_text_md = "\n".join(t for t in formatted_pages if t)
        
        # Step 4: Extract metadata directly from formatted text
        try:
            metadata = extract_metadata(full_text_md, bold_lines=bold_lines, uppercase_titles=uppercase_lines)
            
            # USER REQUEST: Skip invalid documents (fragments, no metadata, no signature indicators)
            if not metadata.get('is_valid', True):
                logger.info(f"Skipping document {pdf_path}: Insufficient metadata found (not a valid legal document)")
                return {} # Return empty for invalid documents as requested
                
        except Exception as e:
            logger.error(f"Metadata extraction failed: {e}")
            # Try once without extra params
            try:
                metadata = extract_metadata(full_text_md)
                if not metadata.get('is_valid', True):
                    return {}
            except:
                return {}

        metadata['duong_dan_file'] = str(Path(pdf_path).absolute())
        metadata['markdown_text'] = full_text_md
        
        logger.info(f"Metadata extraction complete for {pdf_path}")
        return metadata


    def process_directory(self, input_dir: str, recursive: bool = False, max_workers: int = 4, progress_callback=None, force_ocr: bool = False, max_ocr_pages: int = 5) -> List[Tuple[str, List[str]]]:
        """Xử lý toàn bộ file PDF trong thư mục (và thư mục con nếu recursive=True).
        
        Args:
            max_workers: Number of parallel workers for processing
            max_ocr_pages: Max pages to OCR per file
        """
        input_dir = Path(input_dir)
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(input_dir.glob(pattern))
        results = []

        if not pdf_files:
            logger.warning(f"Không tìm thấy file PDF trong thư mục: {input_dir}")
            return results

        # For single or few files, use direct processing
        total_files = len(pdf_files)
        if total_files <= 1 or max_workers <= 1:
            # Direct sequential processing
            for idx, pdf_file in enumerate(pdf_files, start=1):
                pdf_path = str(pdf_file)
                try:
                    logger.info(f"Đang trích xuất: {pdf_path}")
                    if callable(progress_callback):
                        try:
                            progress_callback({'type': 'file_start', 'file': pdf_path, 'index': idx, 'total': total_files})
                        except Exception:
                            logger.exception("Progress callback raised during file_start")

                    _, texts = self.process_pdf(pdf_path, progress_callback=progress_callback, force_ocr=force_ocr, max_ocr_pages=max_ocr_pages)
                    results.append((pdf_path, texts))

                    if callable(progress_callback):
                        try:
                            progress_callback({'type': 'file_done', 'file': pdf_path, 'index': idx, 'total': total_files})
                            progress_callback({'type': 'progress', 'value': int((idx / total_files) * 100)})
                        except Exception:
                            logger.exception("Progress callback raised during file_done/progress")
                except Exception as e:
                    logger.error(f"Lỗi xử lý file {pdf_file}: {e}")
                    if callable(progress_callback):
                        try:
                            progress_callback({'type': 'file_error', 'file': pdf_path, 'error': str(e)})
                        except Exception:
                            logger.exception("Progress callback raised during file_error")
        else:
            # Parallel processing with ThreadPoolExecutor (lighter than ProcessPoolExecutor)
            from concurrent.futures import ThreadPoolExecutor
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for idx, pdf_file in enumerate(pdf_files, start=1):
                    pdf_path = str(pdf_file)
                    try:
                        logger.info(f"Queuing: {pdf_path} ({idx}/{total_files})")
                        if callable(progress_callback):
                            try:
                                progress_callback({'type': 'file_start', 'file': pdf_path, 'index': idx, 'total': total_files})
                            except Exception:
                                logger.exception("Progress callback raised during file_start")
                        
                        # Submit task
                        future = executor.submit(self.process_pdf, pdf_path, None, force_ocr, max_ocr_pages)
                        futures[future] = (pdf_path, idx)
                    except Exception as e:
                        logger.error(f"Error queueing {pdf_file}: {e}")
                
                # Process completed futures
                from concurrent.futures import as_completed
                for future in as_completed(futures):
                    pdf_path, idx = futures[future]
                    try:
                        _, texts = future.result()
                        results.append((pdf_path, texts))
                        if callable(progress_callback):
                            try:
                                progress_callback({'type': 'file_done', 'file': pdf_path, 'index': idx, 'total': total_files})
                                progress_callback({'type': 'progress', 'value': int((idx / total_files) * 100)})
                            except Exception:
                                logger.exception("Progress callback raised during file_done/progress")
                    except Exception as e:
                        logger.error(f"Error processing {pdf_path}: {e}")
                        if callable(progress_callback):
                            try:
                                progress_callback({'type': 'file_error', 'file': pdf_path, 'error': str(e)})
                            except Exception:
                                logger.exception("Progress callback raised during file_error")

        return results


def process_pdf(path: str, force_ocr: bool = False, max_ocr_pages: int = 5) -> Dict[str, str]:
    """Extract text and metadata from a PDF file (convenience API).

    Pipeline:
    1. Extract text from PDF (native text + OCR fallback for scanned pages)
    2. Clean text (normalize Unicode, fix OCR artifacts, collapse whitespace)
    3. Extract metadata using metadata_extractor
    4. Return metadata dict

    Args:
        path: Path to PDF file
        force_ocr: Force OCR even if native text is available
        max_ocr_pages: Maximum pages to process with OCR

    Returns:
        Dict with extracted metadata fields (co_quan_ban_hanh, so_van_ban, etc.)
    """
    try:
        from .config import OCR_ENGINE
    except ImportError:
        try:
            from config import OCR_ENGINE
        except ImportError:
            OCR_ENGINE = 'tesseract'
            
    processor = PDFProcessor(ocr_engine=OCR_ENGINE)
    
    # Step 1: Extract text from PDF
    logger.info(f"Extracting text from: {path}")
    page_texts = processor.extract_text_from_pdf(
        path, 
        force_ocr=force_ocr, 
        max_ocr_pages=max_ocr_pages
    )
    
    # Combine all pages into one document
    full_text = "\n".join(t for t in page_texts if t)
    if not full_text.strip():
        logger.warning(f"No text extracted from {path}")
        return {}
    
    # Step 2: Extract metadata directly from raw text
    logger.debug("Extracting metadata...")
    metadata = extract_metadata(full_text)
    
    # Extract 'Số hồ sơ' from filename - DISABLED per user request
    # # Logic: First part before '-' (e.g. 9-52-52 -> 9, 9-0001 -> 9)
    # try:
    #     filename = os.path.basename(path)
    #     name_no_ext = os.path.splitext(filename)[0]
    #     first_part = name_no_ext.split('-')[0]
    #     # Remove potential whitespace and ensure it's treated as a number to remove leading zeros
    #     # then convert back to string.
    #     # Check digit on the stripped part
    #     if first_part.strip().isdigit():
    #          metadata['so_ho_so'] = str(int(first_part.strip()))
    #     else:
    #          metadata['so_ho_so'] = first_part.strip()
    # except Exception as e:
    #     logger.warning(f"Could not extract dossier number from filename {path}: {e}")
    #     metadata['so_ho_so'] = ""
    metadata['so_ho_so'] = "" # Leave empty for manual entry

    metadata['duong_dan_file'] = str(Path(path).absolute())
    logger.info(f"Successfully extracted metadata: so_van_ban={metadata.get('so_van_ban')}, "
                f"ky_hieu={metadata.get('ky_hieu_van_ban')}")
    return metadata

# Do not instantiate a module-level processor here — leave creation to callers.
# Example usage (in application code):
# processor = PDFProcessor()
# processor_with_poppler = PDFProcessor(poppler_path="C:/path/to/poppler")
