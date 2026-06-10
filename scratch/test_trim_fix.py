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
    
    # 1. Original Command (setpts after trim)
    output_orig = os.path.join(out_dir, "test_orig.mp4")
    cmd_orig = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-i", source_video, "-i", sub_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        "[0:v]trim=start=0.0:end=2.865,setpts=PTS-STARTPTS,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[no_cap_v];"
        "[no_cap_v]trim=start=0:end=2.865,setpts=PTS-STARTPTS[trim_v];"
        "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];"
        "[trim_v][sub0]overlay=enable='between(t,0.0,2.8600000000000003)',format=nv12[cap_v];"
        "[2:a]atrim=start=0:end=2.865,asetpts=PTS-STARTPTS,apad=whole_dur=2.865[final_a]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[cap_v]", "-map", "[final_a]",
        "-shortest", output_orig
    ]
    
    # 2. Fixed Command (setpts before trim)
    output_fixed = os.path.join(out_dir, "test_fixed.mp4")
    cmd_fixed = [
        "ffmpeg", "-y", "-ignore_editlist", "1",
        "-i", source_video, "-i", sub_path,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-fps_mode", "cfr", "-r", "30", "-c:v", "h264_nvenc", "-preset", "12",
        "-filter_complex", 
        "[0:v]setpts=PTS-STARTPTS,trim=start=0.0:end=2.865,setpts=PTS-STARTPTS,format=nv12[v_pre];"
        "[v_pre]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black[no_cap_v];"
        "[no_cap_v]setpts=PTS-STARTPTS,trim=start=0:end=2.865,setpts=PTS-STARTPTS[trim_v];"
        "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];"
        "[trim_v][sub0]overlay=enable='between(t,0.0,2.8600000000000003)',format=nv12[cap_v];"
        "[2:a]atrim=start=0:end=2.865,asetpts=PTS-STARTPTS,apad=whole_dur=2.865[final_a]",
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero", "-map", "[cap_v]", "-map", "[final_a]",
        "-shortest", output_fixed
    ]
    
    print("Running original command (setpts after trim)...", flush=True)
    res_orig = subprocess.run(cmd_orig, capture_output=True, text=True)
    print("ORIGINAL STDERR:")
    print(res_orig.stderr)
    
    print("Running fixed command (setpts before trim)...", flush=True)
    res_fixed = subprocess.run(cmd_fixed, capture_output=True, text=True)
    print("FIXED STDERR:")
    print(res_fixed.stderr)
    
    print("\nPROBE ORIGINAL:")
    res_probe_orig = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,r_frame_rate",
        "-of", "json", output_orig
    ], capture_output=True, text=True)
    print(res_probe_orig.stdout)
    if res_probe_orig.stderr:
        print("PROBE ORIG STDERR:", res_probe_orig.stderr)
    
    print("PROBE FIXED:")
    res_probe_fixed = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration:stream=nb_frames,r_frame_rate",
        "-of", "json", output_fixed
    ], capture_output=True, text=True)
    print(res_probe_fixed.stdout)
    if res_probe_fixed.stderr:
        print("PROBE FIXED STDERR:", res_probe_fixed.stderr)

if __name__ == "__main__":
    main()
