import os
import subprocess
import json

def main():
    work_dir = r"c:\Job\AI\mix\AIGC_video_mix_remake\work\mix_107052"
    if not os.path.exists(work_dir):
        print(f"Directory {work_dir} does not exist!")
        return
        
    files = sorted([f for f in os.listdir(work_dir) if f.startswith("normalized_") and f.endswith(".mp4")])
    print(f"Found {len(files)} normalized files.")
    
    print(f"{'File':<50} | {'Video Dur':<10} | {'Audio Dur':<10} | {'Frames':<6} | {'FPS':<6}")
    print("-" * 90)
    for f in files:
        path = os.path.join(work_dir, f)
        # Probe
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,duration,nb_frames,r_frame_rate",
            "-of", "json", path
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"Failed to probe {f}")
            continue
            
        data = json.loads(res.stdout)
        streams = data.get("streams", [])
        v_dur = "N/A"
        a_dur = "N/A"
        frames = "N/A"
        fps = "N/A"
        for s in streams:
            codec_type = s.get("codec_type")
            if codec_type == "video":
                v_dur = s.get("duration", "N/A")
                frames = s.get("nb_frames", "N/A")
                fps = s.get("r_frame_rate", "N/A")
            elif codec_type == "audio":
                a_dur = s.get("duration", "N/A")
                
        print(f"{f:<50} | {v_dur:<10} | {a_dur:<10} | {frames:<6} | {fps:<6}")

if __name__ == "__main__":
    main()
