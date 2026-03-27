
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from metadata_extractor import extract_metadata

def test_ocr_noise():
    # Simulation of the OCR noise reported by user
    # Case 1: "S6" instead of "Số", "Se" instead of "Số"
    # Case 2: "TRICH NGHI QU" (truncated)
    # Case 3: "Se: BODY." in Issuer (?) or just noise lines.
    
    text_case_1 = """
    DANG UY KHOI CO QUAN
    
    NGHI QUYET
    Về việc ABC...
    
    S6: 02-NQ/DU
    
    Hà Nội, ngày 12 tháng 01 năm 2009
    
    TM. BAN THƯỜNG VỤ
    BÍ THƯ
    
    Nguyễn Văn A
    """
    
    # Text with "Se: BODY" and noise
    text_case_2 = """
    Se: BODY
    
    NGHI QUYET
    Se: BODY.
    
    S6: 07
    
    Ninh Binh, ngay 15 thang 05 nam 2010
    
    TM. BAN CHAP HANH
    
    Tran Van B
    """
    
    print("--- Test Case 1: 'S6' typo ---")
    meta1 = extract_metadata(text_case_1)
    print(f"Doc Type: {meta1['the_loai_van_ban']}")
    print(f"Number: {meta1['so_van_ban']}")
    print(f"Symbol: {meta1['ky_hieu_van_ban']}")
    
    # Expect: Doc Type = NGHI QUYET (not S6...), Number = 02, Symbol = NQ/DU
    
    print("\n--- Test Case 2: 'Se: BODY' noise ---")
    meta2 = extract_metadata(text_case_2)
    print(f"Issuer: {meta2['co_quan_ban_hanh']}")
    print(f"Doc Type: {meta2['the_loai_van_ban']}")
    print(f"Summary: {meta2['trich_yeu_noi_dung']}")
    
    # Expect: Issuer should NOT be "Se: BODY". Doc Type = NGHI QUYET. Summary shoud NOT be "Se: BODY."

if __name__ == "__main__":
    test_ocr_noise()
