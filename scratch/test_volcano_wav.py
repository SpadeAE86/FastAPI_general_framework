import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.volcano_utils import volcano_generate_voice
from config.config import my_config

async def main():
    print("Testing Volcano TTS with encoding='wav'...")
    output_path = "scratch/test_volcano_wav.wav"
    try:
        # We need to temporarily patch/modify volcano_generate_voice encoding to 'wav' 
        # or we can inspect if it supports it by manually building a modified request
        # Let's import the function and see
        print("Starting voice generation...")
        res = await volcano_generate_voice(
            voice_type="ICL_zh_female_qiuling_v1_tob", # standard voice type
            text="现在点小黄车就能拍",
            filename=output_path,
        )
        print(f"Success! Result: {res}")
    except Exception as e:
        print(f"Failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
