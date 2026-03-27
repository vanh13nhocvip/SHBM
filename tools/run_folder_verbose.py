r"""Run verbose extraction over a directory of PDFs.

Usage:
  python tools/run_folder_verbose.py "E:\path\to\pdf_folder"

Outputs:
  - tools/out_verbose.json
  - tools/out_verbose.xlsx

This script sets logging to DEBUG and prints per-file decisions.
"""
import sys
import os
import json
import logging
from pathlib import Path

from src.config import get_poppler_path
from src.pdf_processor import PDFProcessor
from src.metadata_extractor import MetadataExtractor
from src.excel_exporter import ExcelExporter


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_folder_verbose.py <pdf_folder>")
        sys.exit(1)

    folder = Path(sys.argv[1])
    if not folder.exists() or not folder.is_dir():
        print(f"Folder not found: {folder}")
        sys.exit(2)

    # Configure logging for verbose output
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    logger = logging.getLogger('tools.run_folder_verbose')

    poppler = get_poppler_path()
    logger.debug('Using POPPLER_PATH: %s', poppler)

    proc = PDFProcessor(poppler_path=poppler, ocr_enabled=True)
    extractor = MetadataExtractor()
    exporter = ExcelExporter()

    # Process directory (will not parallelize here to keep logs sequential)
    results = proc.process_directory(str(folder), recursive=True, progress_callback=None, force_ocr=False)
    if not results:
        logger.warning('No PDFs found or nothing processed in folder: %s', folder)
        sys.exit(0)

    texts_by_file = {fp: pages for (fp, pages) in results}

    # collect styles per file
    all_styles = {}
    for fp in texts_by_file.keys():
        try:
            bold = proc.extract_bold_lines(fp) or {}
            upper = proc.extract_uppercase_titles(fp) or {}
            merged = {}
            page_set = set(list(bold.keys()) + list(upper.keys()))
            for p in page_set:
                merged[p] = []
                merged[p].extend(bold.get(p, []))
                merged[p].extend([t for t, _ in upper.get(p, [])])
            if merged:
                all_styles[fp] = merged
        except Exception:
            logger.exception('Failed to extract style hints for %s', fp)

    # Extract metadata
    logger.info('Running MetadataExtractor on %d files...', len(texts_by_file))
    metas = extractor.extract_from_directory(texts_by_file, base_dir=str(folder), processes=1, all_styles=all_styles)

    # Write JSON
    out_json = Path('tools') / 'out_verbose.json'
    with out_json.open('w', encoding='utf-8') as f:
        json.dump(metas, f, ensure_ascii=False, indent=2)
    logger.info('Wrote JSON: %s (items: %d)', out_json, len(metas))

    # Write Excel
    out_xlsx = Path('tools') / 'out_verbose.xlsx'
    try:
        exporter.export(metas, str(out_xlsx))
        logger.info('Wrote Excel: %s', out_xlsx)
    except Exception:
        logger.exception('Failed to write Excel output')

    # Print a short summary
    for m in metas:
        logger.debug('FILE METADATA: %s -> %s / %s / %s', m.get('duong_dan_file') or m.get('file') or 'unknown', m.get('so_van_ban'), m.get('ky_hieu_van_ban'), (m.get('trich_yeu_noi_dung') or '')[:120])


if __name__ == '__main__':
    main()
