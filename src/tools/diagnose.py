#!/usr/bin/env python
"""
Unified diagnostic tool for SHBM - verify environment, dependencies, and configuration.

Usage:
  python tools/diagnose.py
  python tools/diagnose.py --verbose
"""
import sys
import os
import shutil
import json
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def main():
    verbose = '--verbose' in sys.argv or '-v' in sys.argv
    
    print("\n" + "=" * 70)
    print("SHBM DIAGNOSTIC REPORT")
    print("=" * 70)
    
    # 1. Python Environment
    print("\n[1] Python Environment")
    print(f"  Executable: {sys.executable}")
    print(f"  Version: {sys.version.split()[0]}")
    print(f"  Platform: {sys.platform}")
    
    # 2. Project Structure
    print("\n[2] Project Structure")
    project_root = Path(__file__).parent.parent
    print(f"  Root: {project_root}")
    venv_exists = (project_root / "venv").exists()
    print(f"  Virtualenv: {'[OK]' if venv_exists else '[MISS]'}")
    
    # 3. Core Modules
    print("\n[3] Core Modules")
    required_modules = [
        "PyPDF2", "pdfplumber", "pandas", "openpyxl",
        "customtkinter", "pdf2image", "pytesseract", "PIL"
    ]
    missing = []
    for mod in required_modules:
        try:
            __import__(mod)
            print(f"  [OK] {mod}")
        except ImportError:
            print(f"  [XX] {mod} (missing)")
            missing.append(mod)
    
    if missing:
        print(f"\n  To install missing packages:")
        print(f"  {sys.executable} -m pip install {' '.join(missing)}")
    
    # 4. System Binaries
    print("\n[4] System Binaries")
    
    # Poppler
    from src.config import get_poppler_path, has_poppler
    poppler_path = get_poppler_path()
    has_poppler_bin = has_poppler()
    print(f"  Poppler Path: {poppler_path}")
    print(f"  Poppler Available: {'[OK]' if has_poppler_bin else '[XX]'}")
    if has_poppler_bin and verbose:
        pdfinfo = Path(poppler_path) / "pdfinfo.exe"
        print(f"    - pdfinfo.exe: {'[OK]' if pdfinfo.exists() else '[XX]'}")
    
    # Tesseract
    has_tesseract = bool(shutil.which('tesseract'))
    print(f"  Tesseract Available: {'[OK]' if has_tesseract else '[XX]'}")
    if not has_tesseract:
        print(f"    (needed for OCR on scanned PDFs; see src/tools/INSTALL_TESSERACT.md)")
    
    # 5. Source Files
    print("\n[5] Core Source Files")
    src_dir = project_root / "src"
    required_files = [
        "config.py", "pdf_processor.py", "metadata_extractor.py",
        "excel_exporter.py", "cli_metadata.py", "cli_bienmuc.py",
        "pdf_metadata_gui.py", "__init__.py", "__main__.py"
    ]
    for fname in required_files:
        fpath = src_dir / fname
        status = "[OK]" if fpath.exists() else "[XX]"
        print(f"  {status} {fname}")
    
    # 6. Configuration Files
    print("\n[6] Configuration Files")
    config_files = ["requirements.txt", "setup.py", "ideal.txt", "README.md"]
    for fname in config_files:
        fpath = project_root / fname
        status = "[OK]" if fpath.exists() else "[XX]"
        print(f"  {status} {fname}")
    
    # 7. Tool Scripts
    print("\n[7] Available Tool Scripts")
    tools_dir = project_root / "src" / "tools"
    tool_scripts = [
        "download_and_install_poppler.ps1",
        "test_performance.py",
        "test_exporter.py",
        "export_single_file.py",
        "run_extract_on_file.py",
        "run_folder_verbose.py"
    ]
    for fname in tool_scripts:
        fpath = tools_dir / fname
        status = "[OK]" if fpath.exists() else "[XX]"
        print(f"  {status} {fname}")
    
    # 8. Summary & Recommendations
    print("\n[8] Summary & Recommendations")
    issues = []
    
    if not venv_exists:
        issues.append("Create virtual environment: python -m venv venv")
    if missing:
        issues.append(f"Install missing packages: pip install {' '.join(missing)}")
    if not has_poppler_bin:
        issues.append("Install Poppler: PowerShell .\\src\\tools\\download_and_install_poppler.ps1")
    if not has_tesseract:
        issues.append("Install Tesseract (optional): see src/tools/INSTALL_TESSERACT.md")
    
    if issues:
        print("\n  [WARN] Issues Found:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        print("\n  [OK] All checks passed! Environment is ready.")
    
    # 9. Quick Tests (if verbose)
    if verbose:
        print("\n[9] Quick Functional Tests")
        try:
            from src.pdf_processor import PDFProcessor
            from src.metadata_extractor import MetadataExtractor
            from src.excel_exporter import ExcelExporter
            print("  [OK] All core modules import successfully")
        except Exception as e:
            print(f"  [XX] Import error: {e}")
    
    print("\n" + "=" * 70)
    print("End of diagnostic report\n")


if __name__ == "__main__":
    main()
