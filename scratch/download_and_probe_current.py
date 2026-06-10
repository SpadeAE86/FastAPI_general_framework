import asyncio
import os
import sys
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
from utils.obs_utils import download_from_obs

async def main():
    obs_path = "aigc/aigc_test/volcovoice_1781058617354/volcovoice0_volcovoice_1781058617354.wav"
    save_dir = "./obs_audio"
    
    print(f"Downloading {obs_path}...")
    local_path = await download_from_obs(obs_path, save_dir)
    print(f"Downloaded to: {local_path}")
    
    probe_cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        local_path,
    ]
    result = subprocess.run(probe_cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Full voice actual duration: {result.stdout.strip()} seconds")
    else:
        print(f"Probe error: {result.stderr.strip()}")

    # Also probe a few segments from audio_response.json
    # seg_0_12: 还是蓝帽认证的
    # seg_0_13: 吃着就很放心
    # seg_0_14: 我自己用下来真的不错
    segs = [
        "aigc/aigc_test/volcovoice_1781058617354/seg_0_12_volcovoice_1781058617354.wav",
        "aigc/aigc_test/volcovoice_1781058617354/seg_0_13_volcovoice_1781058617354.wav",
        "aigc/aigc_test/volcovoice_1781058617354/seg_0_14_volcovoice_1781058617354.wav",
    ]
    for seg_obs in segs:
        local_seg = await download_from_obs(seg_obs, save_dir)
        res = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", local_seg
        ], capture_output=True, text=True)
        print(f"Segment {seg_obs} actual duration: {res.stdout.strip()} seconds")

if __name__ == "__main__":
    asyncio.run(main())
