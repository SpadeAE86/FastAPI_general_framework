import subprocess
import os
import numpy as np
import wave

def get_rms(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        return np.sqrt(np.mean(data**2))

def run_mix_from_source(test_name, filter_complex):
    out_wav = f"./work/mix_7176/test_format_{test_name}.wav"
    if os.path.exists(out_wav):
        os.remove(out_wav)
    
    seg_mp4 = r"./work/mix_7176/segment_0_000.mp4"
    voice_path = r"cache/9b/ee/19be254a7b21608baa66975d55e9.wav"
    
    # Mix the AAC audio from segment_0_000.mp4 (input 0) and WAV audio (input 1)
    cmd = [
        "ffmpeg", "-y", "-i", seg_mp4, "-i", voice_path,
        "-filter_complex", filter_complex, "-map", "[merged]",
        "-acodec", "pcm_s16le", out_wav
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Test {test_name} failed: {res.stderr}")
    else:
        # Check if the output contains the mixed audio (by calculating correlation with original segment)
        # We can extract the original segment audio for comparison
        print(f"Test {test_name} mixed successfully. Output RMS: {get_rms(out_wav):.2f}")
        
        # Let's check correlation with original segment
        with wave.open("./work/mix_7176/seg_check.wav", "rb") as w:
            frames = w.readframes(w.getnframes())
            seg_data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)[:441000] # first 10s
        with wave.open(out_wav, "rb") as w:
            frames = w.readframes(w.getnframes())
            mix_data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)[:441000]
        
        length = min(len(seg_data), len(mix_data))
        corr = np.corrcoef(seg_data[:length], mix_data[:length])[0, 1]
        print(f"  -> Correlation with original segment: {corr:.6f}")

if __name__ == "__main__":
    # Test 1: Current filter (no sample_fmts in aformat)
    # We apply same filtering as normalize_video.py but with only 1 BGM input.
    # original audio stream is input 0:a, voiceover is input 1:a.
    f_current = (
        "[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];"
        "[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27[main_audio];"
        "[1:a]atrim=start=0.0:end=1.07,adelay=0|0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm0];"
        "[main_audio][bgm0]amix=inputs=2:duration=longest:weights='1.0 1':normalize=0,asetpts=PTS-STARTPTS[merged]"
    )
    run_mix_from_source("current", f_current)
    
    # Test 2: Updated filter specifying sample_fmts=fltp (planar float)
    f_fltp = (
        "[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];"
        "[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo:sample_fmts=fltp,apad=whole_dur=16.27[main_audio];"
        "[1:a]atrim=start=0.0:end=1.07,adelay=0|0,aformat=sample_rates=44100:channel_layouts=stereo:sample_fmts=fltp,apad=whole_dur=16.27,volume=2[bgm0];"
        "[main_audio][bgm0]amix=inputs=2:duration=longest:weights='1.0 1':normalize=0,asetpts=PTS-STARTPTS[merged]"
    )
    run_mix_from_source("fltp", f_fltp)
    
    # Test 3: Updated filter specifying sample_fmts=flt (packed float)
    f_flt = (
        "[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];"
        "[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo:sample_fmts=flt,apad=whole_dur=16.27[main_audio];"
        "[1:a]atrim=start=0.0:end=1.07,adelay=0|0,aformat=sample_rates=44100:channel_layouts=stereo:sample_fmts=flt,apad=whole_dur=16.27,volume=2[bgm0];"
        "[main_audio][bgm0]amix=inputs=2:duration=longest:weights='1.0 1':normalize=0,asetpts=PTS-STARTPTS[merged]"
    )
    run_mix_from_source("flt", f_flt)
