import re

# Set of punctuation to remove (excluding ?, !, dashes, ellipses)
PUNCTUATION_TO_REMOVE = set("，。、；：,.;: ")

def strip_ending_punctuation(text: str) -> str:
    text = text.rstrip()
    if not text:
        return text
    
    # Check if the text ends with ellipses or dashes
    if text.endswith("...") or text.endswith("……") or text.endswith("——") or text.endswith("-"):
        return text
        
    # Strip characters from the end one by one
    while text and text[-1] in PUNCTUATION_TO_REMOVE:
        if text.endswith("...") or text.endswith("……") or text.endswith("——") or text.endswith("-"):
            break
        text = text[:-1]
    return text

# Define boundaries
STRONG_PUNCTUATION = "。！？!?；;"
COMMA_PUNCTUATION = "，,、；：:"

def _is_strong_boundary(word: str) -> bool:
    return bool(word) and word[-1] in STRONG_PUNCTUATION

def _is_comma_boundary(word: str) -> bool:
    return bool(word) and word[-1] in COMMA_PUNCTUATION

def mock_words_from_text(text: str) -> list[str]:
    # A simple Chinese word tokenizer that groups punctuation with the preceding char
    # E.g. "冰箱，" is one word
    tokens = []
    i = 0
    while i < len(text):
        char = text[i]
        # If it's a character, check if next is punctuation
        if char.isalnum() or '\u4e00' <= char <= '\u9fff':
            word = char
            # Attach consecutive numbers/letters or trailing punctuation
            while i + 1 < len(text) and (text[i+1] in STRONG_PUNCTUATION or text[i+1] in COMMA_PUNCTUATION or text[i+1] == "L" or text[i+1] == "S" or text[i+1].isdigit() or text[i+1] == "°"):
                i += 1
                word += text[i]
            tokens.append(word)
        else:
            tokens.append(char)
        i += 1
    return tokens

def simulate_splitting(text: str, out_file, soft_chars=4, hard_chars=10, no_comma_max=12):
    words = mock_words_from_text(text)
    out_file.write(f"\nOriginal text: {text}\n")
    out_file.write(f"Tokenized words: {words}\n")
    
    segments = []
    current_words = []
    
    # Split logic
    for idx, word in enumerate(words):
        current_words.append(word)
        current_text = "".join(current_words)
        
        if _is_strong_boundary(word):
            caption_text = strip_ending_punctuation(current_text)
            segments.append(caption_text)
            current_words = []
            continue
            
        if _is_comma_boundary(word):
            soft_ready = len(current_text) >= soft_chars
            hard_ready = len(current_text) >= hard_chars
            # pause is 0, so soft_ready is enough to split
            should_split = hard_ready or soft_ready
            if should_split:
                caption_text = strip_ending_punctuation(current_text)
                segments.append(caption_text)
                current_words = []
                continue
                
        if len(current_text) >= no_comma_max:
            caption_text = strip_ending_punctuation(current_text)
            segments.append(caption_text)
            current_words = []
            continue
            
    if current_words:
        caption_text = strip_ending_punctuation("".join(current_words))
        segments.append(caption_text)
        
    out_file.write("Split segments:\n")
    for s in segments:
        out_file.write(f"  - '{s}' (len={len(s)})\n")
    return segments

if __name__ == "__main__":
    sentences = [
        "智己LS6配了11L双开门冰箱，同级领先的大容量，前后排都能拿取，冷饮随手可得！",
        "后排座椅支持131°最大靠背角度，还有8点SPA级按摩，家人坐在后面就是航司头等舱的享受！"
    ]
    with open("scratch/splitting_result.txt", "w", encoding="utf-8") as out:
        for s in sentences:
            simulate_splitting(s, out)

