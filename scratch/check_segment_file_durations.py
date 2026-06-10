import json
import asyncio
import os
import sys
import subprocess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from utils.obs_utils import download_from_obs

async def main():
    save_dir = "./obs_audio"
    os.makedirs(save_dir, exist_ok=True)
    
    with open("src/utils/audio_response.json", "r", encoding="utf-8") as f:
        audio_data = json.load(f)
    with open("src/utils/body.json", "r", encoding="utf-8") as f:
        body_data = json.load(f)
        
    audio_segs = audio_data["object_list"][0]["detail_info"]
    crops = body_data["crop_config"]
    
    print(f"{'Idx':<3} | {'Text':<20} | {'JSON Aud Dur':<12} | {'Actual File Dur':<15} | {'Video Crop Dur':<14} | {'Aud vs Video Diff':<17} | {'File vs Video Diff'}")
    print("-" * 110)
    
    for idx, seg in enumerate(audio_segs):
        text = seg["caption_text"]
        json_aud_dur = seg["segment_duration"]
        
        crop = crops[idx]
        v_dur = crop["extend_to"] - crop["start"]
        
        # Download and probe segment
        seg_url = seg["segment_url"]
        # Extract path relative to bucket
        obs_prefix = "aigc/aigc_test/"
        obs_path = seg_url.split("myhuaweicloud.com/")[-1]
        
        local_seg = await download_from_obs(obs_path, save_dir)
        probe_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", local_seg
        ]
        res = subprocess.run(probe_cmd, capture_output=True, text=True)
        actual_file_dur = float(res.stdout.strip()) if res.returncode == 0 else 0.0
        
        json_diff = json_aud_dur - v_dur
        file_diff = actual_file_dur - v_dur
        
        print(f"{idx:<3} | {text[:20]:<20} | {json_aud_dur:<12.3f} | {actual_file_dur:<15.3f} | {v_dur:<14.3f} | {json_diff:<+17.3f} | {file_diff:<+17.3f}")

if __name__ == "__main__":
    asyncio.run(main())
