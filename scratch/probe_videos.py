import asyncio
import os
import sys
import subprocess
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from utils.obs_utils import download_from_obs

async def main():
    body_path = "c:/Job/AI/mix/AIGC_video_mix_remake/src/utils/body.json"
    with open(body_path, 'r', encoding='utf-8') as f:
        body_data = json.load(f)
        
    videos = body_data["obs_video_path_list"]
    crops = body_data["crop_config"]
    save_dir = "./obs_video"
    
    print("=== PROBING VIDEO FILE DURATIONS ===")
    for idx, video_obs in enumerate(videos):
        crop = crops[idx]
        crop_dur = crop["end"] - crop["start"]
        print(f"[{idx}] Downloading {video_obs}...")
        try:
            local_path = await download_from_obs(video_obs, save_dir)
            
            probe_cmd = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", local_path
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True)
            if res.returncode == 0:
                actual_dur = float(res.stdout.strip())
                print(f"    Actual Dur: {actual_dur:.3f}s, Crop Dur: {crop_dur:.3f}s, extend_to: {crop.get('extend_to')}")
                if actual_dur < crop_dur:
                    print(f"    WARNING: Video is SHORTER than crop duration! Need extend/freeze.")
            else:
                print(f"    Probe error: {res.stderr.strip()}")
        except Exception as e:
            print(f"    Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
