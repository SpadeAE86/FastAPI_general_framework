import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.pydantic_models.request.frontend_timeline_request import (
    FrontendAudioInfo,
    FrontendTimelineRequest,
    FrontendVideoInfo,
)
from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import SpritesData, SpriteSheet
from utils.frontend_exporter import build_frontend_timeline

def test_exporter():
    # Load request from the new frontend example json
    with open('test/front_end_track_request_example_v2.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    timeline_request = FrontendTimelineRequest(**data)

    timeline_res = build_frontend_timeline(
        timeline_request.mix_request,
        video_info_list=timeline_request.video_info_list,
        audio_info_list=timeline_request.audio_info_list,
    )
    
    # Serialize to dict directly to verify
    out_dict = timeline_res.model_dump(exclude_none=True)
    
    # Optional logic to write dict to output file
    # for easy examination by user
    out_path = 'test/front_end_track_response_example.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out_dict, f, ensure_ascii=False, indent=2)
        
    print(f"Success! Mock response written to {out_path}")

if __name__ == '__main__':
    test_exporter()
