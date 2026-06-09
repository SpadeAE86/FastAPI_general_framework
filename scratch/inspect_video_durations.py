import asyncio
import os
import sys

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.obs_utils import download_from_obs
from utils.general_utils import get_video_info

async def main():
    obs_path = "aigc-ai/ai-project/2026-06-01/transcode_2061326469585862658_1780297951359/1780297950795-7de3_H.264_1280x720_700.mp4"
    save_dir = "./obs_video"
    
    print(f"Downloading {obs_path}...")
    local_path = await download_from_obs(obs_path, save_dir)
    print(f"Downloaded to: {local_path}")
    
    video_info = get_video_info(local_path)
    width, height, duration, rot, pix_format, codec = video_info.get_info()
    
    print(f"Video Info:")
    print(f"  Width: {width}")
    print(f"  Height: {height}")
    print(f"  Duration: {duration} seconds")
    print(f"  Rotation: {rot}")
    print(f"  Pixel Format: {pix_format}")
    print(f"  Codec: {codec}")

if __name__ == "__main__":
    asyncio.run(main())
