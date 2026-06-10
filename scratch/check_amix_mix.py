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
        # Reshape to 2 channels
        data = data.reshape(-1, params.nchannels)
        return data, params.framerate

if __name__ == "__main__":
    work_dir = "./work/mix_7176"
    norm_mp4 = os.path.join(work_dir, "normalized_0.0_10.4_0_706421858ca5c617f71080ad52db.mp4")
    seg_mp4 = os.path.join(work_dir, "segment_0_000.mp4")
    
    # Extract wavs
    norm_wav = "./work/mix_7176/norm_check.wav"
    seg_wav = "./work/mix_7176/seg_check.wav"
    extract_wav(norm_mp4, norm_wav)
    extract_wav(seg_mp4, seg_wav)
    
    data_norm, _ = read_wav(norm_wav)
    data_seg, _ = read_wav(seg_wav)
    
    # Let's check the volume of the original segment compared to the mixed normalized clip.
    # The segment length is 10.4s. The normalized clip is 16.27s.
    # Since from 10.4s onwards the original segment has ended, does the mixed file contain any audio from 10.4s to 16.27s?
    # Yes, it should contain only the voiceovers (and silence from main_audio).
    # What about 0s to 10.4s?
    # Let's inspect a slice where there is both original audio and voiceover.
    # We can check if the mixed signal matches the original segment's audio when voiceover is silent, or if the original segment is completely silent.
    # Wait, let's probe the original segment's RMS. It is 3074.70.
    # Let's find if the original audio stream in the ffmpeg command actually had any signal mapped.
    # Wait! In the ffmpeg command:
    # [0:a]atrim=start=0.0:end=10.4,asetpts=PTS-STARTPTS[trimmed_a];
    # [trimmed_a]volume=3,atrim=start=0:end=10.4,asetpts=PTS-STARTPTS,aformat=sample_rates=44100:channel_layouts=stereo,apad=whole_dur=16.27[main_audio];
    # Wait, in the segment_0_000.mp4 file, what stream is the audio?
    # Let's check with ffprobe on segment_0_000.mp4.
    # Index 0: Video, Index 1: Audio.
    # So the audio stream is indeed "0:a" or "0:a:0".
    # Wait! Let's print out the first 100 samples of both to see what they look like.
    print("First 20 samples of original segment:")
    print(data_seg[:20, 0])
    print("First 20 samples of normalized output:")
    print(data_norm[:20, 0])
