# AI 音乐分析助手

🎵 上传音频文件或直接录音，AI 实时分析音乐风格、调性、BPM、和弦走向，并生成简谱/五线谱。

## 功能

- **音频上传** — 支持 WAV / MP3 / FLAC / M4A / OGG / AAC / WMA / AIFF
- **开始录音** — 浏览器内直接录制，最长 5 分钟
- **风格识别** — 13 种音乐风格分类（Pop / Rock / Jazz / Classical 等）
- **调性检测** — 识别主调与调式（大调/小调）
- **BPM 检测** — 混合算法自动检测速度
- **和弦分析** — 163 种和弦模板匹配
- **歌词匹配** — 粘贴歌词自动对齐旋律，标注最高/最低音
- **乐谱生成** — 简谱/五线谱双模式，支持导出 TXT

## 快速开始

### 方式一：pip 安装（推荐）

`ash
# 克隆仓库
git clone https://github.com/sunanqi94/ai-music-analysis.git
cd ai-music-analysis

# 安装依赖
pip install flask numpy scipy soundfile

# 启动服务
python backend/server.py

# 打开浏览器访问
# → http://127.0.0.1:5002
`

### 方式二：ffmpeg 支持（可选）

如需 MP3/M4A/AAC 支持，将 fmpeg.exe 放入 ackend/ffmpeg/ 目录：
- 下载地址：https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
- 解压后从 in/ffmpeg.exe 复制到 ackend/ffmpeg/ffmpeg.exe

### 方式三：一键启动（Windows）

双击运行 一键启动.bat（需要先安装 Python 依赖）。

## 文件结构

`
ai-music-analysis/
├── backend/
│   ├── server.py          # Flask 后端服务
│   ├── analyzer.py        # 音频分析引擎
│   └── ffmpeg/            # ffmpeg（可选，需自行下载）
├── backend_demo.html      # 主界面（服务端渲染）
├── demo.html              # 独立演示页面（直接打开可用）
├── requirements.txt       # Python 依赖
└── README.md
`

## 技术栈

- **后端**: Python + Flask
- **音频处理**: librosa · numpy · scipy · soundfile
- **前端**: 原生 HTML/CSS/JS（单页面应用）
- **可选**: ffmpeg（用于 MP3/M4A/AAC 解码）

## License

MIT
