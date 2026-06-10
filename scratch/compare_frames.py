import subprocess
import os
import hashlib

def extract_frame_hashes(video_path, out_dir, prefix):
    # Extract frames as png
    os.makedirs(out_dir, exist_ok=True)
    frame_pattern = os.path.join(out_dir, f"{prefix}_frame_%04d.png")
    
    # Run ffmpeg to dump frames
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vsync", "0", frame_pattern
    ]
    subprocess.run(cmd, capture_output=True)
    
    # Calculate md5 for each frame file
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
    out_dir = r"./work/compare_frames"
    os.makedirs(out_dir, exist_ok=True)
    
    gpu_video = r"./work/reproduce_debug/gpu_debug.mp4"
    
    # Generate CPU debug video if not exists
    cpu_video = r"./work/reproduce_debug/cpu_debug.mp4"
    if not os.path.exists(cpu_video):
        source_video = r"cache/0b/f5/a14205c09d01dd730d3a8a6ae709.mp4"
        cmd_cpu = [
            "ffmpeg", "-y", "-ignore_editlist", "1",
            "-init_hw_device", "cuda=cuda0",
            "-i", source_video,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
            "-filter_complex", 
            "[0:v]trim=start=0.0:end=3.0,setpts=PTS-STARTPTS,format=nv12[v_pre];"
            "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
            "[1:a]atrim=start=0:end=3.0,asetpts=PTS-STARTPTS,apad=whole_dur=3.0[final_a];"
            "[trim_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
            "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
            "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
            "-shortest", cpu_video
        ]
        subprocess.run(cmd_cpu, capture_output=True)
        
    print("Extracting frames from GPU video...")
    gpu_hashes = extract_frame_hashes(gpu_video, out_dir, "gpu")
    print("Extracting frames from CPU video...")
    cpu_hashes = extract_frame_hashes(cpu_video, out_dir, "cpu")
    
    print(f"\nGPU frames: {len(gpu_hashes)}, CPU frames: {len(cpu_hashes)}")
    
    # Check for shift
    # If first frame of GPU matches CPU frame at index S:
    found_match = False
    for S in range(len(cpu_hashes) - 5):
        # Compare first few hashes
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
            print(f"\n[OK] Found frame shift match! The GPU video starts at CPU frame index {S}.")
            print(f"This represents a drop of exactly {S} frames ({(S * 1000 / 30):.1f} ms).")
            found_match = True
            break
            
    if not found_match:
        print("\n[FAIL] No frame shift match found within the first few frames.")
        # Print first 5 hashes of both
        print("First 5 GPU hashes:", gpu_hashes[:5])
        print("First 5 CPU hashes:", cpu_hashes[:5])

if __name__ == "__main__":
    main()
