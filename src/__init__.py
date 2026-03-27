"""
SHBM - Số Hoá Biên Mục
"""
from .pdf_processor import PDFProcessor

# Import optional/heavy modules lazily so that importing the package does not
# fail when optional runtime dependencies (like pandas) are missing.
try:
	from .excel_exporter import ExcelExporter
except Exception:
	ExcelExporter = None

try:
	from .gui import main
except Exception:
	# Fallback to the restored pdf_metadata_gui if present
	try:
		from .pdf_metadata_gui import PDFMetadataGUI as _PDFMetadataGUI
		def main():
			app = _PDFMetadataGUI()
			app.mainloop()
	except Exception:
		main = None

__version__ = '0.1.0'