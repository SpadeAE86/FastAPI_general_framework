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
    print(f"Loaded {len(crops)} crops from body.json")
    
    # We will restore to clean git version first to avoid double padding if script is run multiple times
    # Actually, let's just run a git checkout to make sure we start from clean baseline!
    import subprocess
    subprocess.run(["git", "checkout", "src/utils/body.json"])
    
    # Reload clean baseline
    with open(body_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    crops = data.get("crop_config", [])
    
    # Pad each segment by 200ms (0.2s)
    for idx, c in enumerate(crops):
        if "end" in c:
            orig_end = c["end"]
            c["end"] = round(orig_end + 0.2, 3)
            
        if "extend_to" in c and c["extend_to"] is not None:
            orig_ext = c["extend_to"]
            c["extend_to"] = round(orig_ext + 0.2, 3)
            
        print(f"Clip {idx:02d}: end {orig_end} -> {c['end']}, extend_to {orig_ext} -> {c['extend_to']}")
        
    with open(body_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully updated {body_path} with +200ms padding.")

if __name__ == "__main__":
    main()
