"""
Cấu hình toàn cục cho SHBM
"""
import os
import sys

def get_base_path():
    """Lấy đường dẫn gốc của ứng dụng (hỗ trợ PyInstaller)"""
    if getattr(sys, 'frozen', False):
        # Khi chạy từ file .exe của PyInstaller
        return sys._MEIPASS
    # Khi chạy từ mã nguồn (thư mục chứa src/)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

BASE_PATH = get_base_path()

# --- Poppler configuration ---
# Ưu tiên bản local trong src/tools/deps/poppler
local_poppler_bin = os.path.join(BASE_PATH, 'src', 'tools', 'deps', 'poppler', 'bin')
local_poppler_lib = os.path.join(BASE_PATH, 'src', 'tools', 'deps', 'poppler', 'Library', 'bin')

if os.path.exists(local_poppler_bin):
    POPPLER_PATH = local_poppler_bin
elif os.path.exists(local_poppler_lib):
    POPPLER_PATH = local_poppler_lib
else:
    # Fallback to absolute system path (if any)
    POPPLER_PATH = r"C:\Program Files (x86)\poppler-24.02.0\Library\bin"

def has_poppler():
    """Return True if the configured POPPLER_PATH exists on disk."""
    return bool(POPPLER_PATH and os.path.exists(POPPLER_PATH))

def get_poppler_path():
    return POPPLER_PATH

# --- OCR / Tesseract configuration ---
local_tesseract = os.path.join(BASE_PATH, 'src', 'tools', 'deps', 'tesseract', 'tesseract.exe')
if os.path.exists(local_tesseract):
    TESSERACT_CMD = local_tesseract
else:
    TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

OCR_LANG = os.environ.get('OCR_LANG', 'vie')
OCR_ENGINE = os.environ.get('OCR_ENGINE', 'windows') 

def read_params_file(path):
    """
    Đọc file chứa các tham số
    """
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"File {path} not found")
        return ""
