import subprocess
import os
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
    test_dir = "src/test/mp4_test"
    
    print("="*90)
    print("COMPARING PRE-COMPILED CONCAT VIDEOS: CPU baseline vs GPU variants")
    print("="*90)
    print(f"{'File':<25} | {'Duration':<12} | {'Frames':<10} | {'Difference from CPU (Dur / Frames)'}")
    print("-" * 90)
    
    files = {
        "final_mp4.mp4": "CPU Baseline",
        "final_nv_orig.mp4": "GPU Raw (Original)",
        "final_nv_fixA.mp4": "GPU Fix A (RC)",
        "final_nv_fixB.mp4": "GPU Fix B (GOP)",
        "final_nv_fixC.mp4": "GPU Fix C (Combined)"
    }
    
    cpu_info = None
    for filename, desc in files.items():
        filepath = os.path.join(test_dir, filename)
        if not os.path.exists(filepath):
            print(f"{filename:<25} | Not found")
            continue
        info = get_file_info(filepath)
        if filename == "final_mp4.mp4":
            cpu_info = info
            diff_str = "Baseline"
        elif cpu_info:
            diff_dur = info["duration"] - cpu_info["duration"]
            diff_frames = info["frames"] - cpu_info["frames"]
            diff_str = f"{diff_dur:+.3f}s / {diff_frames:+d} frames"
        else:
            diff_str = "N/A"
            
        print(f"{filename:<25} | {info['duration']:8.3f}s | {info['frames']:6d} | {diff_str} ({desc})")

if __name__ == "__main__":
    main()
