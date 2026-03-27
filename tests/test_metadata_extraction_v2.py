import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from metadata_extractor import _extract_summary, _postprocess_summary

def test_extraction():
    print("=== TEST 1: Same Line Extraction ===")
    lines = ["QUYẾT ĐỊNH Về việc phê duyệt kế hoạch 2024", "Điều 1. Phê duyệt..."]
    # DocType index 0 ("QUYẾT ĐỊNH")
    res = _extract_summary(lines, 0, bold_lines=None)
    print(f"Input: {lines[0]}")
    print(f"Result: '{res}'")
    assert "Về việc phê duyệt kế hoạch 2024" in res
    assert "Điều 1" not in res
    
    print("\n=== TEST 2: Doc Type + Bold Block Summary ===")
    lines = ["NGHỊ QUYẾT", "Về việc thông qua dự thảo A", "Điều 1..."]
    bold_lines = {"Về việc thông qua dự thảo A"}
    res = _extract_summary(lines, 0, bold_lines=bold_lines)
    print(f"Input: {lines}")
    print(f"Result: '{res}'")
    assert "Về việc thông qua dự thảo A" in res
    
    print("\n=== TEST 3: Bold Priority over weak signals (but strictly exclude Date) ===")
    lines = ["QUYẾT ĐỊNH", "Hà Nội, ngày 10 tháng 10 năm 2024", "Về việc xyz"]
    # Suppose "Hà Nội..." is bold (user said they are bold sometimes)
    bold_lines = {"Hà Nội, ngày 10 tháng 10 năm 2024", "Về việc xyz"}
    res = _extract_summary(lines, 0, bold_lines=bold_lines)
    print(f"Input: {lines}")
    print(f"Result: '{res}'")
    # Should skip the date line despite it being bold
    assert "Ngày 10" not in res
    assert "Về việc xyz" in res

    print("\n=== TEST 4: Cleaning Strange Chars ===")
    raw = "Về việc xyz | ~ ^ @ #"
    cleaned = _postprocess_summary(raw)
    print(f"Raw: '{raw}'")
    print(f"Cleaned: '{cleaned}'")
    assert "|" not in cleaned
    assert "~" not in cleaned
    
    print("\n=== TEST 5: No Forced Dot ===")
    raw = "Về việc ABC"
    cleaned = _postprocess_summary(raw)
    print(f"Raw: '{raw}'")
    print(f"Cleaned: '{cleaned}'")
    assert not cleaned.endswith(".")
    
    print("\n=== TEST 6: National Motto Exclusion ===")
    lines = ["QUYẾT ĐỊNH", "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Về việc XYZ"]
    res = _extract_summary(lines, 0)
    print(f"Result: '{res}'")
    assert "CỘNG HÒA" not in res
    assert "Về việc XYZ" in res

if __name__ == "__main__":
    test_extraction()
