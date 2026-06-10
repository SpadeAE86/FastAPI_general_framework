import subprocess
import os

def run_probe(filepath):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,r_frame_rate",
        "-of", "json", filepath
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout

def main():
    out_dir = r"./work/mix_107052"
    os.makedirs(out_dir, exist_ok=True)
    
    sub_path = os.path.join(out_dir, "subtitle0.png")
    source_video = r"cache/0b/f5/a14205c09d01dd730d3a8a6ae709.mp4"
    
    # GPU Decoded Command
    output_gpu = os.path.join(out_dir, "test_gpu.mp4")
    cmd_gpu = [
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
        "-shortest", output_gpu
    ]
    
    # CPU Decoded Command (removing -hwaccel cuda -hwaccel_output_format cuda)
    output_cpu = os.path.join(out_dir, "test_cpu.mp4")
    cmd_cpu = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-init_hw_device", "cuda=cuda0",
        "-i", source_video, "-i", sub_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        "[0:v]trim=start=0.0:end=2.865,setpts=PTS-STARTPTS,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[no_cap_v];"
        "[no_cap_v]trim=start=0:end=2.865,setpts=PTS-STARTPTS[trim_v];"
        "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];"
        "[trim_v][sub0]overlay=enable='between(t,0.0,2.8600000000000003)',format=nv12[cap_v];"
        "[2:a]atrim=start=0:end=2.865,asetpts=PTS-STARTPTS,apad=whole_dur=2.865[final_a];"
        "[cap_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
        "-shortest", output_cpu
    ]
    
    print("Running GPU decoded normalize...", flush=True)
    res_gpu = subprocess.run(cmd_gpu, capture_output=True, text=True)
    print("GPU STDERR:")
    print(res_gpu.stderr)
    
    print("Running CPU decoded normalize...", flush=True)
    res_cpu = subprocess.run(cmd_cpu, capture_output=True, text=True)
    print("CPU STDERR:")
    print(res_cpu.stderr)
    
    print("\nPROBE GPU:")
    print(run_probe(output_gpu))
    
    print("PROBE CPU:")
    print(run_probe(output_cpu))

if __name__ == "__main__":
    main()
