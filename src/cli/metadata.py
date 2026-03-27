#!/usr/bin/env python3
"""CLI for extracting metadata from PDFs.

Usage: python -m src.cli.metadata extract <pdf_folder> --out output.xlsx
"""
import argparse
import sys
import json
import csv
import logging
from pathlib import Path
from typing import Dict, List

from ..metadata_extractor import MetadataExtractor
from ..pdf_processor import PDFProcessor, process_pdf
from ..config import get_poppler_path, TESSERACT_CMD, OCR_LANG
from ..excel_exporter import ExcelExporter


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def metadata_to_dict_list(metas) -> List[Dict]:
    rows = []
    def val(src, *keys):
        for k in keys:
            if isinstance(src, dict):
                v = src.get(k)
            else:
                v = getattr(src, k, None)
            if v:
                return v
        return ''

    for m in metas:
        rows.append({
            'Cơ quan ban hành': val(m, 'co_quan_ban_hanh', 'co_quan'),
            'Số văn bản': val(m, 'so_van_ban', 'so_van'),
            'Ký hiệu': val(m, 'ky_hieu_van_ban', 'ky_hieu'),
            'Ngày ký': val(m, 'ngay_ky', 'ngay'),
            'Thể loại văn bản': val(m, 'the_loai_van_ban'),
            'Trích yếu nội dung văn bản': val(m, 'trich_yeu_noi_dung', 'trich_yeu'),
            'Người Ký': val(m, 'nguoi_ky'),
            'Loại văn bản': val(m, 'loai_ban', 'loai_van_ban'),
            'Trang Số': val(m, 'trang_so'),
            'Số trang': val(m, 'so_trang_van_ban', 'so_trang'),
            'Địa chỉ tài liệu gốc': val(m, 'dia_chi_tai_lieu_goc', 'duong_dan', 'duong_dan_file'),
            'Người nhập tin': ''
        })
    return rows


