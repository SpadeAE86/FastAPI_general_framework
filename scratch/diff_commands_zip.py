import re

with open("C:/Users/25065/.gemini/antigravity/brain/799bb1fa-33d8-46cb-bf13-c14fc497c327/.system_generated/tasks/task-6128.log", "r", encoding="utf-8") as f:
    log_content = f.read()

match = re.search(r"full command: (ffmpeg .*?normalized_0.0_10.4_0_.*?\.mp4)", log_content)
service_cmd = match.group(1)

# Extract -filter_complex values
test_fc = (
    "[0:v]setpts=PTS-STARTPTS,trim=start=0.0:end=10.4,setpts=PTS-STARTPTS[v_pre];"
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
    "[main_audio][bgm0][bgm1][bgm2][bgm3][bgm4][bgm5][bgm6][bgm7][bgm8][bgm9][bgm10][bgm11][bgm12][bgm13]amix=inputs=15:duration=longest:weights='1.0 1 1 1 1 1 1 1 1 1 1 1 1 1 1':normalize=0,asetpts=PTS-STARTPTS[merged]"
)

# Extract -filter_complex from service_cmd
fc_match = re.search(r"-filter_complex\s+(.*?)\s+-ar", service_cmd)
service_fc = fc_match.group(1)

# Clean quotes
test_fc = test_fc.replace('"', '').replace("'", "")
service_fc = service_fc.replace('"', '').replace("'", "")

print("Test filter_complex length:", len(test_fc))
print("Service filter_complex length:", len(service_fc))

if test_fc == service_fc:
    print("Filter complexes are EXACTLY identical (ignoring quotes)!")
else:
    print("Filter complexes differ!")
    test_parts = test_fc.split(";")
    service_parts = service_fc.split(";")
    print("Test parts:", len(test_parts))
    print("Service parts:", len(service_parts))
    for idx in range(max(len(test_parts), len(service_parts))):
        t_p = test_parts[idx] if idx < len(test_parts) else "<none>"
        s_p = service_parts[idx] if idx < len(service_parts) else "<none>"
        if t_p != s_p:
            print(f"Difference at part {idx}:\n  Test:    {t_p}\n  Service: {s_p}")
            break
