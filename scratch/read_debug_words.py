import json

with open("./scratch/volcovoice_1780986195916_response.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

if "debug_objects" in data:
    debug_obj = data["debug_objects"][0]
    print(debug_obj.keys())
    print("\nSegments:")
    for idx, seg in enumerate(debug_obj["segments"]):
        print(f"Segment {idx}:")
        print(f"  caption_text: {seg.get('caption_text')}")
        print(f"  start_ms: {seg.get('start_ms')}")
        print(f"  end_ms: {seg.get('end_ms')}")
        print(f"  pause_ms: {seg.get('pause_ms')}")
        print(f"  duration_ms: {seg.get('duration_ms')}")
        
    print("\nWords around first boundary:")
    # Print words around segment 0 end
    seg0_end = debug_obj["segments"][0]["end_ms"]
    print(f"Segment 0 end_ms: {seg0_end}")
    for word in debug_obj["frontend_words"]:
        # print words between 1.5s and 3.0s
        t_start = word["start_time"]
        t_end = word["end_time"]
        if 1500 <= t_start <= 3000:
            print(f"  Word: '{word['word']}', start: {t_start}, end: {t_end}")
