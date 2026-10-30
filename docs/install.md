# 部署教程（保姆级，含所有坑）

> 目标：Windows 10/11 + NVIDIA 8G显存，从零到桌宠跑起来。

## 1. 安装 Ollama

```powershell
winget install Ollama.Ollama
# 国内GitHub直连慢的话 winget 走微软CDN，速度通常没问题
```

## 2. 导入无审查模型

Ollama官方库没有abliterated模型，从 hf-mirror 下载 GGUF 后导入：

```powershell
# 下载 Qwen2.5-7B abliterated Q4_K_M (约4.4G)
curl -L -o qwen2.5-7b-abliterated.gguf "https://hf-mirror.com/RichardErkhov/huihui-ai_-_Qwen2.5-7B-Instruct-abliterated-v3-gguf/resolve/main/Qwen2.5-7B-Instruct-abliterated-v3.Q4_K_M.gguf"
```

Modelfile（**必须带TEMPLATE，否则对话不遵循指令**，这是我们踩过的最大的坑）：

```
FROM ./qwen2.5-7b-abliterated.gguf
TEMPLATE """<|im_start|>system
{{ .System }}<|im_end|>
<|im_start|>user
{{ .Prompt }}<|im_end|>
<|im_start|>assistant
"""
PARAMETER stop <|im_start|>
PARAMETER stop <|im_end|>
PARAMETER temperature 0.7
PARAMETER top_p 0.8
PARAMETER num_ctx 10000
```

```powershell
ollama create qwen2.5-abliterated -f Modelfile
```

⚠️ 不要用 Qwen3 系的 abliterated 版本做伴侣对话——Qwen3默认思考模式会输出无关推理内容，
即使 /no_think 也不稳定。Qwen2.5-7B-abliterated-v3 实测对话体验最好（8G显存 47 tok/s）。

## 3. 安装 LiveTalking

```powershell
git clone https://github.com/lipku/LiveTalking.git
cd LiveTalking
uv venv --python 3.12 .venv
# 50系显卡必须 cu128+ 的 PyTorch
uv pip install --python .venv/Scripts/python.exe torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
# 国内PyPI超时就用清华源
set UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
# 桌宠客户端依赖
uv pip install --python .venv/Scripts/python.exe PySide6 sounddevice
```

模型权重（wav2lip.pth / s3fd.pth）从 hf-mirror 下载，见本仓库 docs/model.md。

## 4. 启动

```powershell
# 终端1: LiveTalking
cd LiveTalking
set LLM_SYSTEM_PROMPT=你是用户的AI伴侣，性格温柔，说话简短口语化
.venv\Scripts\python.exe app.py --transport webrtc --model wav2lip --avatar_id wav2lip256_green --llm_provider ollama --tts edgetts

# 终端2: 桌宠
cd GlassMate
python client\desktop_pet.py
```

浏览器验证：http://127.0.0.1:8010 应能看到数字人视频流。

## 常见坑（全部实测踩过）

| 症状 | 原因 | 解决 |
|------|------|------|
| LLM回复答非所问/输出推理 | Modelfile没带TEMPLATE | 按上面完整Modelfile重建 |
| 人物边缘一圈绿 | 绿幕溢色 | 客户端已内置despill，调 --tolerance |
| 抠像有大片背景残留 | 素材是渐变背景非纯色 | 用 tools/make_greenscreen.py 重新合成纯绿幕 |
| cv2报错读不到图 | 路径含中文 | 素材放纯ASCII路径 |
| genavatar卡死 | 显存被LiveTalking/ComfyUI占满 | 先停服务再跑，8G显存三者互斥 |
| winget装Ollama报"stdin is not a tty" | git-bash下winget限制 | 用PowerShell或加 --disable-interactivity |
| GitHub直连超时 | 网络 | 给git/gh挂代理: set HTTPS_PROXY=http://127.0.0.1:7890 |
| bat文件中文乱码 | 编码 | bat存为UTF-8+CRLF，开头加 chcp 65001 |

## 5. 换装（可选，需要ComfyUI）

需要：ComfyUI + SDXL checkpoint（推荐Juggernaut-XL_v9）+ qwen_image_2.1（int8）
+ qwen3vl_8b text encoder + qwen_image_2.1 vae + birefnet.safetensors

```powershell
python tools\change_outfit.py "白色JK制服，黑色过膝袜" --name jk制服
python tools\apply_outfit.py jk制服
```

显存调度：换装生成时ComfyUI占~6G，与LiveTalking互斥。apply_outfit.py会自动停服务腾显存。
