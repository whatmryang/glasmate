# 模型清单与下载

本仓库不分发任何模型权重，全部运行时自行下载。

## 必需

| 模型 | 用途 | 大小 | 下载 |
|------|------|------|------|
| Qwen2.5-7B-Instruct-abliterated-v3 (Q4_K_M) | 对话LLM | 4.4G | hf-mirror: `RichardErkhov/huihui-ai_-_Qwen2.5-7B-Instruct-abliterated-v3-gguf` |
| wav2lip256.pth | 口型驱动 | 205M | hf-mirror: `CherryOnes/LiveTalking` → wav2lip.pth |
| s3fd.pth | 人脸检测 | 86M | hf-mirror: `camenduru/Wav2Lip` → checkpoints/s3fd-619a316812.pth |

## 换装功能（可选）

| 模型 | 用途 | 下载 |
|------|------|------|
| SDXL checkpoint (推荐Juggernaut-XL_v9) | 基础形象生成 | civitai/hf-mirror |
| qwen_image_2.1_int8_convrot.safetensors | 指令式换装(ComfyUI UNETLoader) | hf-mirror |
| qwen3vl_8b_int8_convrot.safetensors | Qwen-Image-Edit文本编码器 | hf-mirror |
| qwen_image_2.1_vae_bf16.safetensors | VAE | hf-mirror |
| birefnet.safetensors | 抠像 | hf-mirror (ComfyUI background_removal目录) |

⚠️ Qwen-Image-Edit 的文本编码器必须是 Qwen3-VL-8B（hidden 4096），
用 qwen2.5-vl-7b（hidden 3584）会报 `normalized_shape=[4096]` 维度错误。

## 国内加速

```bash
# HuggingFace镜像
export HF_ENDPOINT=https://hf-mirror.com
# pip清华源
export UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple
```
