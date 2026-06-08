import sys
import os

# Add src directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from service.volcovoice_service import _build_segments_from_words
from utils.volcano_utils import VolcanoWordTimestamp

def mock_words_from_text(text: str) -> list[VolcanoWordTimestamp]:
    # Simple mock builder where each Chinese character is a word.
    # Words have mock timestamps incremented by 200ms.
    words = []
    strong_punctuation = "。！？!?；;"
    comma_punctuation = "，,、；：:"
    
    i = 0
    t = 0.0
    while i < len(text):
        char = text[i]
        if char.isalnum() or '\u4e00' <= char <= '\u9fff':
            word = char
            while i + 1 < len(text) and (text[i+1] in strong_punctuation or text[i+1] in comma_punctuation or text[i+1] == "L" or text[i+1] == "S" or text[i+1].isdigit() or text[i+1] == "°"):
                i += 1
                word += text[i]
            words.append(VolcanoWordTimestamp(word=word, start_time=t, end_time=t + 150))
            t += 200
        else:
            words.append(VolcanoWordTimestamp(word=char, start_time=t, end_time=t + 150))
            t += 200
        i += 1
    return words

def test_volcovoice_splitting():
    print("Running test_volcovoice_splitting...")

    # Sentence 1
    s1 = "智己LS6配了11L双开门冰箱，同级领先的大容量，前后排都能拿取，冷饮随手可得！"
    words1 = mock_words_from_text(s1)
    segments, decisions = _build_segments_from_words(words1)
    
    print("\nSentence 1 segments:")
    for seg in segments:
        print(f"  - '{seg['caption_text']}'")
        
    expected_s1 = [
        "智己LS6配了11L双开门冰箱",
        "同级领先的大容量",
        "前后排都能拿取",
        "冷饮随手可得！"
    ]
    
    assert len(segments) == len(expected_s1), f"Expected {len(expected_s1)} segments, got {len(segments)}"
    for idx, expected in enumerate(expected_s1):
        assert segments[idx]['caption_text'] == expected, f"Expected '{expected}', got '{segments[idx]['caption_text']}'"

    # Sentence 2
    s2 = "后排座椅支持131°最大靠背角度，还有8点SPA级按摩，家人坐在后面就是航司头等舱的享受！"
    words2 = mock_words_from_text(s2)
    segments2, decisions2 = _build_segments_from_words(words2)
    
    print("\nSentence 2 segments:")
    for seg in segments2:
        print(f"  - '{seg['caption_text']}'")
        
    expected_s2 = [
        "后排座椅支持131°最大靠背角度",
        "还有8点SPA级按摩",
        "家人坐在后面就是航司头等舱的享受！"
    ]
    
    assert len(segments2) == len(expected_s2), f"Expected {len(expected_s2)} segments, got {len(segments2)}"
    for idx, expected in enumerate(expected_s2):
        assert segments2[idx]['caption_text'] == expected, f"Expected '{expected}', got '{segments2[idx]['caption_text']}'"

    print("\nAll volcovoice splitting tests passed successfully!")

if __name__ == "__main__":
    test_volcovoice_splitting()
