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
    out_dir = r"./work/reproduce_no_shortest"
    os.makedirs(out_dir, exist_ok=True)
    
    source_video = r"cache/0b/f5/a14205c09d01dd730d3a8a6ae709.mp4"
    segment_dur = 3.0

    # 1. GPU decoding (WITHOUT -shortest)
    gpu_file = os.path.join(out_dir, "gpu_no_shortest.mp4")
    cmd_gpu = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-init_hw_device", "cuda=cuda0", "-hwaccel", "cuda", "-hwaccel_output_format", "cuda",
        "-i", source_video,
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        f"[0:v]trim=start=0.0:end={segment_dur},setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
        f"[1:a]atrim=start=0:end={segment_dur},asetpts=PTS-STARTPTS,apad=whole_dur={segment_dur}[final_a];"
        "[trim_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
        gpu_file
    ]
    res_gpu = subprocess.run(cmd_gpu, capture_output=True)
    if res_gpu.returncode != 0:
        print("GPU failed:", res_gpu.stderr.decode('utf-8', errors='ignore'))
        return

    # 2. CPU decoding (WITHOUT -shortest)
    cpu_file = os.path.join(out_dir, "cpu_no_shortest.mp4")
    cmd_cpu = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-init_hw_device", "cuda=cuda0",
        "-i", source_video,
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        f"[0:v]trim=start=0.0:end={segment_dur},setpts=PTS-STARTPTS,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
        f"[1:a]atrim=start=0:end={segment_dur},asetpts=PTS-STARTPTS,apad=whole_dur={segment_dur}[final_a];"
        "[trim_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[v_post]", "-map", "[final_a]",
        cpu_file
    ]
    res_cpu = subprocess.run(cmd_cpu, capture_output=True)
    if res_cpu.returncode != 0:
        print("CPU failed:", res_cpu.stderr.decode('utf-8', errors='ignore'))
        return

    # 3. Print info
    gpu_info = get_file_info(gpu_file)
    cpu_info = get_file_info(cpu_file)
    
    print("\n" + "="*60)
    print("NO-SHORT-FLAG DECODING COMPARISON")
    print("="*60)
    print(f"GPU Decoded Duration: {gpu_info['duration']:.3f}s / {gpu_info['frames']} frames")
    print(f"CPU Decoded Duration: {cpu_info['duration']:.3f}s / {cpu_info['frames']} frames")
    print("="*60)

if __name__ == "__main__":
    main()
