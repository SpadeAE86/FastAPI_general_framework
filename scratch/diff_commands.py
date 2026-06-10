import sys

test_cmd = (
    "ffmpeg -y -ignore_editlist 1 -noautorotate -fflags +genpts -i ./work/mix_7176/segment_0_000.mp4 "
    "-loop 1 -i work/mix_7176/subtitle0.png -loop 1 -i work/mix_7176/subtitle1.png -loop 1 -i work/mix_7176/subtitle2.png "
    "-loop 1 -i work/mix_7176/subtitle3.png -loop 1 -i work/mix_7176/subtitle4.png -loop 1 -i work/mix_7176/subtitle5.png "
    "-loop 1 -i work/mix_7176/subtitle6.png -loop 1 -i work/mix_7176/subtitle7.png -loop 1 -i work/mix_7176/subtitle8.png "
    "-loop 1 -i work/mix_7176/subtitle9.png -loop 1 -i work/mix_7176/subtitle10.png -loop 1 -i work/mix_7176/subtitle11.png "
    "-loop 1 -i work/mix_7176/subtitle12.png -loop 1 -i work/mix_7176/subtitle13.png "
    "-i cache/9b/ee/19be254a7b21608baa66975d55e9.wav -i cache/46/17/78eee3daedcb41dd345f2c9033fb.wav "
    "-i cache/20/c9/0aedaab37e5cc9ff2b2c3ef3b180.wav -i cache/e1/c5/2e54a12f83b2c71ec0b7a890833f.wav "
    "-i cache/a7/27/e0e48021693287b43bcd8dfbbb49.wav -i cache/78/48/32c21260aa811b7884382215bbfb.wav "
    "-i cache/63/ce/914337f7ebfa3b541a6f4751c79a.wav -i cache/60/10/3b5cf849b354c82d2c9b0da18031.wav "
    "-i cache/7b/f0/ac247dc85cb3491a65f3bfd7ddc7.wav -i cache/e2/47/0631830f9665e7a070148e4f5bf0.wav "
    "-i cache/ec/c9/c31c9aba872a55d737814e8429da.wav -i cache/b1/5b/a5fcf7357c9ef1309e1b841ff6cc.wav "
    "-i cache/cc/db/d4cd88a06c00cd49100e45e72106.wav -i cache/04/d2/9484c68aeeef7ed74734b77fc226.wav "
    "-fps_mode cfr -r 30 -threads 2 -preset ultrafast -filter_complex "
    "\"[0:v]setpts=PTS-STARTPTS,trim=start=0.0:end=10.4,setpts=PTS-STARTPTS[v_pre];"
    "[v_pre]scale=1440:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1440:1080:(ow-iw)/2:(oh-ih)/2:black,colorbalance=rs=0.0:gs=-0.0:bs=0.0:rm=0.0:gm=-0.0:bm=0.0:rh=0.0:gh=-0.0:bh=0.0,colorbalance=rs=0.0:rm=0.0:rh=0.0:bs=-0.0:bm=-0.0:bh=-0.0,eq=saturation=1.0[no_cap_v];"
    "[no_cap_v]setpts=PTS-STARTPTS,trim=start=0:end=10.4,setpts=PTS-STARTPTS[trim_v];"
    "[trim_v]tpad=stop_mode=clone:stop_duration=5.869999999999999[freeze_v];"
    "[1:v]format=rgba,setpts=PTS-STARTPTS[sub0];[freeze_v][sub0]overlay=enable='between(t,0.0,1.0650000000000002)'[overlay0];"
    "[2:v]format=rgba,setpts=PTS-STARTPTS[sub1];[overlay0][sub1]overlay=enable='between(t,1.07,2.065)'[overlay1];"
    "[3:v]format=rgba,setpts=PTS-STARTPTS[sub2];[overlay1][sub2]overlay=enable='between(t,2.07,3.525)'[overlay2];"
    "[4:v]format=rgba,setpts=PTS-STARTPTS[sub3];[overlay2][sub3]overlay=enable='between(t,3.53,4.525)'[overlay3];"
    "[5:v]format=rgba,setpts=PTS-STARTPTS[sub4];[overlay3][sub4]overlay=enable='between(t,4.53,5.525)'[overlay4];"
    "[6:v]format=rgba,setpts=PTS-STARTPTS[sub5];[overlay4][sub5]overlay=enable='between(t,5.53,6.695)'[overlay5];"
    "[7:v]format=rgba,setpts=PTS-STARTPTS[sub6];[overlay5][sub6]overlay=enable='between(t,6.7,7.695)'[overlay6];"
    "[8:v]format=rgba,setpts=PTS-STARTPTS[sub7];[overlay6][sub7]overlay=enable='between(t,7.7,8.995)'[overlay7];"
    "[9:v]format=rgba,setpts=PTS-STARTPTS[sub8];[overlay7][sub8]overlay=enable='between(t,9.0,10.694999999999999)'[overlay8];"
    "[10:v]format=rgba,setpts=PTS-STARTPTS[sub9];[overlay8][sub9]overlay=enable='between(t,10.7,11.825)'[overlay9];"
    "[11:v]format=rgba,setpts=PTS-STARTPTS[sub10];[overlay9][sub10]overlay=enable='between(t,11.83,12.825)'[overlay10];"
    "[12:v]format=rgba,setpts=PTS-STARTPTS[sub11];[overlay10][sub11]overlay=enable='between(t,12.83,13.825)'[overlay11];"
    "[13:v]format=rgba,setpts=PTS-STARTPTS[sub12];[overlay11][sub12]overlay=enable='between(t,13.83,14.924999999999999)'[overlay12];"
    "[14:v]format=rgba,setpts=PTS-STARTPTS[sub13];[overlay12][sub13]overlay=enable='between(t,14.93,16.265)',format=nv12[cap_v];"
    "[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];"
    "[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27[main_audio];"
    "[15:a]atrim=start=0.0:end=1.07,adelay=0.0|0.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm0];"
    "[16:a]atrim=start=0.0:end=2.07,adelay=1070.0|1070.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm1];"
    "[17:a]atrim=start=0.0:end=3.53,adelay=2070.0|2070.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm2];"
    "[18:a]atrim=start=0.0:end=4.53,adelay=3530.0|3530.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm3];"
    "[19:a]atrim=start=0.0:end=5.53,adelay=4530.0|4530.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm4];"
    "[20:a]atrim=start=0.0:end=6.7,adelay=5530.0|5530.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm5];"
    "[21:a]atrim=start=0.0:end=7.7,adelay=6700.0|6700.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm6];"
    "[22:a]atrim=start=0.0:end=9.0,adelay=7700.0|7700.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm7];"
    "[23:a]atrim=start=0.0:end=10.7,adelay=9000.0|9000.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm8];"
    "[24:a]atrim=start=0.0:end=11.83,adelay=10700.0|10700.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm9];"
    "[25:a]atrim=start=0.0:end=12.83,adelay=11830.0|11830.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm10];"
    "[26:a]atrim=start=0.0:end=13.83,adelay=12830.0|12830.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm11];"
    "[27:a]atrim=start=0.0:end=14.93,adelay=13830.0|13830.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm12];"
    "[28:a]atrim=start=0.0:end=16.27,adelay=14930.0|14930.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm13];"
    "[main_audio][bgm0][bgm1][bgm2][bgm3][bgm4][bgm5][bgm6][bgm7][bgm8][bgm9][bgm10][bgm11][bgm12][bgm13]amix=inputs=15:duration=longest:weights='1.0 1 1 1 1 1 1 1 1 1 1 1 1 1 1':normalize=0,asetpts=PTS-STARTPTS[merged]\" "
    "-ar 44100 -ac 2 -video_track_timescale 15360 -y -avoid_negative_ts make_zero -map [cap_v] -map [merged] -shortest ./work/mix_7176/manual_norm0_test.mp4"
)

