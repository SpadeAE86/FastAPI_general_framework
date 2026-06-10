import subprocess
import os

def main():
    source_video = r"cache/0b/f5/a14205c09d01dd730d3a8a6ae709.mp4"
    out_dir = r"./work/reproduce_debug"
    os.makedirs(out_dir, exist_ok=True)
    gpu_file = os.path.join(out_dir, "gpu_debug.mp4")
    
    cmd_gpu = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-init_hw_device", "cuda=cuda0", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
        "-i", source_video,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        "[0:v]trim=start=0.0:end=3.0,setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
        "[1:a]atrim=start=0:end=3.0,asetpts=PTS-STARTPTS,apad=whole_dur=3.0[final_a];"
        "[trim_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
        "-shortest", gpu_file
    ]
    
    print("Running GPU command...")
    res = subprocess.run(cmd_gpu, capture_output=True, text=True)
    print("GPU COMMAND Return Code:", res.returncode)
    print("\nGPU COMMAND STDERR:\n", res.stderr)

if __name__ == "__main__":
    main()
