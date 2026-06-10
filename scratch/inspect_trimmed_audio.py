import os
import subprocess
import numpy as np
import wave

def analyze_wav(wav_path):
    with wave.open(wav_path, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        data = np.frombuffer(frames, dtype=np.int16).astype(np.float64)
        data = data.reshape(-1, params.nchannels)
        rms = np.sqrt(np.mean(data**2))
        max_val = np.max(np.abs(data))
        print(f"File: {os.path.basename(wav_path)}")
        print(f"RMS: {rms:.2f}, Max Amplitude: {max_val}")
        return data

if __name__ == "__main__":
    work_dir = "./work/mix_7176"
    seg_mp4 = os.path.join(work_dir, "segment_0_000.mp4")
    out_wav = "./work/mix_7176/main_audio_only.wav"
    
    # Extract [main_audio]
    filter_str = "[0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];[trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27[main_audio]"
    cmd = [
        "ffmpeg", "-y", "-i", seg_mp4, "-filter_complex", filter_str, "-map", "[main_audio]", "-acodec", "pcm_s16le", out_wav
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("FFmpeg failed to extract main_audio_only:", res.stderr)
    else:
        analyze_wav(out_wav)
