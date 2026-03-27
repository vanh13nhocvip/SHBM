
import os
import sys
import re

# Mocking the logic found in extract_from_directory
def mock_extract_tenure(file_path):
    # Simulate data dict
    data = {}
    
    # Logic copied from metadata_extractor.py
    rel_dir = os.path.dirname(file_path) # Simplified: Treat input as full path
    folder_parts = rel_dir.replace("\\", "/").split("/")
    
    print(f"Testing path: {file_path}")
    print(f"Folder parts: {folder_parts}")
    
    for part in reversed(folder_parts):
        norm_part = " ".join(part.lower().split())
        
        # Priority 1: Explicit "Nhiệm kỳ" label
        if "nhiem ky" in norm_part or "nhiệm kỳ" in norm_part:
            data["nhiem_ky"] = part
            data["tenure"] = part
            print(f"-> Found explicit tenure: {part}")
            break
        
        # Priority 2: Year range (YYYY-YYYY or YYYY_YYYY)
        # User request: "G:\...\2.SOHOA_KCCQĐT_2010-2018" -> 2010-2018
        m_years = re.search(r"(\d{4})[-_](\d{4})", part)
        if m_years:
            y1, y2 = int(m_years.group(1)), int(m_years.group(2))
            # Validity check: reasonable years
            if 1900 <= y1 <= 2100 and 1900 <= y2 <= 2100:
                # Use the range as the tenure
                val = f"{y1}-{y2}"
                data["nhiem_ky"] = val
                data["tenure"] = val
                print(f"-> Found year range tenure: {val}")
                break
    
    if "nhiem_ky" not in data:
         print("-> No tenure found")
    print("-" * 20)

if __name__ == "__main__":
    # Test cases
    paths = [
        r"G:/1.SOHOA_KCCQĐT_BACNINH/2.SOHOA_KCCQĐT_2010-2018/1000-001-007.pdf",
        r"G:/Data/Nhiệm kỳ 2015-2020/file.pdf",
        r"G:/Data/SomeDir/file.pdf",
        r"G:/Archive/Project_2000_2005/doc.pdf"
    ]
    
    for p in paths:
        mock_extract_tenure(p)
