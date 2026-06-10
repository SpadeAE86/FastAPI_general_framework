import subprocess
import os

def main():
    out_dir = r"./work/mix_107052"
    os.makedirs(out_dir, exist_ok=True)
    
    # Create subtitle0.png if not exists (dummy 1080x1920 transparent image)
    sub_path = os.path.join(out_dir, "subtitle0.png")
    if not os.path.exists(sub_path):
        print("Creating dummy subtitle0.png...", flush=True)
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black@0:s=1080x1920",
            "-vframes", "1", sub_path
        ], capture_output=True)
        
    source_video = r"C:\Job\AI\mix\AIGC_video_mix_remake\cache\0b\f5\a14205c09d01dd730d3a8a6ae709.mp4"
    if not os.path.exists(source_video):
        print(f"ERROR: source_video does not exist at {source_video}", flush=True)
        # Try relative cache
        source_video = r"cache/0b/f5/a14205c09d01dd730d3a8a6ae709.mp4"
        if not os.path.exists(source_video):
            print(f"ERROR: relative source_video also does not exist!", flush=True)
            return
            
    output_video = os.path.join(out_dir, "test_shortest.mp4")
    
    # Run ffmpeg with -shortest
    cmd = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-init_hw_device", "cuda=cuda0", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
        "-i", source_video, "-i", sub_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        "[0:v]trim=start=0.0:end=2.865,setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[no_cap_v];"
        "[no_cap_v]trim=start=0:end=2.865,setpts=PTS-STARTPTS[trim_v];"
        "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];"
        "[trim_v][sub0]overlay=enable='between(t,0.0,2.8600000000000003)',format=nv12[cap_v];"
        "[2:a]atrim=start=0:end=2.865,asetpts=PTS-STARTPTS,apad=whole_dur=2.865[final_a];"
        "[cap_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
        "-shortest", output_video
    ]
    
    print("Running FFMPEG with -shortest...", flush=True)
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print("FFMPEG failed:", res.stderr.decode('utf-8', errors='ignore'), flush=True)
        return
        
    # Probe duration and frame count
    probe_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,r_frame_rate",
        "-of", "json", output_video
    ]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)
    print("\nProbed Output (with -shortest):", flush=True)
    print(probe_res.stdout, flush=True)
    
    # Let's run without -shortest
    output_no_shortest = os.path.join(out_dir, "test_no_shortest.mp4")
    cmd_no_shortest = [c for c in cmd if c != "-shortest"]
    cmd_no_shortest[-1] = output_no_shortest
    
    print("Running FFMPEG without -shortest...", flush=True)
    subprocess.run(cmd_no_shortest, capture_output=True)
    probe_res_no = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,r_frame_rate",
        "-of", "json", output_no_shortest
    ], capture_output=True, text=True)
    print("\nProbed Output (WITHOUT -shortest):", flush=True)
    print(probe_res_no.stdout, flush=True)

if __name__ == "__main__":
    main()
