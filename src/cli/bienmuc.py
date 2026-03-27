#!/usr/bin/env python3
"""Công cụ dòng lệnh: Biên mục PDF (làm sạch trang và trích xuất văn bản)

Usage:
    python -m src.cli.bienmuc --input path/to/file_or_dir [--save-texts]
"""
import argparse
import json
import logging
from pathlib import Path
from typing import List
import os

from ..config import POPPLER_PATH
from ..pdf_processor import PDFProcessor
from ..metadata_extractor import MetadataExtractor
from ..excel_exporter import ExcelExporter


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def save_texts(output_json: Path, texts_by_page: List[str]):
    with output_json.open('w', encoding='utf-8') as f:
        json.dump({'pages': texts_by_page}, f, ensure_ascii=False, indent=2)


def process_file(processor: PDFProcessor, input_path: Path, save_texts_flag: bool, output: Path = None, base_input: Path = None):
    """Process a single file. If `output` is provided it can be either a file path or directory.
    If `base_input` is provided then when `output` is a directory we preserve relative path from base_input.
    """
    # Determine output path
    if output:
        if output.exists() and output.is_dir():
            # preserve relative structure if base_input provided
            if base_input:
                rel = input_path.relative_to(base_input)
                out_dir = output / rel.parent
                out_dir.mkdir(parents=True, exist_ok=True)
                out_file = out_dir / f"{input_path.stem}_clean{input_path.suffix}"
            else:
                output.mkdir(parents=True, exist_ok=True)
                out_file = output / f"{input_path.stem}_clean{input_path.suffix}"
        else:
            # treat output as a file path
            out_file = output
            out_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        out_file = None

    if out_file:
        out_path, texts = processor.process_pdf(str(input_path), output_path=str(out_file))
    else:
        out_path, texts = processor.process_pdf(str(input_path))

    logging.info(f"Finished: {input_path} -> {out_path} (pages: {len(texts)})")
    if save_texts_flag:
        json_path = Path(out_path).with_suffix('.json')
        save_texts(json_path, texts)
        logging.info(f"Saved extracted texts: {json_path}")


def process_directory(processor: PDFProcessor, input_dir: Path, recursive: bool, save_texts_flag: bool, output_dir: Path = None):
    # If output_dir is None, delegate to processor.process_directory
    if not output_dir:
        results = processor.process_directory(str(input_dir), recursive=recursive)
        for in_file, out_file, texts in results:
            logging.info(f"Processed: {in_file} -> {out_file} (pages: {len(texts)})")
            if save_texts_flag:
                json_path = Path(out_file).with_suffix('.json')
                save_texts(json_path, texts)
                logging.info(f"Saved extracted texts: {json_path}")
        return

    # When output_dir provided, walk files and preserve relative structure
    pattern = '**/*.pdf' if recursive else '*.pdf'
    for pdf_path in input_dir.glob(pattern):
        try:
            process_file(processor, pdf_path, save_texts_flag, output=output_dir, base_input=input_dir)
        except Exception as e:
            logging.exception(f"Error processing {pdf_path}: {e}")


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description='Biên mục PDF - CLI')
    parser.add_argument('--input', '-i', required=True, help='File PDF hoặc thư mục chứa PDF')
    parser.add_argument('--dpi', type=int, default=300, help='DPI khi convert PDF -> ảnh')
    parser.add_argument('--recursive', action='store_true', help='Tìm kiếm đệ quy trong thư mục')
    parser.add_argument('--save-texts', action='store_true', help='Lưu text trích xuất ra file .json cạnh file gốc')
    parser.add_argument('--output', '-o', help='Output file or output directory. If directory, outputs will be written there preserving relative structure for directories')
    args = parser.parse_args()

    processor = PDFProcessor(poppler_path=POPPLER_PATH)
    p = Path(args.input)

    all_texts = {}

    if p.is_file():
        out_path, texts = processor.process_pdf(str(p))
        all_texts[str(p)] = texts
    elif p.is_dir():
        results = processor.process_directory(str(p), recursive=args.recursive)
        for in_file, out_file, texts in results:
            all_texts[in_file] = texts
    else:
        logging.error('Đường dẫn input không tồn tại')
        return

    # Optionally save per-file JSONs
    if args.save_texts:
        for infile, texts in all_texts.items():
            json_path = Path(infile).with_suffix('.json')
            save_texts(json_path, texts)
            logging.info(f"Saved texts: {json_path}")

    # Print extracted texts to stdout (for CLI usage)
    for infile, texts in all_texts.items():
        print(f"\n--- {infile} ---")
        for i, page_text in enumerate(texts, 1):
            print(f"[Page {i}]:\n{page_text}\n")
