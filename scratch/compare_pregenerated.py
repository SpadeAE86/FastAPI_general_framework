import os
import subprocess
import json

def get_file_info(filepath):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,duration,r_frame_rate",
        "-of", "json", filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        return {"error": res.stderr}
    try:
        data = json.loads(res.stdout)
        v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        if not v_stream and data.get("streams"):
            v_stream = data["streams"][0]
        return {
            "duration": float(v_stream.get("duration", 0.0)),
            "frames": int(v_stream.get("nb_frames", 0)),
            "fps": v_stream.get("r_frame_rate", "N/A")
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    files = [
        "src/test/mp4_test/nv_orig_2.mp4",
        "src/test/mp4_test/nv_fixA_2.mp4",
        "src/test/mp4_test/nv_fixB_2.mp4",
        "src/test/mp4_test/nv_fixC_2.mp4",
        "src/test/mp4_test/nv_trimmed_2.mp4",
    ]
    
    print(f"{'Filename':<30} | {'Duration':<10} | {'Frames':<10} | {'FPS':<10}")
    print("-" * 70)
    for f in files:
        if os.path.exists(f):
            info = get_file_info(f)
            print(f"{os.path.basename(f):<30} | {info['duration']:8.3f}s | {info['frames']:8d} | {info['fps']:<10}")
        else:
            print(f"{os.path.basename(f):<30} | Not Found")

if __name__ == "__main__":
    main()