def write_json(path: Path, data):
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, rows: List[Dict]):
    if not rows:
        return
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def process_and_extract(processor: PDFProcessor, extractor: MetadataExtractor, input_path: Path, recursive: bool):
    texts_by_file = {}
    styles_by_file = {}
    if input_path.is_file():
        _, texts = processor.process_pdf(str(input_path))
        texts_by_file[str(input_path)] = texts
        # collect style hints (bold lines and uppercase title-like lines)
        try:
            bold = processor.extract_bold_lines(str(input_path)) or {}
            upper = processor.extract_uppercase_titles(str(input_path)) or {}
            merged = {}
            page_set = set(list(bold.keys()) + list(upper.keys()))
            for p in page_set:
                merged[p] = []
                merged[p].extend(bold.get(p, []))
                merged[p].extend([t for t, _ in upper.get(p, [])])
            if merged:
                styles_by_file[str(input_path)] = merged
        except Exception:
            pass
    else:
        results = processor.process_directory(str(input_path), recursive=recursive)
        for in_file, out_file, texts in results:
            texts_by_file[in_file] = texts
            try:
                bold = processor.extract_bold_lines(in_file) or {}
                upper = processor.extract_uppercase_titles(in_file) or {}
                merged = {}
                page_set = set(list(bold.keys()) + list(upper.keys()))
                for p in page_set:
                    merged[p] = []
                    merged[p].extend(bold.get(p, []))
                    merged[p].extend([t for t, _ in upper.get(p, [])])
                if merged:
                    styles_by_file[in_file] = merged
            except Exception:
                pass

    # return collected texts and styles for further processing
    return texts_by_file, styles_by_file


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description='Trích xuất metadata từ PDF (CLI)')
    subparsers = parser.add_subparsers(dest='command')

    # Legacy single-invocation parser (keeps previous behaviour)
    legacy = subparsers.add_parser('run', help='Legacy run mode (keeping old flags)')
    legacy.add_argument('--input', '-i', required=True, help='File PDF hoặc thư mục chứa PDF')
    legacy.add_argument('--output', '-o', default='metadata.json', help='File output (json or csv)')
    legacy.add_argument('--format', choices=['json', 'csv', 'excel'], default='json', help='Định dạng output')
    legacy.add_argument('--recursive', action='store_true', help='Tìm kiếm đệ quy trong thư mục')
    legacy.add_argument('--api-mode', choices=['local_rules'], default='local_rules', help='Chế độ xử lý text: hiện chỉ hỗ trợ chế độ luật cục bộ (local_rules)')

    # New: shbm extract <pdf_folder> --out output.xlsx
    extract = subparsers.add_parser('extract', help='Scan folder and extract metadata per-PDF and write to Excel')
    extract.add_argument('pdf_folder', help='File hoặc thư mục chứa PDF để trích xuất')
    extract.add_argument('--out', '-o', required=True, help='Đường dẫn output .xlsx')
    extract.add_argument('--recursive', '-r', action='store_true', help='Tìm kiếm đệ quy trong thư mục')
    extract.add_argument('--ocr', action='store_true', help='Force OCR for all files')

    # If user calls module without subcommand, preserve legacy behaviour by expecting the legacy flags
    if len(sys.argv) == 1:
        parser.print_help()
        return

    args = parser.parse_args()

    # Create processor and pass configured poppler & Tesseract so OCR (pdf2image + pytesseract) dùng đúng model
    processor = PDFProcessor(
        poppler_path=get_poppler_path(),
        ocr_enabled=True,
        tesseract_cmd=TESSERACT_CMD,
        ocr_dpi=300,
        ocr_lang=OCR_LANG,
        use_cache=True,
    )
    extractor = MetadataExtractor()

    # Handle subcommands
    if args.command == 'extract':
        p = Path(args.pdf_folder)
        if not p.exists():
            logging.error('Đường dẫn input không tồn tại')
            return

        # Collect pdf files
        if p.is_file() and p.suffix.lower() == '.pdf':
            pdfs = [p]
        elif p.is_dir():
            if args.recursive:
                pdfs = sorted([x for x in p.rglob('*.pdf')])
            else:
                pdfs = sorted([x for x in p.glob('*.pdf')])
        else:
            logging.error('Không có file PDF hợp lệ')
            return

        if not pdfs:
            logging.info('Không tìm thấy file PDF nào để xử lý')
            return

        metas = []
        total = len(pdfs)
        for idx, fp in enumerate(pdfs, start=1):
            logging.info(f'[{idx}/{total}] Processing: {fp}')
            try:
                md = process_pdf(str(fp), force_ocr=bool(args.ocr))
                if md:
                    metas.append(md)
            except Exception:
                logging.exception(f'Failed to process {fp}')

        # Export to Excel using ExcelExporter
        out_path = Path(args.out)
        if out_path.suffix.lower() != '.xlsx':
            out_path = out_path.with_suffix('.xlsx')
        exporter = ExcelExporter()
        exporter.export(metas, str(out_path))
        logging.info(f'Wrote metadata Excel: {out_path} (items: {len(metas)})')
        return

    # Legacy run: map args from legacy parser
    # argparse places legacy args under 'run' namespace if used; handle both cases
    if args.command == 'run' or args.command is None:
        # If used as subcommand 'run', attributes are under args
        if hasattr(args, 'input'):
            input_arg = args.input
            output_arg = getattr(args, 'output', 'metadata.json')
            fmt = getattr(args, 'format', 'json')
            recursive = getattr(args, 'recursive', False)
            api_mode = getattr(args, 'api_mode', 'local_rules')
        else:
            logging.error('No input provided for legacy run mode')
            return

        p = Path(input_arg)
        if not p.exists():
            logging.error('Đường dẫn input không tồn tại')
            return

        texts_by_file, styles_by_file = process_and_extract(processor, extractor, p, recursive)

        # Currently no external AI cleaning mode is available; texts are passed
        # directly to the local rule-based extractor.

        try:
            if styles_by_file:
                metas = extractor.extract_from_directory(texts_by_file, base_dir=str(p), all_styles=styles_by_file)
            else:
                metas = extractor.extract_from_directory(texts_by_file, base_dir=str(p))
        except Exception:
            metas = extractor.extract_from_directory(texts_by_file, base_dir=str(p))

        rows = metadata_to_dict_list(metas)

        out_path = Path(output_arg)
        if fmt == 'json':
            write_json(out_path, rows)
            logging.info(f"Wrote metadata JSON: {out_path} (items: {len(rows)})")
        elif fmt == 'csv':
            write_csv(out_path, rows)
            logging.info(f"Wrote metadata CSV: {out_path} (items: {len(rows)})")
        else:
            # Excel export: use ExcelExporter and pass the original DocumentMetadata list
            exporter = ExcelExporter()
            # Ensure .xlsx extension
            if out_path.suffix.lower() != '.xlsx':
                out_path = out_path.with_suffix('.xlsx')
            exporter.export(metas, str(out_path))
            logging.info(f"Wrote metadata Excel: {out_path} (items: {len(rows)})")


if __name__ == '__main__':
    main()
