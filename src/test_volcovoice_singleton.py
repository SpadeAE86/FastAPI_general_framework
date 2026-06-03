import argparse
import json
import sys

sys.path.append("c:\\Job\\AI\\mix\\AIGC_video_mix_remake\\src")

from models.pydantic_models.request.volcovoice_request import character_options
from utils.volcano_utils import volcano_singleton_timestamps_test


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a single Volcano TTS timestamps debug request.")
    parser.add_argument("--text", default="你好，这里是火山引擎单例测试。我们重点验证字级时间戳是否返回。")
    parser.add_argument("--speaker", default="Vivi", help="Display speaker name from character_options, or a raw speaker id.")
    parser.add_argument("--output", default="./final/volcovoice_singleton_debug.mp3")
    parser.add_argument("--model", default=None)
    parser.add_argument("--speech-rate", type=int, default=0)
    parser.add_argument("--loudness-rate", type=int, default=0)
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--format", default="mp3")
    parser.add_argument("--emotion", default=None)
    parser.add_argument("--emotion-scale", type=int, default=None)
    parser.add_argument("--disable-markdown-filter", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    speaker = args.speaker if args.speaker in character_options.values() else character_options.get(args.speaker, args.speaker)

    result = volcano_singleton_timestamps_test(
        text=args.text,
        speaker=speaker,
        output_path=args.output,
        model=args.model,
        speech_rate=args.speech_rate,
        loudness_rate=args.loudness_rate,
        sample_rate=args.sample_rate,
        audio_format=args.format,
        emotion=args.emotion,
        emotion_scale=args.emotion_scale,
        disable_markdown_filter=args.disable_markdown_filter,
    )

    print("=== Volcano singleton test summary ===")
    print(json.dumps(
        {
            "api_generation": result.api_generation,
            "timestamp_mode": result.timestamp_mode,
            "output_path": result.output_path,
            "audio_bytes": result.audio_bytes,
            "event_count": result.event_count,
            "usage": result.usage,
            "sentence_count": len(result.sentences),
        },
        ensure_ascii=False,
        indent=2,
    ))

    print("\n=== Sentence timestamps ===")
    for idx, sentence in enumerate(result.sentences):
        print(f"[{idx}] event={sentence.event} text={sentence.text}")
        for word in sentence.words:
            confidence = "" if word.confidence is None else f" confidence={word.confidence:.4f}"
            print(f"  - {word.word}: {word.start_time:.3f}s -> {word.end_time:.3f}s{confidence}")


if __name__ == "__main__":
    main()
