import sys
import os
import unicodedata

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from metadata_extractor import extract_metadata, _extract_number_and_symbol

def run_test(name, func):
    print(f"Running {name}...", end=" ", flush=True)
    try:
        func()
        print("PASSED")
    except AssertionError as e:
        print(f"FAILED: {e}")
    except Exception as e:
        print(f"ERROR: {e}")

def test_bold_title_detailed():
    text = """
    UBND TỈNH ABC
    
    KẾ HOẠCH PHÁT TRIỂN KINH TẾ
    
    Nội dung...
    """
    bold_val = "KẾ HOẠCH PHÁT TRIỂN KINH TẾ"
    bold_lines = {bold_val}
    
    # Check normalization
    text_norm = unicodedata.normalize('NFC', text)
    bold_val_norm = unicodedata.normalize('NFC', bold_val)
    
    meta = extract_metadata(text, bold_lines=bold_lines)
    val = meta.get('the_loai_van_ban')
    
    if val != bold_val:
        print("\n--- DEBUG START ---")
        lines = [l.strip() for l in text.splitlines()]
        found_line = lines[3]
        print(f"Target line in text: {repr(found_line)}")
        print(f"Bold value in set:   {repr(bold_val)}")
        print(f"Equal? {found_line == bold_val}")
        print(f"Target in set? {found_line in bold_lines}")
        print(f"Target norm: {repr(unicodedata.normalize('NFC', found_line))}")
        print(f"Bold val norm: {repr(unicodedata.normalize('NFC', bold_val))}")
        print("--- DEBUG END ---")
    
    assert val == bold_val, f"Expected {bold_val}, got '{val}'"

def test_number_extraction():
    # Test cases for stricter number extraction
    cases = [
        ("Số: 01/NQ-UBND", "01", "NQ-UBND"),
        ("Số 123-QĐ", "123", "QĐ"),
        ("Số tiền: 1.000.000 VNĐ", "", ""), # Should not match
        ("Số lượng: 50 trang", "", ""), # Should not match
    ]
    for text, expected_num, expected_symbol in cases:
        num, symbol = _extract_number_and_symbol(text.splitlines())
        assert num == expected_num, f"For '{text}', expected num '{expected_num}', got '{num}'"
        assert symbol == expected_symbol, f"For '{text}', expected symbol '{expected_symbol}', got '{symbol}'"

def test_validity_filtering():
    # Test valid document
    valid_text = """
    UBND TỈNH ABC
    Số: 01/NQ-UBND
    Hà Nội, ngày 01 tháng 01 năm 2025
    NGHỊ QUYẾT
    Về việc...
    (Chữ ký, Dấu)
    """
    meta_valid = extract_metadata(valid_text)
    assert meta_valid.get('so_van_ban') == "01", "Should extract metadata for valid doc"
    
    # Test invalid document (no date, no number)
    invalid_text = """
    CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
    Độc lập - Tự do - Hạnh phúc
    
    ĐƠN XIN NGHỈ PHÉP
    
    Kính gửi...
    """
    meta_invalid = extract_metadata(invalid_text)
    # Based on current implementation, invalid returns a dict with empty strings
    assert meta_invalid.get('so_van_ban') == "", "Should NOT extract metadata for invalid doc"
    assert meta_invalid.get('ngay_ban_hanh') == "", "Should NOT extract date for invalid doc"

if __name__ == "__main__":
    run_test("Bold Title Detection", test_bold_title_detailed)
    run_test("Number Extraction", test_number_extraction)
    run_test("Validity Filtering", test_validity_filtering)
