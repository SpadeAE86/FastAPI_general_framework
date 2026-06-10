import subprocess
import json
import os

def check_audio(filepath):
    print(f"\n=== Inspecting {filepath} ===")
    if not os.path.exists(filepath):
        print("File does not exist!")
        return
    
    # 1. Probe audio streams
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=index,codec_name,sample_rate,channels,channel_layout",
        "-of", "json", filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        streams = json.loads(res.stdout).get("streams", [])
        if not streams:
            print("No audio streams found!")
            return
        for s in streams:
            print(f"Audio Stream: Index {s.get('index')}, Codec: {s.get('codec_name')}, "
                  f"Sample Rate: {s.get('sample_rate')}Hz, Channels: {s.get('channels')}, "
                  f"Layout: {s.get('channel_layout')}")
    else:
        print("Failed to probe audio streams:", res.stderr)
        return

    # 2. Get audio statistics (mean volume, max volume)
    # This filter calculates the volume statistics of the audio stream.
    cmd_stats = [
        "ffmpeg", "-i", filepath, "-af", "volumedetect", "-f", "null", "NUL" if os.name == "nt" else "/dev/null"
    ]
    res_stats = subprocess.run(cmd_stats, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    # Search for volumedetect output in stderr
    for line in res_stats.stderr.splitlines():
        if "parsed_volumedetect" in line or "mean_volume" in line or "max_volume" in line:
            print(line.strip())

if __name__ == "__main__":
    work_dir = "./work/mix_7176"
    seg0 = os.path.join(work_dir, "segment_0_000.mp4")
    norm0 = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    norm1 = os.path.join(work_dir, "normalized_10.4_33.77_1_706421858ca5c617f71080ad52db.mp4")
    
    check_audio(seg0)
    check_audio(norm0)
    check_audio(norm1)
