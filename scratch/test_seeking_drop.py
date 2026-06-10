import os
import subprocess
import json

# Real video source
SOURCE = "src/resource/mix_2045/1772606105011_H.264_640x360_400.mp4"
W, H, FPS, TB = 640, 360, 30, 15360
START_TIME = 5.0
END_TIME = 8.0
SEGMENT_DUR = END_TIME - START_TIME # 3.0s
OUT_DIR = r"./work/test_seeking"

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

def run_seeking_normalization(src, out_file, mode):
    gpu_cuda_device_init = ["-init_hw_device", "cuda=cuda0"] if "gpu" in mode else []
    gpu_activate_flag = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"] if "gpu" in mode else []
    gpu_encoder = ["-c:v", "h264_nvenc", "-preset", "12"] if "gpu" in mode else ["-c:v", "libx264", "-preset", "ultrafast"]
    
    # Notice that we seek using -ss and -to as output options (after -i) just like the codebase does
    # Wait, the codebase actually seeks via filter complex (trim=start=X:end=Y) or seeks via segment command.
    # Let's use the exact trim filter complex method from normalize_video.py:
    # "trim=start={raw_start_time}:end={raw_end_time},setpts=PTS-STARTPTS"
    
    if mode == 'cpu':
        vf = (
            f"[0:v]trim=start={START_TIME}:end={END_TIME},setpts=PTS-STARTPTS,format=nv12[v_pre];"
            f"[v_pre]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[v_post];"
            f"[1:a]atrim=start=0:end={SEGMENT_DUR},asetpts=PTS-STARTPTS,apad=whole_dur={SEGMENT_DUR}[final_a]"
        )
        end_v = "[v_post]"
    elif mode == 'gpu_unfixed':
        # Unfixed GPU: without setpts=PTS-STARTPTS right before hwupload
        vf = (
            f"[0:v]trim=start={START_TIME}:end={END_TIME},setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
            f"[v_pre]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
            f"[1:a]atrim=start=0:end={SEGMENT_DUR},asetpts=PTS-STARTPTS,apad=whole_dur={SEGMENT_DUR}[final_a];"
            f"[trim_v]format=nv12,hwupload=derive_device=cuda[v_post]"
        )
        end_v = "[v_post]"
    elif mode == 'gpu_fixed':
        # Fixed GPU: has setpts=PTS-STARTPTS right before hwupload
        vf = (
            f"[0:v]trim=start={START_TIME}:end={END_TIME},setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
            f"[v_pre]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
            f"[1:a]atrim=start=0:end={SEGMENT_DUR},asetpts=PTS-STARTPTS,apad=whole_dur={SEGMENT_DUR}[final_a];"
            f"[trim_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]"
        )
        end_v = "[v_post]"
        
    cmd = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        *gpu_cuda_device_init,
        *gpu_activate_flag,
        "-i", src,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", str(FPS),
        *gpu_encoder,
        "-filter_complex", vf,
        "-ar", "44100", "-ac", "2",
        "-video_track_timescale", str(TB),
        "-avoid_negative_ts", "make_zero",
        "-map", end_v, "-map", "[final_a]",
        "-shortest", out_file
    ]
    
    subprocess.run(cmd, capture_output=True)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    modes = ['cpu', 'gpu_unfixed', 'gpu_fixed']
    
    print("="*80)
    print(f"TESTING SEEKING NORMALIZATION (start={START_TIME}s, end={END_TIME}s)")
    print("="*80)
    
    for mode in modes:
        out_file = os.path.join(OUT_DIR, f"{mode}_seek.mp4")
        run_seeking_normalization(SOURCE, out_file, mode)
        info = get_file_info(out_file)
        print(f"Mode: {mode:<12} | Dur: {info['duration']:.3f}s | Frames: {info['frames']}")
    print("="*80)

if __name__ == "__main__":
    main()
