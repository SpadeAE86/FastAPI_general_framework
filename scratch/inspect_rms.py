import os
import subprocess
import numpy as np

def extract_wav(mp4_path, wav_path):
    if os.path.exists(wav_path):
        os.remove(wav_path)
    cmd = ["ffmpeg", "-y", "-i", mp4_path, "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", wav_path]
    subprocess.run(cmd, capture_output=True)

def analyze_wav(wav_path):
    import wave
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16)
        # Reshape to 2 channels
        data = data.reshape(-1, params.nchannels)
        rms_L = np.sqrt(np.mean(data[:, 0].astype(np.float64)**2))
        rms_R = np.sqrt(np.mean(data[:, 1].astype(np.float64)**2))
        max_val = np.max(np.abs(data))
        print(f"File: {os.path.basename(wav_path)}")
        print(f"Channels: {params.nchannels}, Frames: {params.nframes}, Sample Rate: {params.framerate}")
        print(f"RMS: Left={rms_L:.2f}, Right={rms_R:.2f}, Max Amplitude={max_val}")
        return data

if __name__ == "__main__":
    work_dir = "./work/mix_7176"
    seg0_mp4 = os.path.join(work_dir, "segment_0_000.mp4")
    norm0_mp4 = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    
    seg0_wav = "./work/mix_7176/seg0.wav"
    norm0_wav = "./work/mix_7176/norm0.wav"
    
    extract_wav(seg0_mp4, seg0_wav)
    extract_wav(norm0_mp4, norm0_wav)
    
    data_seg = analyze_wav(seg0_wav)
    data_norm = analyze_wav(norm0_wav)
    
    # Check if the original audio is completely zero or if it correlates with the segment.
    # The first segment is 10.4s. The normalized clip is 16.27s (padded with silence).
    # Let's check the RMS of the original audio from segment vs the normalized output in the last 4 seconds (where some voiceovers might be silent? Wait, voiceovers are active up to 16.27s. But the original audio is trimmed to 10.4s, so from 10.4s to 16.27s, the original audio part in normalized is padded with silence!)
    # Let's print the RMS of the first 2 seconds of both.
    rate = 44100
    print("\n--- Slice Analysis (0.0s to 2.0s) ---")
    seg_slice = data_seg[:2 * rate]
    norm_slice = data_norm[:2 * rate]
    print(f"Original Segment 0-2s RMS: {np.sqrt(np.mean(seg_slice.astype(np.float64)**2)):.2f}")
    print(f"Normalized Output 0-2s RMS: {np.sqrt(np.mean(norm_slice.astype(np.float64)**2)):.2f}")
