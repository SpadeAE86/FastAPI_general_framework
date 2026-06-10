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
        # If codec_type is not available in short show_entries, use the first stream
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
    out_dir = r"./work/reproduce"
    os.makedirs(out_dir, exist_ok=True)
    
    source_video = r"cache/0b/f5/a14205c09d01dd730d3a8a6ae709.mp4"
    if not os.path.exists(source_video):
        print(f"Error: source video not found at {source_video}")
        return
        
    sub_path = os.path.join(out_dir, "dummy_sub.png")
    if not os.path.exists(sub_path):
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black@0:s=1080x1920",
            "-vframes", "1", sub_path
        ], capture_output=True)

    segment_dur = 3.0
    
    # 1. GPU normalization commands
    gpu_files = []
    print("Generating 3 GPU-decoded normalized segments...", flush=True)
    for idx in range(3):
        out_file = os.path.join(out_dir, f"gpu_seg_{idx}.mp4")
        gpu_files.append(out_file)
        cmd = [
            "ffmpeg", "-y", "-ignore_editlist", "1",
            "-init_hw_device", "cuda=cuda0", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
            "-i", source_video, "-i", sub_path,
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
            "-filter_complex", 
            f"[0:v]trim=start=0.0:end={segment_dur},setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
            "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[no_cap_v];"
            f"[no_cap_v]trim=start=0:end={segment_dur},setpts=PTS-STARTPTS[trim_v];"
            "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];"
            f"[trim_v][sub0]overlay=enable='between(t,0.0,{segment_dur})',format=nv12[cap_v];"
            f"[2:a]atrim=start=0:end={segment_dur},asetpts=PTS-STARTPTS,apad=whole_dur={segment_dur}[final_a];"
            "[cap_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
            "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
            "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
            "-shortest", out_file
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            print(f"GPU Seg {idx} failed:", res.stderr.decode('utf-8', errors='ignore'))
            return

    # 2. CPU normalization commands (removing -hwaccel cuda)
    cpu_files = []
    print("Generating 3 CPU-decoded normalized segments...", flush=True)
    for idx in range(3):
        out_file = os.path.join(out_dir, f"cpu_seg_{idx}.mp4")
        cpu_files.append(out_file)
        cmd = [
            "ffmpeg", "-y", "-ignore_editlist", "1",
            # No hwaccel for input video
            "-i", source_video, "-i", sub_path,
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
            "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
            "-filter_complex", 
            # Trim first, format is already system memory, then scale & pad
            f"[0:v]trim=start=0.0:end={segment_dur},setpts=PTS-STARTPTS,format=nv12[v_pre];"
            "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[no_cap_v];"
            f"[no_cap_v]trim=start=0:end={segment_dur},setpts=PTS-STARTPTS[trim_v];"
            "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];"
            f"[trim_v][sub0]overlay=enable='between(t,0.0,{segment_dur})',format=nv12[cap_v];"
            f"[2:a]atrim=start=0:end={segment_dur},asetpts=PTS-STARTPTS,apad=whole_dur={segment_dur}[final_a];"
            # Upload to gpu for nvenc
            "[cap_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
            "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
            "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
            "-shortest", out_file
        ]
        # Make sure to specify the hardware device init so hwupload can derive from it
        cmd.insert(4, "-init_hw_device")
        cmd.insert(5, "cuda=cuda0")
        
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            print(f"CPU Seg {idx} failed:", res.stderr.decode('utf-8', errors='ignore'))
            return

    # 3. Concatenate GPU files
    gpu_list_path = os.path.join(out_dir, "gpu_list.txt")
    with open(gpu_list_path, "w", encoding="utf-8") as f:
        for filepath in gpu_files:
            f.write(f"file '{os.path.abspath(filepath)}'\n")
            
    gpu_concat_file = os.path.join(out_dir, "gpu_concat.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", gpu_list_path,
        "-c", "copy", gpu_concat_file
    ], capture_output=True)

    # 4. Concatenate CPU files
    cpu_list_path = os.path.join(out_dir, "cpu_list.txt")
    with open(cpu_list_path, "w", encoding="utf-8") as f:
        for filepath in cpu_files:
            f.write(f"file '{os.path.abspath(filepath)}'\n")
            
    cpu_concat_file = os.path.join(out_dir, "cpu_concat.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", cpu_list_path,
        "-c", "copy", cpu_concat_file
    ], capture_output=True)

    # 5. Output comparison results
    print("\n" + "="*80)
    print("REPRODUCTION RESULTS: GPU DECODING VS CPU DECODING")
    print("="*80)
    print(f"Target duration per clip: {segment_dur:.3f}s")
    print(f"Expected concatenated duration (3 clips): {segment_dur * 3:.3f}s (90 frames at 30fps)\n")
    
    print(f"{'Type':<12} | {'Clip 0 (Dur/Frames)':<22} | {'Clip 1 (Dur/Frames)':<22} | {'Clip 2 (Dur/Frames)':<22} | {'CONCAT (Dur/Frames)'}")
    print("-" * 115)
    
    gpu_info = [get_file_info(f) for f in gpu_files]
    gpu_c_info = get_file_info(gpu_concat_file)
    gpu_row = f"{'GPU (Cuda)':<12} | " + " | ".join(f"{info['duration']:.3f}s / {info['frames']:3d}" for info in gpu_info) + f" | {gpu_c_info['duration']:.3f}s / {gpu_c_info['frames']:3d}"
    print(gpu_row)
    
    cpu_info = [get_file_info(f) for f in cpu_files]
    cpu_c_info = get_file_info(cpu_concat_file)
    cpu_row = f"{'CPU Dec':<12} | " + " | ".join(f"{info['duration']:.3f}s / {info['frames']:3d}" for info in cpu_info) + f" | {cpu_c_info['duration']:.3f}s / {cpu_c_info['frames']:3d}"
    print(cpu_row)
    print("-" * 115)
    
    lost_dur = cpu_c_info['duration'] - gpu_c_info['duration']
    lost_frames = cpu_c_info['frames'] - gpu_c_info['frames']
    print(f"Loss due to GPU decoding startup frame drop: {lost_dur:.3f} seconds ({lost_frames} frames)")
    print(f"Average loss per segment: {lost_dur / 3:.3f} seconds ({(lost_frames / 3):.1f} frames)")
    print("="*80)

if __name__ == "__main__":
    main()
