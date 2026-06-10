import subprocess
import json

def main():
    video_path = r"C:\Users\25065\Downloads\final-1781068668938.mp4"
    
    print("="*80)
    print("ANALYZING USER VIDEO FRAME TIMESTAMPS")
    print("="*80)
    
    # Run ffprobe to get all frame PTS
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=pts_time", "-of", "json", video_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("Failed to run ffprobe on the video file.")
        return
        
    try:
        data = json.loads(res.stdout)
        frames = data.get("frames", [])
        print(f"Total video frames found: {len(frames)}")
        
        if not frames:
            print("No video frames found in the stream.")
            return
            
        pts_list = [float(f["pts_time"]) for f in frames if "pts_time" in f]
        pts_list.sort()
        
        print(f"First frame PTS: {pts_list[0]:.6f}s")
        print(f"Last frame PTS:  {pts_list[-1]:.6f}s")
        print(f"Calculated Duration (last - first): {pts_list[-1] - pts_list[0]:.6f}s")
        
        # Check for gaps
        expected_interval = 1.0 / 30.0 # 0.033333
        gaps = []
        for i in range(1, len(pts_list)):
            diff = pts_list[i] - pts_list[i-1]
            if diff > expected_interval * 1.5:
                gaps.append((i-1, i, pts_list[i-1], pts_list[i], diff))
                
        print(f"\nFound {len(gaps)} PTS gaps:")
        for idx, (p1, p2, t1, t2, d) in enumerate(gaps[:20]):
            print(f"  Gap {idx:02d}: Frame {p1} ({t1:.6f}s) -> Frame {p2} ({t2:.6f}s), Gap = {d:.6f}s (approx {round(d/expected_interval)} frames)")
        if len(gaps) > 20:
            print(f"  ... and {len(gaps) - 20} more gaps")
            
    except Exception as e:
        print(f"Error during analysis: {e}")
    print("="*80)

if __name__ == "__main__":
    main()
