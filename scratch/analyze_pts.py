import subprocess
import json

def main():
    video_path = r"C:\Users\25065\Downloads\final-1781060457662.mp4"
    
    cmd_v = [
        "ffprobe", "-v", "error", "-show_frames", "-select_streams", "v",
        "-show_entries", "frame=pts_time,pict_type", "-of", "json", video_path
    ]
    print("Running ffprobe on frames...")
    res_v = subprocess.run(cmd_v, capture_output=True, text=True)
    if res_v.returncode != 0:
        print("Error running ffprobe:", res_v.stderr)
        return
        
    data = json.loads(res_v.stdout)
    frames = data.get("frames", [])
    print(f"Total Video Frames: {len(frames)}")
    
    # Check for non-monotonic PTS or large gaps
    prev_pts = -1.0
    gaps = []
    for idx, f in enumerate(frames):
        pts = float(f.get("pts_time", 0.0))
        if prev_pts >= 0.0:
            diff = pts - prev_pts
            # At 30fps, expected diff is 1/30 = 0.0333s. If diff is significantly larger or smaller, log it
            if diff > 0.04 or diff < 0.03:
                gaps.append((idx, prev_pts, pts, diff))
        prev_pts = pts
        
    print(f"Number of frame timestamp anomalies (gaps/overlaps): {len(gaps)}")
    if gaps:
        print("Anomalies details (first 20):")
        for idx, prev, curr, diff in gaps[:20]:
            print(f"  Frame {idx:4d}: gap from {prev:.3f}s to {curr:.3f}s (diff = {diff:.3f}s)")
            
    # Print the last 10 frames
    print("\nLast 10 Frames:")
    for idx, f in enumerate(frames[-10:]):
        frame_idx = len(frames) - 10 + idx
        print(f"  Frame {frame_idx:4d}: pts_time={f.get('pts_time')}, pict_type={f.get('pict_type')}")

if __name__ == "__main__":
    main()
