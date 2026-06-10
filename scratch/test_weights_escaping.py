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

def run_mix_test(test_name, weights_val):
    out_wav = f"./work/mix_7176/test_weights_{test_name}.wav"
    if os.path.exists(out_wav):
        os.remove(out_wav)
    
    seg_mp4 = r"./work/mix_7176/segment_0_000.mp4"
    voice_path = r"cache/9b/ee/19be254a7b21608baa66975d55e9.wav"
    
    # Filter complex
    filter_complex = (
        f"[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];"
        f"[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27[main_audio];"
        f"[1:a]atrim=start=0.0:end=1.07,adelay=0.0|0.0,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27,volume=2[bgm0];"
        f"[main_audio][bgm0]amix=inputs=2:duration=longest:weights={weights_val}:normalize=0,asetpts=PTS-STARTPTS[merged]"
    )
    
    cmd = [
        "ffmpeg", "-y", "-i", seg_mp4, "-i", voice_path,
        "-filter_complex", filter_complex, "-map", "[merged]",
        "-acodec", "pcm_s16le", out_wav
    ]
    
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Test {test_name} failed: {res.stderr}")
        return None
        
    rms = get_rms(out_wav)
    
    # Calculate correlation with original segment
    with wave.open("./work/mix_7176/seg_check.wav", "rb") as w:
        frames = w.readframes(w.getnframes())
        seg_data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)[:441000]
    with wave.open(out_wav, "rb") as w:
        frames = w.readframes(w.getnframes())
        mix_data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)[:441000]
    
    length = min(len(seg_data), len(mix_data))
    corr = np.corrcoef(seg_data[:length], mix_data[:length])[0, 1]
    print(f"Test {test_name} (weights={weights_val}): RMS={rms:.2f}, Correlation={corr:.6f}")

if __name__ == "__main__":
    # Test 1: double quotes
    run_mix_test("double_quotes", '"1.0 1"')
    
    # Test 2: single quotes
    run_mix_test("single_quotes", "'1.0 1'")
    
    # Test 3: no quotes
    run_mix_test("no_quotes", "1.0 1")
