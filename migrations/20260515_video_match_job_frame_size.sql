-- 视频匹配任务：画面比例约束（与 OpenSearch car_interior_analysis_v2.frame_size 对齐）
ALTER TABLE video_match_job
  ADD COLUMN frame_size VARCHAR(32) NULL COMMENT '横版16:9 / 竖版9:16，转写后写入分镜 tags_json'
  AFTER car_model;
