import json
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.pydantic_models.request.mixed_video_request import MixedVideoRequest
from models.pydantic_models.response.frontend_timeline_response import SpritesData, SpriteSheet
from utils.frontend_exporter import build_frontend_timeline

def test_exporter():
    # Load request from example json
    with open('test/front_end_track_request_example.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    req = MixedVideoRequest(**data)
    
    # Mock sprites and fps
    num_clips = len(req.obs_video_path_list) if req.obs_video_path_list else 0
    fps_list = [req.fps] * num_clips
    
    sprites_list = []
    for i in range(num_clips):
        sprite = SpritesData(
            sheets=[
                SpriteSheet(
                    url=f"aigc/aigc_test/mock_sprite_{i}/sprite_1.webp",
                    cols=5,
                    rows=5,
                    frameCount=25,
                    startFrame=0
                )
            ],
            sampleInterval=1,
            totalSamples=25,
            frameWidth=100,
            frameHeight=100
        )
        sprites_list.append(sprite)
        
    timeline_res = build_frontend_timeline(req, fps_list=fps_list, sprites_list=sprites_list)
    
    # Serialize to dict directly to verify
    out_dict = timeline_res.model_dump(exclude_none=True)
    
    # Optional logic to write dict to output file
    # for easy examination by user
    out_path = 'test/front_end_track_response_mock.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out_dict, f, ensure_ascii=False, indent=2)
        
    print(f"Success! Mock response written to {out_path}")

if __name__ == '__main__':
    test_exporter()
