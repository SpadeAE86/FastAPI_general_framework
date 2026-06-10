import os
import subprocess
import hashlib

def extract_boundary_frames(video_path, out_dir, prefix, start_time, num_frames=15):
    os.makedirs(out_dir, exist_ok=True)
    frame_pattern = os.path.join(out_dir, f"{prefix}_frame_%03d.png")
    
    # Run ffmpeg to dump frames starting from start_time
    cmd = [
        "ffmpeg", "-y", "-ss", str(start_time), "-i", video_path,
        "-vframes", str(num_frames), frame_pattern
    ]
    subprocess.run(cmd, capture_output=True)
    
    hashes = []
    files = sorted([f for f in os.listdir(out_dir) if f.startswith(f"{prefix}_frame_")])
    for f in files:
        filepath = os.path.join(out_dir, f)
        with open(filepath, "rb") as fh:
            h = hashlib.md5(fh.read()).hexdigest()
        hashes.append(h)
        # Clean up files
        os.remove(filepath)
    return hashes

def count_duplicates(hashes):
    duplicates = 0
    prev_h = None
    for h in hashes:
        if prev_h is not None and h == prev_h:
            duplicates += 1
        prev_h = h
    return duplicates

def main():
    out_dir = r"./work/boundary_visuals_more"
    os.makedirs(out_dir, exist_ok=True)
    
    videos = {
        "final_nv_ts.mp4": "src/test/mp4_test/final_nv_ts.mp4",
        "final_nv_base_genpts.mp4": "src/test/mp4_test/final_nv_base_genpts.mp4",
        "final_nv_ptstest.mp4": "src/test/mp4_test/final_nv_ptstest.mp4",
        "final_nv_buf.mp4": "src/test/mp4_test/final_nv_buf.mp4",
    }
    
    print("="*80)
    print("ANALYSIS OF BOUNDARY DUP/FROZEN FRAMES AT t=4.0s FOR ADDITIONAL FILES")
    print("="*80)
    print(f"{'Filename':<30} | {'Frozen/Duplicate Frames at Start (of 15)':<40}")
    print("-" * 80)
    for name, path in videos.items():
        if os.path.exists(path):
            hashes = extract_boundary_frames(path, out_dir, name.replace(".", "_"), 4.0, 15)
            dups = count_duplicates(hashes)
            print(f"{name:<30} | {dups:2d} frames ({((dups * 1000) / 30):.1f} ms)")
        else:
            print(f"{name:<30} | Not Found")
    print("="*80)

if __name__ == "__main__":
    main()
