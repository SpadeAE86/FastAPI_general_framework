import subprocess
import os

if __name__ == "__main__":
    seg_mp4 = r"./work/mix_7176/segment_0_000.mp4"
    cache_files = [
        "cache/9b/ee/19be254a7b21608baa66975d55e9.wav",
        "cache/46/17/78eee3daedcb41dd345f2c9033fb.wav",
        "cache/20/c9/0aedaab37e5cc9ff2b2c3ef3b180.wav",
        "cache/e1/c5/2e54a12f83b2c71ec0b7a890833f.wav",
        "cache/a7/27/e0e48021693287b43bcd8dfbbb49.wav",
        "cache/78/48/32c21260aa811b7884382215bbfb.wav",
        "cache/63/ce/914337f7ebfa3b541a6f4751c79a.wav",
        "cache/60/10/3b5cf849b354c82d2c9b0da18031.wav",
        "cache/7b/f0/ac247dc85cb3491a65f3bfd7ddc7.wav",
        "cache/e2/47/0631830f9665e7a070148e4f5bf0.wav",
        "cache/ec/c9/c31c9aba872a55d737814e8429da.wav",
        "cache/b1/5b/a5fcf7357c9ef1309e1b841ff6cc.wav",
        "cache/cc/db/d4cd88a06c00cd49100e45e72106.wav",
        "cache/04/d2/9484c68aeeef7ed74734b77fc226.wav"
    ]
    
    cmd = [
        "ffmpeg", "-y", "-ignore_editlist", "1", "-noautorotate", "-fflags", "+genpts",
        "-i", seg_mp4
    ]
    
    for i in range(14):
        cmd.extend(["-loop", "1", "-i", f"work/mix_7176/subtitle{i}.png"])
        
    for f in cache_files:
        cmd.extend(["-i", f])
        
    filter_parts = []
    # Video filters
    filter_parts.append("[0:v]setpts=PTS-STARTPTS,trim=start=0.0:end=10.4,setpts=PTS-STARTPTS[v_pre]")
    filter_parts.append("[v_pre]scale=1440:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1440:1080:(ow-iw)/2:(oh-ih)/2:black,colorbalance=rs=0.0:gs=-0.0:bs=0.0:rm=0.0:gm=-0.0:bm=0.0:rh=0.0:gh=-0.0:bh=0.0,colorbalance=rs=0.0:rm=0.0:rh=0.0:bs=-0.0:bm=-0.0:bh=-0.0,eq=saturation=1.0[no_cap_v]")
    filter_parts.append("[no_cap_v]setpts=PTS-STARTPTS,trim=start=0:end=10.4,setpts=PTS-STARTPTS[trim_v]")
    filter_parts.append("[trim_v]tpad=stop_mode=clone:stop_duration=5.869999999999999[freeze_v]")
    
    cur_v = "freeze_v"
    for i in range(14):
        filter_parts.append(f"[{i+1}:v]format=rgba,setpts=PTS-STARTPTS[sub{i}]")
    times = [
        (0.0, 1.07), (1.07, 2.07), (2.07, 3.53), (3.53, 4.53), (4.53, 5.53), (5.53, 6.7),
        (6.7, 7.7), (7.7, 9.0), (9.0, 10.7), (10.7, 11.83), (11.83, 12.83), (12.83, 13.83),
        (13.83, 14.93), (14.93, 16.27)
    ]
    for i, (start, end) in enumerate(times):
        out_label = f"overlay{i}"
        if i == 13:
            filter_parts.append(f"[{cur_v}][sub{i}]overlay=enable='between(t,{start},{end - 0.005})',format=nv12[cap_v]")
        else:
            filter_parts.append(f"[{cur_v}][sub{i}]overlay=enable='between(t,{start},{end - 0.005})'[{out_label}]")
            cur_v = out_label
            
    # Audio filters
    filter_parts.append("[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a]")
    filter_parts.append("[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27[main_audio]")
    
    audio_configs = [
        {"start": 0.0, "end": 1.07, "offset": 0.0},
        {"start": 0.0, "end": 2.07, "offset": 1.07},
        {"start": 0.0, "end": 3.53, "offset": 2.07},
        {"start": 0.0, "end": 4.53, "offset": 3.53},
        {"start": 0.0, "end": 5.53, "offset": 4.53},
        {"start": 0.0, "end": 6.7, "offset": 5.53},
        {"start": 0.0, "end": 7.7, "offset": 6.7},
        {"start": 0.0, "end": 9.0, "offset": 7.7},
        {"start": 0.0, "end": 10.7, "offset": 9.0},
        {"start": 0.0, "end": 11.83, "offset": 10.7},
        {"start": 0.0, "end": 12.83, "offset": 11.83},
        {"start": 0.0, "end": 13.83, "offset": 12.83},
        {"start": 0.0, "end": 14.93, "offset": 13.83},
        {"start": 0.0, "end": 16.27, "offset": 14.93}
    ]
    mix_inputs = ["[main_audio]"]
    weights = ["1.0"]
    
    base_idx = 15
    for idx, cfg in enumerate(audio_configs):
        stream_idx = idx + base_idx
        local_delay_ms = cfg["offset"] * 1000
        filter_parts.append(
            f"[{stream_idx}:a]atrim=start={cfg['start']}:end={cfg['end']},"
            f"adelay={local_delay_ms}|{local_delay_ms},"
            f"aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm{idx}]"
        )
        mix_inputs.append(f"[bgm{idx}]")
        weights.append("1")
        
    mix_in_str = "".join(mix_inputs)
    weight_str = " ".join(weights)
    filter_parts.append(
        f"{mix_in_str}amix=inputs=15:duration=longest:weights='{weight_str}':normalize=0,asetpts=PTS-STARTPTS[merged]"
    )
    
    filter_complex = ";".join(filter_parts)
    
    cmd.extend([
        "-fps_mode", "cfr", "-r", "30",
        "-threads", "2", "-preset", "ultrafast",
        "-filter_complex", filter_complex,
        "-ar", "44100", "-ac", "2", "-video_track_timescale", "15360",
        "-avoid_negative_ts", "make_zero",
        "-map", "[cap_v]", "-map", "[merged]", "-shortest",
        "./work/mix_7176/manual_norm0_test.mp4"
    ])
    
    print("Running ffmpeg manually and capturing output...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    
    with open("scratch/ffmpeg_stderr.log", "w", encoding="utf-8") as f:
        f.write(res.stderr)
        
    print(f"Finished. Return code: {res.returncode}")
