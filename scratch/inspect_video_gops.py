import os
import subprocess
import json
import glob
import sys

def probe_video(filepath):
    # Get basic info
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration,start_time:stream=codec_name,nb_frames",
        "-of", "json", filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return None
    try:
        data = json.loads(res.stdout)
        v_stream = next((s for s in data.get("streams", []) if s.get("codec_name")), {})
        duration = float(data.get("format", {}).get("duration", 0.0))
        start_time = float(data.get("format", {}).get("start_time", 0.0))
        nb_frames = int(v_stream.get("nb_frames", 0))
        codec = v_stream.get("codec_name", "unknown")
    except Exception as e:
        return None

    # Check for B-frames - only read first 5 seconds
    b_cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "frame=pict_type",
        "-read_intervals", "%+5", "-of", "json", filepath
    ]
    b_res = subprocess.run(b_cmd, capture_output=True, text=True)
    b_count = 0
    if b_res.returncode == 0:
        try:
            frames_data = json.loads(b_res.stdout)
            for f in frames_data.get("frames", []):
                if f.get("pict_type") == "B":
                    b_count += 1
        except Exception:
            pass

    return {
        "path": filepath,
        "codec": codec,
        "duration": duration,
        "start_time": start_time,
        "nb_frames": nb_frames,
        "b_frames_found": b_count
    }

def main():
    print("Scanning videos under cache/ and src/resource/ ...", flush=True)
    patterns = [
        "cache/**/*.mp4",
        "src/resource/**/*.mp4"
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))

    results = []
    for f in files:
        info = probe_video(f)
        if info:
            results.append(info)
            print(f"File: {info['path']}")
            print(f"  Codec: {info['codec']}, Dur: {info['duration']:.3f}s, Start: {info['start_time']:.3f}s, Frames: {info['nb_frames']}, B-frames in first 5s: {info['b_frames_found']}", flush=True)

if __name__ == "__main__":
    main()
