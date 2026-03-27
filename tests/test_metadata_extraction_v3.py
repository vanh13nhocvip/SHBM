import sys
import os
import io

# Force UTF-8 for stdout
sys.stdout.reconfigure(encoding='utf-8')

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

try:
    from metadata_extractor import _extract_summary, _postprocess_summary
except ImportError as e:
    print(f"Error importing: {e}")
    sys.exit(1)

def run_test(name, func):
    print(f"\n[{name}] Running...")
    try:
        func()
        print(f"[{name}] PASSED.")
    except AssertionError as e:
        print(f"[{name}] FAILED: {e}")
    except Exception as e:
        print(f"[{name}] ERROR: {e}")

def test_same_line():
    lines = ["QUYẾT ĐỊNH Về việc phê duyệt kế hoạch 2024", "Điều 1. Phê duyệt..."]
    res = _extract_summary(lines, 0, bold_lines=None)
    print(f"Result: '{res}'")
    assert "Về việc phê duyệt kế hoạch 2024" in res, f"Expected 'Về việc...' but got '{res}'"
    assert "Điều 1" not in res, "Should not contain next line"

def test_doc_type_bold_block():
    lines = ["NGHỊ QUYẾT", "Về việc thông qua dự thảo A", "Điều 1..."]
    bold_lines = {"Về việc thông qua dự thảo A"}
    res = _extract_summary(lines, 0, bold_lines=bold_lines)
    print(f"Result: '{res}'")
    assert "Về việc thông qua dự thảo A" in res, f"Expected contents of bold line but got '{res}'"

def test_bold_priority_and_date_exclusion():
    lines = ["QUYẾT ĐỊNH", "Hà Nội, ngày 10 tháng 10 năm 2024", "Về việc xyz"]
    bold_lines = {"Hà Nội, ngày 10 tháng 10 năm 2024", "Về việc xyz"}
    res = _extract_summary(lines, 0, bold_lines=bold_lines)
    print(f"Result: '{res}'")
    assert "Ngày 10" not in res, "Should exclude Date even if bold"
    assert "Về việc xyz" in res, "Should capture bold content"

def test_cleaning_strange_chars():
    raw = "Về việc xyz | ~ ^ @ #"
    cleaned = _postprocess_summary(raw)
    print(f"Cleaned: '{cleaned}'")
    assert "|" not in cleaned
    assert "~" not in cleaned
    assert "Về việc xyz" in cleaned

def test_no_forced_dot():
    raw = "Về việc ABC"
    cleaned = _postprocess_summary(raw)
    print(f"Cleaned: '{cleaned}'")
    assert not cleaned.endswith("."), "Should not force dot at end"

def test_national_motto_exclusion():
    lines = ["QUYẾT ĐỊNH", "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Về việc XYZ"]
    res = _extract_summary(lines, 0)
    print(f"Result: '{res}'")
    assert "CỘNG HÒA" not in res, "Should exclude Motto"
    assert "Về việc XYZ" in res, "Should match content"

if __name__ == "__main__":
    run_test("Test 1: Same Line", test_same_line)
    run_test("Test 2: Bold Block", test_doc_type_bold_block)
    run_test("Test 3: Bold Priority & Exclusion", test_bold_priority_and_date_exclusion)
    run_test("Test 4: Cleaning", test_cleaning_strange_chars)
    run_test("Test 5: No Dot", test_no_forced_dot)
    run_test("Test 6: Motto Exclusion", test_national_motto_exclusion)
