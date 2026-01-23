from typing import List

from pydantic import Field

from models.pydantic_models.response.base_response import BaseResponse


#
class SpriteImageResponse(BaseResponse):
    sprite_image_url_list: List[str] = Field(...,
                                description="雪碧图url列表"
                                )
    audio_url: str = Field(...,
                        description="音频url"
                        )
    video_resolution_x: int = Field(...,
                        description="视频宽度"
                        )
    video_resolution_y: int = Field(...,
                    description="视频高度"
                    )
    sprite_id: int = Field(
        default=123,
        description="雪碧图任务 ID"
    )