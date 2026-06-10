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
    
    print(f"Loaded {len(crops)} crops and {len(captions)} captions from body.json")
    
    # 1. First, let's extract the clean (unpadded) durations from the crop_config.
    # Since the crop_config currently has end == extend_to (or similar unpadded values),
    # we can use the current c["end"] as the clean duration D_i.
    clean_durations = []
    for c in crops:
        # If speed is not 1.0, we might need to adjust, but here speed is 1.0. Let's print to verify
        speed = c.get("speed", 1.0)
        clean_dur = c["end"] - c["start"]
        clean_durations.append(clean_dur)
        
    print("Clean durations:", clean_durations)
    
    # 2. Modify crop_config with +200ms padding
    for idx, c in enumerate(crops):
        clean_dur = clean_durations[idx]
        c["end"] = round(c["start"] + clean_dur + 0.2, 3)
        c["extend_to"] = round(c["start"] + clean_dur + 0.2, 3)
        print(f"Crop {idx:02d}: end={c['end']}, extend_to={c['extend_to']}")
        
    # 3. Modify cap_config.caption_list with cumulative +200ms timeline
    current_time = 0.0
    for idx, cap in enumerate(captions):
        clean_dur = clean_durations[idx]
        cap["start"] = round(current_time, 3)
        cap["end"] = round(current_time + clean_dur + 0.2, 3)
        print(f"Caption {idx:02d}: cap='{cap['cap']}', start={cap['start']}, end={cap['end']}")
        current_time = cap["end"]
        
    # 4. Save back to body.json
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("Successfully updated body.json with +200ms padding!")

if __name__ == "__main__":
    main()
