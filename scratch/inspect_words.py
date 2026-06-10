import urllib.request
import json

def main():
    url = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/aigc/aigc_test/volcovoice_1781058617354/volcovoice_volcovoice_1781058617354_response.json"
    print("Downloading debug JSON...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        
    print("\n=== SEGMENTS IN DEBUG JSON ===")
    segments = data.get("segments", [])
    for idx, seg in enumerate(segments):
        print(f"[{idx}] text: {seg['caption_text']}")
        print(f"    start_ms: {seg['start_ms']}, end_ms: {seg['end_ms']}, duration_ms: {seg['duration_ms']}, pause_ms: {seg['pause_ms']}")
        
    print("\n=== WORDS IN DEBUG JSON FOR THE END OF TIMELINE ===")
    words = data.get("frontend_words", [])
    # Find words near the end
    end_words = words[-30:] # last 30 words
    for w in end_words:
        print(f"Word: {w.get('word')}, start_time: {w.get('start_time')}, end_time: {w.get('end_time')}")

if __name__ == "__main__":
    main()
