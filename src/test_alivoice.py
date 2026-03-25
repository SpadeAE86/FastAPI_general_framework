import sys
import asyncio

# 添加路径
sys.path.append('c:\\Job\\AI\\mix\\AIGC_video_mix_remake\\src')

from service.alivoice_service import process_alivoice_task
from models.pydantic_models.request.alivoice_request import Alivoice_VO

async def test_run():
    config = Alivoice_VO(
        biz_id=8888,
        txt_str=["你好啊，这是一个测试语音", "这里是第二句话，来测试一下拼接"],
        voice_character="female", 
        audio_speed_level=500,
        volume=50
    )

    try:
        print(f"Submitting request to process_alivoice_task... Data: \n{config.model_dump_json(indent=2)}")
        result = await process_alivoice_task(config)
        print("Success! Result:")
        print(result.model_dump_json(indent=2))
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_run())
