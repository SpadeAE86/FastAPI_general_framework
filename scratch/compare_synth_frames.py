import subprocess
import os
import hashlib

def extract_frame_hashes(video_path, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    frame_pattern = os.path.join(out_dir, f"{prefix}_frame_%04d.png")
    
    # Run ffmpeg to dump frames
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vsync", "0", frame_pattern
    ]
    subprocess.run(cmd, capture_output=True)
    
    hashes = []
    files = sorted([f for f in os.listdir(out_dir) if f.startswith(f"{prefix}_frame_")])
    for f in files:
        filepath = os.path.join(out_dir, f)
        with open(filepath, "rb") as fh:
            h = hashlib.md5(fh.read()).hexdigest()
        hashes.append(h)
        # Clean up
        os.remove(filepath)
    return hashes

def main():
    out_dir = r"./work/compare_synth"
    os.makedirs(out_dir, exist_ok=True)
    
    print("="*60)
    print("COMPARING PRE-GENERATED TEST CLIPS (GPU VS CPU DECODING)")
    print("="*60)
    
    for idx in range(4):
        gpu_video = f"src/test/mp4_test/synth_gpu_{idx}.mp4"
        cpu_video = f"src/test/mp4_test/synth_cpu_{idx}.mp4"
        
        if not os.path.exists(gpu_video) or not os.path.exists(cpu_video):
            print(f"Clip {idx}: Not found (GPU exists: {os.path.exists(gpu_video)}, CPU exists: {os.path.exists(cpu_video)})")
            continue
            
        gpu_hashes = extract_frame_hashes(gpu_video, out_dir, f"gpu_{idx}")
        cpu_hashes = extract_frame_hashes(cpu_video, out_dir, f"cpu_{idx}")
        
        # Check for shift
        found_match = False
        for S in range(0, 20):
            match = True
            for i in range(10):
                if i < len(gpu_hashes) and S + i < len(cpu_hashes):
                    if gpu_hashes[i] != cpu_hashes[S + i]:
                        match = False
                        break
                else:
                    match = False
                    break
            if match:
                shift_str = f"starts at CPU frame {S} (drop of {S} frames / {(S * 1000 / 30):.1f}ms)" if S > 0 else "is identical (0 frames drop)"
                print(f"Clip {idx:2d} | GPU frames: {len(gpu_hashes):3d} | CPU frames: {len(cpu_hashes):3d} | Result: {shift_str}")
                found_match = True
                break
                
        if not found_match:
            print(f"Clip {idx:2d} | GPU frames: {len(gpu_hashes):3d} | CPU frames: {len(cpu_hashes):3d} | Result: No match found")

if __name__ == "__main__":
    main()
