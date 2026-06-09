import json
import os
import sys
import subprocess
import asyncio

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.obs_utils import download_from_obs

async def main():
    unique_paths = set()

    # Read src/utils/body.json
    body_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'utils', 'body.json')
    if os.path.exists(body_path):
        try:
            with open(body_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                video_list = data.get("obs_video_path_list", [])
                for p in video_list:
                    if p:
                        unique_paths.add(p)
        except Exception as e:
            print(f"Error reading body.json: {e}")

    # Read debug_payload.json
    debug_path = os.path.join(os.path.dirname(__file__), '..', 'debug_payload.json')
    if os.path.exists(debug_path):
        try:
            with open(debug_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                video_list = data.get("obs_video_path_list", [])
                for p in video_list:
                    if p:
                        unique_paths.add(p)
        except Exception as e:
            print(f"Error reading debug_payload.json: {e}")

    print(f"Found {len(unique_paths)} unique video paths:")
    for i, p in enumerate(sorted(unique_paths)):
        print(f"  {i+1}: {p}")

    save_dir = "./obs_video"
    os.makedirs(save_dir, exist_ok=True)

    results = []

    for path in sorted(unique_paths):
        print(f"\nProcessing: {path}")
        try:
            local_path = await download_from_obs(path, save_dir)
            
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
                duration_str = result.stdout.strip()
                duration = float(duration_str)
                print(f"  Local path: {local_path}")
                print(f"  Duration: {duration:.3f} seconds")
                results.append((path, duration, local_path))
            else:
                print(f"  Probe error: {result.stderr.strip()}")
                results.append((path, None, f"Probe error: {result.stderr.strip()}"))
        except Exception as e:
            print(f"  Download error: {e}")
            results.append((path, None, f"Download error: {str(e)}"))

    print("\n" + "="*50)
    print("FINAL SUMMARY OF ALL UNIQUE VIDEOS:")
    print("="*50)
    
    over_6s = []
    under_6s = []
    errors = []

    for path, duration, local in results:
        if duration is None:
            errors.append((path, local))
        elif duration >= 6.0:
            over_6s.append((path, duration, local))
        else:
            under_6s.append((path, duration, local))

    print(f"\nVideos >= 6.0s ({len(over_6s)}):")
    for path, duration, local in over_6s:
        print(f"  - {duration:.3f}s: {path} (local: {local})")

    print(f"\nVideos < 6.0s ({len(under_6s)}):")
    for path, duration, local in under_6s:
        print(f"  - {duration:.3f}s: {path} (local: {local})")

    if errors:
        print(f"\nFailed to process ({len(errors)}):")
        for path, err in errors:
            print(f"  - {path}: {err}")

if __name__ == "__main__":
    asyncio.run(main())
