import os
import subprocess
import json

# Real video sources from mix_976
SOURCES = [
    "src/resource/mix_976/1770197220818_H.264_360x640_AAC_400.mp4",
    "src/resource/mix_976/1770197220820_H.264_360x640_AAC_400.mp4",
    "src/resource/mix_976/1770197220824_H.264_360x640_AAC_400.mp4"
]

W, H, FPS, TB = 640, 360, 30, 15360
SEGMENT_DUR = 3.0
OUT_DIR = r"./work/reproduce_stutter"

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

def run_normalization(src, out_file, mode):
    # Determine command based on mode
    # mode: 'cpu', 'gpu_unfixed', 'gpu_fixed'
    
    gpu_cuda_device_init = ["-init_hw_device", "cuda=cuda0"] if "gpu" in mode else []
    gpu_activate_flag = ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"] if "gpu" in mode else []
    gpu_encoder = ["-c:v", "h264_nvenc", "-preset", "12"] if "gpu" in mode else ["-c:v", "libx264", "-preset", "ultrafast"]
    
    # Complex filter structure
    # For CPU: 
    # [0:v]trim=start=0:end=3.0,setpts=PTS-STARTPTS,format=nv12[v_pre];
    # [v_pre]scale=640:360:force_original_aspect_ratio=decrease:flags=lanczos,pad=640:360:(ow-iw)/2:(oh-ih)/2:black[trim_v];
    # [1:a]atrim=start=0:end=3.0,asetpts=PTS-STARTPTS,apad=whole_dur=3.0[final_a]
    # For GPU:
    # [0:v]trim=start=0:end=3.0,setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre]; ...
    # And the post-filter for GPU:
    # unfixed: [trim_v]format=nv12,hwupload=derive_device=cuda[v_post]
    # fixed:   [trim_v]setpts=PTS-STARTPTS,format=nv12,hwupload=derive_device=cuda[v_post]
    
    if mode == 'cpu':
        vf = (
            f"[0:v]trim=start=0:end={SEGMENT_DUR},setpts=PTS-STARTPTS,format=nv12[v_pre];"
            f"[v_pre]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[v_post];"
            f"[1:a]atrim=start=0:end={SEGMENT_DUR},asetpts=PTS-STARTPTS,apad=whole_dur={SEGMENT_DUR}[final_a]"
        )
        end_v = "[v_post]"
    elif mode == 'gpu_unfixed':
        vf = (
            f"[0:v]trim=start=0:end={SEGMENT_DUR},setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
            f"[v_pre]scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black[trim_v];"
            f"[1:a]atrim=start=0:end={SEGMENT_DUR},asetpts=PTS-STARTPTS,apad=whole_dur={SEGMENT_DUR}[final_a];"
            f"[trim_v]format=nv12,hwupload=derive_device=cuda[v_post]"
        )
        end_v = "[v_post]"
    elif mode == 'gpu_fixed':
        vf = (
            f"[0:v]trim=start=0:end={SEGMENT_DUR},setpts=PTS-STARTPTS,hwdownload,format=nv12[v_pre];"
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

def concat_files(files, out_file, list_file):
    with open(list_file, "w", encoding="utf-8") as f:
        for filepath in files:
            f.write(f"file '{os.path.abspath(filepath)}'\n")
            
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file,
        "-c", "copy", out_file
    ], capture_output=True)

def analyze_packets(video):
    r = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_packets", "-show_entries", "packet=pts_time,size,flags",
        "-of", "csv=p=0", video
    ], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    packets = []
    for line in r.stdout.strip().split("\n"):
        parts = line.split(",")
        if len(parts) >= 3:
            try:
                packets.append({
                    "pts": float(parts[0]),
                    "size": int(parts[1]),
                    "is_key": "K" in parts[2]
                })
            except ValueError:
                pass
    return packets

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    modes = ['cpu', 'gpu_unfixed', 'gpu_fixed']
    
    results = {}
    
    for mode in modes:
        print(f"\nProcessing mode: {mode} ...", flush=True)
        mode_files = []
        for idx, src in enumerate(SOURCES):
            out_file = os.path.join(OUT_DIR, f"{mode}_seg_{idx}.mp4")
            run_normalization(src, out_file, mode)
            mode_files.append(out_file)
            info = get_file_info(out_file)
            print(f"  Segment {idx}: {info['duration']:.3f}s / {info['frames']} frames", flush=True)
            
        concat_file = os.path.join(OUT_DIR, f"{mode}_concat.mp4")
        list_file = os.path.join(OUT_DIR, f"{mode}_list.txt")
        concat_files(mode_files, concat_file, list_file)
        
        concat_info = get_file_info(concat_file)
        packets = analyze_packets(concat_file)
        
        # Calculate skip frames
        skip_count = sum(1 for p in packets if p['size'] < 200 and not p['is_key'])
        
        # Find boundary skips (near 3.0s and 6.0s)
        boundary_skips = []
        for p in packets:
            pts = p['pts']
            if p['size'] < 200 and not p['is_key']:
                if abs(pts - 3.0) < 0.25 or abs(pts - 6.0) < 0.25:
                    boundary_skips.append(p)
                    
        results[mode] = {
            "duration": concat_info.get("duration", 0.0),
            "frames": concat_info.get("frames", 0),
            "total_skips": skip_count,
            "boundary_skips_count": len(boundary_skips),
            "packets": packets
        }
        print(f"  CONCAT result: {concat_info['duration']:.3f}s / {concat_info['frames']} frames, Total Skips: {skip_count}, Boundary Skips: {len(boundary_skips)}", flush=True)

    print("\n" + "="*80)
    print("REPRODUCTION SUMMARY TABLE")
    print("="*80)
    print(f"{'Mode':<15} | {'Concat Dur':<12} | {'Concat Frames':<15} | {'Total Skips':<12} | {'Boundary Skips':<15}")
    print("-" * 80)
    for mode in modes:
        res = results[mode]
        print(f"{mode:<15} | {res['duration']:10.3f}s | {res['frames']:13d} | {res['total_skips']:12d} | {res['boundary_skips_count']:15d}")
    print("="*80)
    
    # Let's inspect the packets around the 3.0s boundary
    print("\n" + "="*80)
    print("DETAILED PACKET INSPECTION AROUND SEGMENT BOUNDARY (t = 3.0s)")
    print("="*80)
    print(f"{'Mode':<12} | {'Frame PTS':<12} | {'Packet Size (Bytes)':<22} | {'Type'}")
    print("-" * 80)
    for mode in modes:
        res = results[mode]
        boundary_packets = [p for p in res['packets'] if 2.9 <= p['pts'] <= 3.2]
        for p in boundary_packets:
            p_type = "I (Key)" if p['is_key'] else ("P (Skip)" if p['size'] < 200 else "P (Normal)")
            print(f"{mode:<12} | {p['pts']:10.6f}s | {p['size']:18d} | {p_type}")
        print("-" * 80)

if __name__ == "__main__":
    main()
