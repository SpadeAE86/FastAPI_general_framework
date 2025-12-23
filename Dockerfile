# 使用自制的python3.12 包含ffmpeg rocketmq的基础镜像
FROM python312-ffmpeg:2.1

# 复制代码文件
COPY . /app
WORKDIR /app/src

#从requirements.txt里安装依赖
RUN pip install --timeout=600 \
    -r requirements.txt

# 暴露端口
EXPOSE 5000


# 启动命令
CMD ["uvicorn", "FastAPI_server:app", "--host", "0.0.0.0", "--port", "5000"]