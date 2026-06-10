import urllib.request
import json

def main():
    url = "https://freeuuu.obs.cn-east-3.myhuaweicloud.com/aigc/aigc_test/volcovoice_1781058617354/volcovoice_volcovoice_1781058617354_response.json"
    print("Downloading debug JSON...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        
    debug_obj = data.get("debug_objects", [])[0]
    
    print("\n=== SEGMENTS IN DEBUG_OBJECTS ===")
    segments = debug_obj.get("segments", [])
    for idx, seg in enumerate(segments):
        print(f"[{idx}] text: {seg['caption_text']}")
        print(f"    start_ms: {seg['start_ms']}, end_ms: {seg['end_ms']}, duration_ms: {seg['duration_ms']}, pause_ms: {seg['pause_ms']}")
        
    print("\n=== WORDS FOR THE END OF TIMELINE ===")
    words = debug_obj.get("frontend_words", [])
    # Find words for segment 12, 13, 14
    # segment 12: 还是蓝帽认证的 (start_ms: 27898)
    # segment 13: 吃着就很放心 (start_ms: 29238)
    # segment 14: 我自己用下来真的不错 (start_ms: 30888)
    for w in words:
        st = w.get('start_time')
        et = w.get('end_time')
        word = w.get('word')
        if st >= 27000:
            print(f"Word: {word:<10} | Start: {st:<6} | End: {et:<6}")

if __name__ == "__main__":
    main()
