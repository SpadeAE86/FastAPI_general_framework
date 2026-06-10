import json
import os

def main():
    body_path = "src/utils/body.json"
    if not os.path.exists(body_path):
        print(f"Error: {body_path} not found.")
        return
        
    with open(body_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Keep the first 4 video paths
    orig_videos = data.get("obs_video_path_list", [])
    if len(orig_videos) < 4:
        print(f"Warning: original video list has only {len(orig_videos)} items, cannot take 4.")
        videos = orig_videos
    else:
        videos = orig_videos[:4]
        
    # Simplify crop_config to 4 items of 2.5s
    new_crops = []
    for i in range(4):
        new_crops.append({
            "end": 2.5,
            "extend_to": 2.5,
            "mirror": False,
            "rotation": 0.0,
            "scale": 1.0,
            "speed": 1.0,
            "start": 0.0,
            "translate_x": 0.0,
            "translate_y": 0.0
        })
        
    # Clear caption list
    cap_config = data.get("cap_config", {})
    cap_config["caption_list"] = []
    
    # Set other lists to match 4 segments
    data["crop_config"] = new_crops
    data["obs_video_path_list"] = videos
    data["mute_config"] = [True] * 4
    data["filter_config"] = []
    
    # Save back
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print("Successfully modified body.json to 4 segments of 2.5s (basic crop_config).")

if __name__ == "__main__":
    main()
