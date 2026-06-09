import asyncio
import os
import sys
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.obs_utils import download_from_obs

async def main():
    # Let's download the first few segment WAVs from the new audio response
    segs = [
        "aigc/aigc_test/volcovoice_1780986195916/seg_0_0_volcovoice_1780986195916.wav",
        "aigc/aigc_test/volcovoice_1780986195916/seg_0_1_volcovoice_1780986195916.wav",
        "aigc/aigc_test/volcovoice_1780986195916/seg_0_2_volcovoice_1780986195916.wav"
    ]
    save_dir = "./scratch"
    
    for path in segs:
        print(f"Downloading {path}...")
        try:
            local_path = await download_from_obs(path, save_dir)
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
                print(f"  FFprobe Duration: {result.stdout.strip()} seconds")
            else:
                print(f"  Probe error: {result.stderr.strip()}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