# Parse service command from task-6128.log
with open("C:/Users/25065/.gemini/antigravity/brain/799bb1fa-33d8-46cb-bf13-c14fc497c327/.system_generated/tasks/task-6128.log", "r", encoding="utf-8") as f:
    log_content = f.read()

import re
match = re.search(r"full command: (ffmpeg .*?normalized_0.0_10.4_0_.*?\.mp4)", log_content)
if not match:
    print("Could not find full command in log!")
    sys.exit(1)
    
service_cmd = match.group(1)

# Compare them by splitting on spaces (ignoring differences in paths, slashes, and quotes)
def clean_parts(cmd_str):
    parts = []
    # Replace backslashes with forward slashes for matching
    cmd_str = cmd_str.replace("\\", "/")
    # Remove quotes
    cmd_str = cmd_str.replace('"', '').replace("'", "")
    # Split
    for p in cmd_str.split(" "):
        p = p.strip()
        if p:
            # Normalize absolute paths to cache filenames
            if "/cache/" in p:
                p = "cache/" + p.split("/cache/")[-1]
            parts.append(p)
    return parts

test_parts = clean_parts(test_cmd)
service_parts = clean_parts(service_cmd)

print(f"Test parts count: {len(test_parts)}")
print(f"Service parts count: {len(service_parts)}")

diffs = []
for i in range(max(len(test_parts), len(service_parts))):
    p_test = test_parts[i] if i < len(test_parts) else "<none>"
    p_service = service_parts[i] if i < len(service_parts) else "<none>"
    if p_test != p_service:
        diffs.append((i, p_test, p_service))

print(f"Found {len(diffs)} differences:")
for idx, p_t, p_s in diffs[:20]:
    print(f"  Position {idx}:\n    Test:    {p_t}\n    Service: {p_s}")
