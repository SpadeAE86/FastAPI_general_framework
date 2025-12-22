# 使用官方 Python 3.12 基础镜像
FROM python:3.12

# 删除所有默认源，强制使用阿里云
RUN rm -f /etc/apt/sources.list /etc/apt/sources.list.d/* && \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware" > /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian/ bookworm-updates main non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.aliyun.com/debian-security/ bookworm-security main non-free non-free-firmware" >> /etc/apt/sources.list \

# 安装基础工具
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    bzip2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
#RUN wget https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz -O ffmpeg.tar.xz && \
# 替代apt安装FFmpeg的步骤
# 下载并安装 FFmpeg

# 将本地的 ffmpeg 和 ffprobe 复制到 /usr/local/bin/
COPY ffmpeg /usr/local/bin/
COPY ffprobe /usr/local/bin/

RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# 复制你本地的 NotoColorEmoji 字体到容器字体目录
COPY asset/fonts/NotoColorEmoji-Regular.ttf /usr/share/fonts/truetype/noto/NotoColorEmoji-Regular.ttf

# 刷新字体缓存
RUN fc-cache -fv

# 设置清华 pip 镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 复制代码文件
COPY . /app
WORKDIR /app/src

# 安装依赖（使用conda-forge的ffmpeg）
RUN pip install --timeout=600 \
        fastapi==0.115.13 \
        uvicorn==0.34.3 \
        ffmpeg-python==0.2.0 \
        setuptools==80.9.0\
        aliyun-python-sdk-core>=2.15.1 \
        oss2 \
        aiofiles\
        esdk-obs-python>=3.25.3 \
        pydub \
        streamlit \
        pyyaml \
        redis \
        httpx \
        tabulate \
        imageio \
        emoji \
        Pillow \
        huaweicloudsdkmetastudio \
        alibabacloud_avatar20220130==2.5.3 \
        volcengine \
        websockets \
        tortoise-orm \
        aiomysql \
        openai





# 暴露端口
EXPOSE 5000


# 启动命令
CMD ["uvicorn", "FastAPI_server:app", "--host", "0.0.0.0", "--port", "5000"]