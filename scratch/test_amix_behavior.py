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

def run_mix(test_name, filter_complex):
    out_wav = f"./work/mix_7176/test_mix_{test_name}.wav"
    if os.path.exists(out_wav):
        os.remove(out_wav)
    
    # We will mix main_audio_only.wav (input 0) and seg_0_0_volcovoice_1781059901819.wav (input 1)
    # The voiceover is located at cache/... but we can find it from the previous command or just download/copy it.
    # Actually we already have the cache paths from the previous log tail:
    # C:\Job\AI\mix\AIGC_video_mix_remake\cache\9b\ee\19be254a7b21608baa66975d55e9.wav is seg_0_0.
    voice_path = r"cache/9b/ee/19be254a7b21608baa66975d55e9.wav"
    main_audio = r"work/mix_7176/main_audio_only.wav"
    
    cmd = [
        "ffmpeg", "-y", "-i", main_audio, "-i", voice_path,
        "-filter_complex", filter_complex, "-map", "[merged]",
        "-acodec", "pcm_s16le", out_wav
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Test {test_name} failed: {res.stderr}")
    else:
        print(f"Test {test_name} mixed successfully. Output RMS: {get_rms(out_wav):.2f}")

if __name__ == "__main__":
    # Test 1: amix with normalize=0, weights="1.0 1", duration=longest
    run_mix("norm0_weights", "[0:a][1:a]amix=inputs=2:duration=longest:weights='1.0 1':normalize=0[merged]")
    
    # Test 2: amix with normalize=1, weights="1.0 1", duration=longest
    run_mix("norm1_weights", "[0:a][1:a]amix=inputs=2:duration=longest:weights='1.0 1':normalize=1[merged]")
    
    # Test 3: amix with normalize=0, NO weights, duration=longest
    run_mix("norm0_no_weights", "[0:a][1:a]amix=inputs=2:duration=longest:normalize=0[merged]")
    
    # Test 4: amix with default (normalize=1, no weights)
    run_mix("default", "[0:a][1:a]amix=inputs=2:duration=longest[merged]")
