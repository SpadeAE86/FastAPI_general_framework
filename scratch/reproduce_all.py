import os
import subprocess
import hashlib

def extract_boundary_frames(video_path, out_dir, prefix, start_time, num_frames=12):
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
        os.remove(filepath)
    return hashes

def main():
    out_dir = r"./work/reproduce_final"
    os.makedirs(out_dir, exist_ok=True)
    
    # Pre-compiled files representing different schemes
    cpu_path = "src/test/mp4_test/final_mp4.mp4"
    gpu_unfixed_path = "src/test/mp4_test/final_nv_orig.mp4"
    gpu_fixed_path = "src/test/mp4_test/final_nv_ptstest.mp4"
    
    print("=" * 80)
    print("      LOCAL REPRODUCTION: GPU DECODING FRAME DROPS & FREEZES AT BOUNDARIES")
    print("=" * 80)
    
    print("\n[1] Boundary Analysis at t=4.0s (First segment transition):")
    print("-" * 80)
    
    num_frames = 12
    cpu_hashes = extract_boundary_frames(cpu_path, out_dir, "cpu", 4.0, num_frames)
    gpu_unfixed_hashes = extract_boundary_frames(gpu_unfixed_path, out_dir, "gpu_unfixed", 4.0, num_frames)
    gpu_fixed_hashes = extract_boundary_frames(gpu_fixed_path, out_dir, "gpu_fixed", 4.0, num_frames)
    
    print(f"{'Frame #':<8} | {'CPU (Baseline) MD5':<22} | {'GPU Unfixed MD5':<22} | {'GPU Fixed MD5':<22}")
    print("-" * 80)
    
    for idx in range(num_frames):
        cpu_h = cpu_hashes[idx][:12] if idx < len(cpu_hashes) else "N/A"
        gpu_unf = gpu_unfixed_hashes[idx][:12] if idx < len(gpu_unfixed_hashes) else "N/A"
        gpu_fix = gpu_fixed_hashes[idx][:12] if idx < len(gpu_fixed_hashes) else "N/A"
        
        # Mark duplicates
        cpu_mark = " (frozen)" if idx > 0 and cpu_hashes[idx] == cpu_hashes[idx-1] else ""
        gpu_unf_mark = " (frozen)" if idx > 0 and gpu_unfixed_hashes[idx] == gpu_unfixed_hashes[idx-1] else ""
        gpu_fix_mark = " (frozen)" if idx > 0 and gpu_fixed_hashes[idx] == gpu_fixed_hashes[idx-1] else ""
        
        print(f"Frame {idx:02d} | {cpu_h + cpu_mark:<22} | {gpu_unf + gpu_unf_mark:<22} | {gpu_fix + gpu_fix_mark:<22}")
        
    print("-" * 80)
    
    # Calculate duplicate count
    def get_dup_count(hashes):
        return sum(1 for i in range(1, len(hashes)) if hashes[i] == hashes[i-1])
        
    cpu_dups = get_dup_count(cpu_hashes)
    gpu_unf_dups = get_dup_count(gpu_unfixed_hashes)
    gpu_fix_dups = get_dup_count(gpu_fixed_hashes)
    
    print("\n[2] Summary Table:")
    print("-" * 80)
    print(f"{'Normalization Scheme':<25} | {'Visual Freeze Duration at Boundary':<35} | {'Frozen Frames'}")
    print("-" * 80)
    print(f"{'CPU (Baseline)':<25} | {cpu_dups * 33.33:6.1f} ms                          | {cpu_dups:2d} frames")
    print(f"{'GPU (Unfixed)':<25} | {gpu_unf_dups * 33.33:6.1f} ms                          | {gpu_unf_dups:2d} frames")
    print(f"{'GPU (Fixed)':<25} | {gpu_fix_dups * 33.33:6.1f} ms                          | {gpu_fix_dups:2d} frames")
    print("=" * 80)

if __name__ == "__main__":
    main()
