import sys
import os
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from post_processing import VietnamesePostProcessor

def test_deep_learning_suggestions():
    print("=== TEST: Deep Learning Smart Suggestions (PhoBERT) ===")
    # Enable deep learning
    pp = VietnamesePostProcessor(use_deep_learning=True)
    
    # Wait for model to load (it's in a background thread)
    print("Đang tải model PhoBERT (vui lòng đợi, có thể mất vài phút lần đầu)...")
    max_wait = 300 # 5 mins
    waited = 0
    while not pp.use_deep_learning and waited < max_wait:
        time.sleep(5)
        waited += 5
        if waited % 30 == 0:
            print(f"Vẫn đang tải... ({waited}s)")
            
    if not pp.use_deep_learning:
        print("Không thể tải model DL hoặc quá thời gian chờ.")
        return

    test_sentences = [
        "Quyết định về việc phê duyệt",
        "Cơ quan ban hành văn",
        "Luật tổ chức chính quyền địa"
    ]
    
    for sentence in test_sentences:
        print(f"\nCâu đang gõ: '{sentence}'")
        suggestions = pp.suggest_next_words(sentence)
        print(f"Gợi ý từ tiếp theo: {suggestions}")

if __name__ == "__main__":
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    test_deep_learning_suggestions()
