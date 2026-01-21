from pydantic import Field

from models.pydantic_models.response.base_response import BaseResponse


#
class SpriteImageResponse(BaseResponse):
    sprite_image_url_list: str
    audio_url: str
    sprite_id: int = Field(
        default=123,
        description="雪碧图任务 ID"
    )