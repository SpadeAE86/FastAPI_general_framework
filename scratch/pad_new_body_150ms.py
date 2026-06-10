import json
import os

def main():
    body_path = "src/utils/body.json"
    if not os.path.exists(body_path):
        print(f"Error: {body_path} not found.")
        return
        
    with open(body_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    crops = data.get("crop_config", [])
    captions = data.get("cap_config", {}).get("caption_list", [])
    
    # Clean durations derived from the original unpadded 15-segment config
    clean_durations = [2.965, 2.15, 2.98, 2.23, 2.46, 2.05, 3.0, 2.2, 2.573, 2.88, 1.52, 2.09, 1.44, 1.75, 2.252]
    
    print(f"Loaded {len(crops)} crops and {len(captions)} captions from body.json")
    if len(crops) != len(clean_durations) or len(captions) != len(clean_durations):
        print(f"Error: length mismatch! Expected {len(clean_durations)} segments.")
        return
        
    # 1. Modify crop_config with +150ms padding (+0.15s)
    for idx, c in enumerate(crops):
        clean_dur = clean_durations[idx]
        c["end"] = round(c["start"] + clean_dur + 0.15, 3)
        c["extend_to"] = round(c["start"] + clean_dur + 0.15, 3)
        print(f"Crop {idx:02d}: end={c['end']}, extend_to={c['extend_to']}")
        
    # 2. Modify cap_config.caption_list with cumulative +150ms timeline
    current_time = 0.0
    for idx, cap in enumerate(captions):
        clean_dur = clean_durations[idx]
        cap["start"] = round(current_time, 3)
        cap["end"] = round(current_time + clean_dur + 0.15, 3)
        print(f"Caption {idx:02d}: cap='{cap['cap']}', start={cap['start']}, end={cap['end']}")
        current_time = cap["end"]
        
    # 3. Save back to body.json
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("Successfully updated body.json with +150ms padding!")

if __name__ == "__main__":
    main()
