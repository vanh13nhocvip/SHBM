
import sys
import os
import io

# Ensure src is in path for standalone execution
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from pdf_processor import PDFProcessor
from metadata_extractor import extract_metadata

# Hardcoded String Samples
SAMPLE_CV = """
BỘ TÀI CHÍNH
TỔNG CỤC THUẾ
-------
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
---------------
Số: 123/TCT-CS
Hà Nội, ngày 01 tháng 01 năm 2020

V/v trả lời chính sách thuế GTGT

Kính gửi: Cục Thuế tỉnh A

Tổng cục Thuế nhận được công văn số...
"""

SAMPLE_BODY = """
UBND TỈNH X
SỞ Y TẾ
Số: 99/SYT-NVY
Hà Nội, ngày 20 tháng 10 năm 2021

Kính gửi: Các đơn vị trực thuộc

Thực hiện chỉ đạo của UBND tỉnh về việc tiêm chủng mở rộng đợt 2.
Sở Y tế yêu cầu các đơn vị chuẩn bị danh sách...
"""

# Dynamically load samples
samples_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples")
if os.path.exists(samples_dir):
    FILE_SAMPLES = [os.path.join("samples", f) for f in os.listdir(samples_dir) if f.lower().endswith('.pdf')]
else:
    FILE_SAMPLES = []

def run_string_tests(f_out):
    f_out.write("\n" + "="*50 + "\n")
    f_out.write("PART 1: STRING SAMPLE TESTS\n")
    f_out.write("="*50 + "\n")
    
    cases = [("Cong Van V/v", SAMPLE_CV), ("Body Fallback", SAMPLE_BODY)]
    
    for name, text in cases:
        f_out.write(f"\n--- {name} ---\n")
        data = extract_metadata(text)
        _print_metadata(f_out, data)

def run_file_tests(f_out):
    f_out.write("\n" + "="*50 + "\n")
    f_out.write("PART 2: FILE SAMPLE TESTS\n")
    f_out.write("="*50 + "\n")
    
    processor = PDFProcessor()
    
    # Locate project root assuming this script is in src/
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    for rel_path in FILE_SAMPLES:
        full_path = os.path.join(project_root, rel_path)
        if not os.path.exists(full_path):
            f_out.write(f"\nMISSING FILE: {rel_path}\n")
            continue
            
        f_out.write(f"\nPROCESSING: {os.path.basename(rel_path)}\n")
        
        try:
            # 1. Get Metadata
            metadata = processor.extract_and_metadata(full_path, max_ocr_pages=3)
            _print_metadata(f_out, metadata)
            
            # 2. Get Raw Text Dump (First Page) for Debugging
            f_out.write("\n[RAW TEXT DUMP - PAGE 1 SAMPLE]\n")
            pages = processor.extract_text_from_pdf(full_path, max_ocr_pages=1, force_ocr=False)
            text = "\n".join(pages) if isinstance(pages, list) else pages
            lines = text.split('\n')
            for i, line in enumerate(lines[:30]): # First 30 lines
                f_out.write(f"{i:02d}: {line.strip()}\n")
            f_out.write("...\n")
            
        except Exception as e:
             f_out.write(f"ERROR: {e}\n")

def _print_metadata(f_out, data):
    f_out.write(f"Cơ quan ban hành:   {data.get('co_quan_ban_hanh', '')}\n")
    f_out.write(f"Số hiệu:            {data.get('so_van_ban', '')}\n")
    f_out.write(f"Ký hiệu:            {data.get('ky_hieu_van_ban', '')}\n")
    f_out.write(f"Ngày ban hành:      {data.get('ngay_ban_hanh', '')}\n")
    f_out.write(f"Thể loại văn bản:   {data.get('the_loai_van_ban', '')}\n")
    f_out.write(f"Trích yếu nội dung: {data.get('trich_yeu_noi_dung', '')}\n")
    f_out.write(f"Người ký:           {data.get('nguoi_ky', '')}\n")

def main():
    output_file = "verification_output.txt"
    with open(output_file, "w", encoding="utf-8") as f_out:
        run_string_tests(f_out)
        run_file_tests(f_out)
    
    print(f"Verification complete. Results saved to {output_file}")

if __name__ == "__main__":
    main()
