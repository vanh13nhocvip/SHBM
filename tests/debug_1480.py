
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from pdf_processor import PDFProcessor
from metadata_extractor import extract_metadata

def debug_file():
    proc = PDFProcessor()
    # Path to sample
    pdf_path = os.path.join("samples", "1480-01-01.pdf")
    if not os.path.exists(pdf_path):
        print(f"File not found: {pdf_path}")
        return

    print(f"Extracting text from {pdf_path}...")
    _, texts = proc.process_pdf(pdf_path)
    full_text = "\n".join(texts)
    
    meta = extract_metadata(full_text)
    print("EXTRACTED METADATA:")
    for k, v in meta.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    debug_file()
