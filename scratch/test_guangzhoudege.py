import sys
import os
import asyncio

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from utils.volcano_utils import volcano_generate_voice

async def main():
    print("Testing 广州德哥 ...")
    try:
        result = await volcano_generate_voice(
            voice_type="zh_male_guangzhoudege_emo_mars_bigtts",
            text="我就是普通的上班族",
            filename="./scratch/test_guangzhoudege.wav",
        )
        print("✅ 成功生成!")
        print(f"File: {result.output_path}")
    except Exception as e:
        print(f"❌ 生成失败: {e}")

if __name__ == "__main__":
    asyncio.run(main())
