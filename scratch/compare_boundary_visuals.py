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
        hashes.append((f, h))
        # Clean up files
        os.remove(filepath)
    return hashes

def main():
    out_dir = r"./work/boundary_visuals"
    os.makedirs(out_dir, exist_ok=True)
    
    gpu_video = "src/test/mp4_test/final_nv_orig.mp4"
    cpu_video = "src/test/mp4_test/final_mp4.mp4"
    
    if not os.path.exists(gpu_video) or not os.path.exists(cpu_video):
        print(f"Error: test videos not found. GPU exist: {os.path.exists(gpu_video)}, CPU exist: {os.path.exists(cpu_video)}")
        return
        
    print("="*80)
    print("COMPARING BOUNDARY VISUAL FRAMES AT t=4.0s (GPU VS CPU)")
    print("="*80)
    
    # Extract frames right at the boundary (t=4.0s)
    gpu_frames = extract_boundary_frames(gpu_video, out_dir, "gpu", 4.0, 15)
    cpu_frames = extract_boundary_frames(cpu_video, out_dir, "cpu", 4.0, 15)
    
    print(f"{'Frame #':<8} | {'GPU Frame File & MD5 Hash':<40} | {'CPU Frame File & MD5 Hash':<40}")
    print("-" * 95)
    for idx in range(max(len(gpu_frames), len(cpu_frames))):
        gpu_str = f"{gpu_frames[idx][0]}: {gpu_frames[idx][1][:12]}..." if idx < len(gpu_frames) else "N/A"
        cpu_str = f"{cpu_frames[idx][0]}: {cpu_frames[idx][1][:12]}..." if idx < len(cpu_frames) else "N/A"
        print(f"{idx:<8} | {gpu_str:<40} | {cpu_str:<40}")
    print("-" * 95)
    
    # Analyze duplicates
    print("\nDuplicate Analysis:")
    print("-" * 25)
    
    def find_duplicates(frames, label):
        duplicates = 0
        prev_h = None
        for idx, (f, h) in enumerate(frames):
            if prev_h is not None and h == prev_h:
                print(f"  [{label}] Frame {idx} is a DUPLICATE of frame {idx-1}")
                duplicates += 1
            prev_h = h
        print(f"  [{label}] Total duplicate/frozen frames in first 15 frames: {duplicates}")
        
    find_duplicates(gpu_frames, "GPU (Unfixed)")
    find_duplicates(cpu_frames, "CPU (Baseline)")
    print("="*80)

if __name__ == "__main__":
    main()
