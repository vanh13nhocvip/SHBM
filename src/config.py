"""
Cấu hình toàn cục cho SHBM
"""
import os


# Override with environment variables if set
POPPLER_PATH = r"C:\Program Files (x86)\poppler-24.02.0\Library\bin"

# Override with environment variable if set
if 'POPPLER_PATH' in os.environ:
    POPPLER_PATH = os.environ['POPPLER_PATH']
else:
    # Prefer a project-local copy if present (src/tools/deps/poppler)
    # Calculate from src/ directory (2 levels up to project root, then down to src/tools/deps/poppler)
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    local_poppler_bin = os.path.join(project_root, 'src', 'tools', 'deps', 'poppler', 'bin')
    local_poppler_lib = os.path.join(project_root, 'src', 'tools', 'deps', 'poppler', 'Library', 'bin')
    if os.path.exists(local_poppler_bin):
        POPPLER_PATH = local_poppler_bin
    elif os.path.exists(local_poppler_lib):
        POPPLER_PATH = local_poppler_lib

def has_poppler():
    """Return True if the configured POPPLER_PATH exists on disk."""
    return bool(POPPLER_PATH and os.path.exists(POPPLER_PATH))
    
def get_poppler_path():
    return POPPLER_PATH

# --- OCR / Tesseract configuration ---

TESSERACT_CMD = os.environ.get('TESSERACT_CMD', r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
OCR_LANG = os.environ.get('OCR_LANG', 'vie')
# Options: 'tesseract', 'windows'
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
