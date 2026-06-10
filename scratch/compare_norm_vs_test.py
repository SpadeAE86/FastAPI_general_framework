import wave
import numpy as np

def read_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        return data, params.nchannels

if __name__ == "__main__":
    seg, c_seg = read_wav("./work/mix_7176/seg0.wav")
    test_wav, c_test = read_wav("./work/mix_7176/test_mix_15_norm0.wav")
    norm_wav, c_norm = read_wav("./work/mix_7176/norm0.wav")
    
    print(f"seg: channels={c_seg}, len={len(seg)}")
    print(f"test: channels={c_test}, len={len(test_wav)}")
    print(f"norm: channels={c_norm}, len={len(norm_wav)}")
    
    # Interleaved first 5s correlation
    length = min(len(seg), len(test_wav), len(norm_wav), int(5.0 * 44100 * 2))
    
    corr_test = np.corrcoef(seg[:length], test_wav[:length])[0, 1]
    corr_norm = np.corrcoef(seg[:length], norm_wav[:length])[0, 1]
    
    print(f"Correlation (interleaved) - Test mix vs Seg: {corr_test:.6f}")
    print(f"Correlation (interleaved) - Norm mix vs Seg: {corr_norm:.6f}")
    
    # Let's also check correlation of test_wav with norm_wav
    corr_between = np.corrcoef(test_wav[:length], norm_wav[:length])[0, 1]
    print(f"Correlation between Test mix and Norm mix: {corr_between:.6f}")
