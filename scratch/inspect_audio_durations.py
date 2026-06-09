import asyncio
import os
import sys
import subprocess

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.obs_utils import download_from_obs

async def main():
    bgms = [
        "aigc/aigc_test/volcovoice_1780971203719/volcovoice0_volcovoice_1780971203719.wav",
        "aigc/crawl_data_base/jianying_music/宁静森林之音.MP3"
    ]
    save_dir = "./obs_audio"
    
    for path in bgms:
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
                print(f"  Duration: {result.stdout.strip()} seconds")
            else:
                print(f"  Probe error: {result.stderr.strip()}")
        except Exception as e:
            print(f"  Error downloading or probing: {e}")

if __name__ == "__main__":
    asyncio.run(main())
