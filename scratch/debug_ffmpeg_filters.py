import subprocess
import os
import numpy as np
import wave

def get_rms_and_correlation(wav_path, seg_wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        sig_norm = data[:, 0]
        
    with wave.open(seg_wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data_seg = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data_seg = data_seg.reshape(-1, params.nchannels)
        sig_seg = data_seg[:, 0]
        
    length = min(len(sig_norm), len(sig_seg), int(10.4 * 44100))
    corr = np.corrcoef(sig_norm[:length], sig_seg[:length])[0, 1]
    rms = np.sqrt(np.mean(sig_norm[:length]**2))
    return rms, corr

def run_cmd(name, filter_complex, extra_inputs=None):
    out_wav = f"./work/mix_7176/debug_{name}.wav"
    if os.path.exists(out_wav):
        os.remove(out_wav)
    
    cmd = ["ffmpeg", "-y", "-ignore_editlist", "1", "-i", "./work/mix_7176/segment_0_000.mp4"]
    if extra_inputs:
        for inp in extra_inputs:
            cmd.extend(["-i", inp])
            
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-acodec", "pcm_s16le", out_wav
    ])
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Filter {name} failed: {res.stderr}")
    else:
        rms, corr = get_rms_and_correlation(out_wav, "./work/mix_7176/seg0.wav")
        print(f"Filter {name} succeeded. RMS: {rms:.2f}, Correlation: {corr:.6f}")

if __name__ == "__main__":
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
    
    # Let's run a test mixing [main_audio] with 14 voiceovers directly to WAV
    # Inputs:
    # 0: segment_0_000.mp4
    # 1 to 14: the 14 voiceovers
    filter_parts = []
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
    for idx, cfg in enumerate(audio_configs):
        stream_idx = idx + 1
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
        f"{mix_in_str}amix=inputs=15:duration=longest:weights='{weight_str}':normalize=0,asetpts=PTS-STARTPTS[out]"
    )
    
    filter_complex = ";".join(filter_parts)
    run_cmd("amix_15_direct", filter_complex, extra_inputs=cache_files)
