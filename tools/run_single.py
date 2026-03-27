#!/usr/bin/env python3
"""Run extraction on a single PDF and show brief diagnostics.

This unified runner replaces older helper scripts like export_single_file.py
and run_extract_on_file.py. It:
 - prints POPPLER_PATH and Tesseract availability
 - extracts text (native + OCR fallback)
 - prints snippets from first pages
 - runs metadata extraction and prints JSON result

Usage:
    python tools/run_single.py <path/to/file.pdf>
"""
import sys
import os
import json
import shutil
from pathlib import Path

# Ensure package sources are importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

try:
    from src import config
    from src.pdf_processor import PDFProcessor
    from src.metadata_extractor import extract_metadata
except Exception as e:
    print("Failed to import project modules:", e)
    sys.exit(2)


def main():
    if len(sys.argv) < 2:
        print("Usage: python tools/run_single.py <pdf_path>")
        sys.exit(1)

    pdf = sys.argv[1]
    if not os.path.exists(pdf):
        print(f"File not found: {pdf}")
        sys.exit(2)

    print('PDF:', pdf)
    try:
        poppler = config.get_poppler_path()
        print('POPPLER_PATH (config):', poppler)
        print('POPPLER exists:', os.path.exists(poppler))
    except Exception:
        print('POPPLER info unavailable')

    print('Tesseract on PATH:', bool(shutil.which('tesseract')))

    proc = PDFProcessor(poppler_path=config.get_poppler_path(), ocr_enabled=True)
    try:
        path, texts = proc.process_pdf(pdf, progress_callback=None, force_ocr=False)
    except Exception as e:
        print('PDFProcessor raised:', repr(e))
        sys.exit(3)

    non_empty = sum(1 for t in texts if t and t.strip())
    print(f'Pages extracted: {len(texts)} (non-empty: {non_empty})')
    if texts:
        for i, t in enumerate(texts[:3], start=1):
            snippet = (t[:400] + '...') if t and len(t) > 400 else (t or '')
            print(f'--- Page {i} snippet ---\n{snippet}\n')

    full_text = "\n".join(t for t in texts if t)
    try:
        metadata = extract_metadata(full_text)
    except Exception as e:
        print('Metadata extractor raised:', repr(e))
        sys.exit(4)

    # Augment with path and print
    metadata['duong_dan_file'] = str(Path(pdf).absolute())
    print('\nExtracted metadata:')
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
