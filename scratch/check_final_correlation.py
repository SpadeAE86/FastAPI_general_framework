import os
import subprocess
import numpy as np
import wave

def extract_wav(mp4_path, wav_path):
    if os.path.exists(wav_path):
        os.remove(wav_path)
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", wav_path]
    subprocess.run(cmd, capture_output=True)

def read_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        return data, params.framerate

if __name__ == "__main__":
    final_mp4 = "./final/mix_7176/final-1781081787266.mp4"
    final_wav = "./final/mix_7176/final_test.wav"
    seg0_wav = "./work/mix_7176/seg0.wav"
    
    extract_wav(final_mp4, final_wav)
    
    data_norm, rate = read_wav(final_wav)
    data_seg, _ = read_wav(seg0_wav)
    
    # Segment 0 is 10.4s. Compare the first 10.4s
    length = min(len(data_norm), len(data_seg), int(10.4 * rate))
    sig_norm_L = data_norm[:length, 0]
    sig_seg_L = data_seg[:length, 0]
    
    corr_L = np.corrcoef(sig_norm_L, sig_seg_L)[0, 1]
    print(f"Final Video Correlation with seg0 (first 10.4s): {corr_L:.6f}")
    
    # Let's also check RMS
    rms = np.sqrt(np.mean(sig_norm_L**2))
    print(f"Final Video RMS (first 10.4s): {rms:.2f}")
