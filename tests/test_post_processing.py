import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from post_processing import get_post_processor

def test_correction():
    pp = get_post_processor()
    print(f"SymSpell enabled: {pp.use_symspell}")
    
    # Test case: common typo in admin terms
    # "Quyết định" is in dictionary. Let's try "Quyết đinh" (missing dot) or "Quyet dinh"
    test_cases = [
        "Quyết đinh",
        "Nghị quvết",
        "Cộng hoà xã hỗi chủ nghĩa"
    ]
    
    for tc in test_cases:
        corrected = pp.correct_text(tc)
        print(f"Original: '{tc}' -> Corrected: '{corrected}'")

if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    test_correction()
