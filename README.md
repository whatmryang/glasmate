# GlassMate 玻璃伴侣

> 把想念的人，留在桌面上。

**一个有温度的本地AI伴侣** — 她可以是你喜欢的样子，也可以是你对某个人的思念。
透明桌宠 · 实时口型 · AI换装 · 全程离线，你的每一句话都只留在自己电脑里。

*A local-first desktop companion with a heart. She can be anyone you want —
a character, a companion, or a gentle way to keep someone you miss close by.*

![demo](docs/demo.gif)

---

## 为什么做这个项目

市面上的AI伴侣，要么是把你的每句话上传到别人服务器的云端产品，要么是冷冰冰的聊天框。
我做 GlassMate，是想让它**真正属于你**：形象、声音、性格、记忆，全部在你自己的电脑上生成和运行，
拔了网线她依然在，不订阅、不限量、不看任何人的脸色。

更重要的是——**它可以为你在乎的人定制。**

- 🧓 **给远方的亲人**：把爷爷奶奶的样子和口头禅做成桌宠，常伴屏幕一角，随时"说说话"
- 💑 **给爱人**：定制TA的形象和音色，异地时桌面上有个熟悉的陪伴
- 👶 **给孩子**：做一个会讲故事、会回答十万个为什么的卡通伙伴，安全、离线、无广告无诱导消费
- 🕯️ **给思念**：这是一个私人而温柔的用途——用照片和声音，让离开的人以另一种方式"在场"

技术上它不假装自己是真人，也不会替代真实的关系。但在那些想念的时刻，
一个会应你、记得你、随叫随到的身影，本身就是一种安慰。
**请带着善意和尊重使用它，尤其是涉及真实的人时——务必获得本人授权，逝者请征得家属同意。**

## 它能做什么

- 🧍 **真人风格数字人桌宠**：无边框透明窗口常驻桌面，不是二次元纸片人，是照片级真人形象（口型实时驱动）
- 👗 **一句话换装**：衣橱面板输入"白色JK制服"，AI本地生成新服装，点"换上"2-3分钟生效
- 🧠 **专属性格定制**：接Ollama本地大模型，性格、说话方式、和你的关系全由你定义；无云端审查过滤，人设不被平台对齐（请遵守当地法律，善用）
- 🗣️ **音色克隆**：Edge TTS开箱即用，升级GPT-SoVITS后，几秒音频就能复刻亲人的声音；说话可随时打断，像真人对话
- 💬 **思考云朵交互**：白色云朵输入气泡 + 回复字幕云朵，滚轮缩放，随手拖动
- 🔒 **全程离线**：对话、生图、语音全部本地推理，拔网线照样能聊

## 架构

```
你(文字/语音) → Ollama本地LLM(无审查) → Edge TTS → LiveTalking(wav2lip口型驱动)
                                                        ↓ WebRTC
换装管线: SDXL生图 → birefnet抠像 → 绿幕合成 → genavatar → 桌宠透明渲染(PySide6+OpenCV抠绿)
```

| 组件 | 作用 | 上游 |
|------|------|------|
| client/desktop_pet.py | 透明桌宠客户端(抠像/缩放/衣橱UI/自动重连) | 本项目原创 |
| tools/change_outfit.py | AI换装(Qwen-Image-Edit指令式重绘) | 本项目原创 |
| tools/apply_outfit.py | 一键换装(重建avatar+重启服务+自动重连) | 本项目原创 |
| tools/gen_green_img.py | 绿幕全身形象生成(SDXL) | 本项目原创 |
| tools/make_greenscreen.py | birefnet抠像→纯绿幕合成 | 本项目原创 |
| [LiveTalking](https://github.com/lipku/LiveTalking) | 实时数字人引擎(wav2lip) | MIT |
| [Ollama](https://ollama.com) | 本地LLM推理 | MIT |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | 生图后端 | GPL-3.0 |

## 硬件要求

- NVIDIA显卡 ≥8G显存（RTX 3060/4060/5060级别实测可跑）
- 32G内存更稳，硬盘预留30G
- Windows 10/11（Linux理论可跑，未验证）

## 快速开始

```bash
# 1. 安装LiveTalking(参考其官方文档) + Ollama
# 2. 拉取去审查中文模型
ollama create qwen2.5-abliterated -f Modelfile   # 见 docs/model.md

# 3. 克隆本仓库, 装客户端依赖
pip install PySide6 opencv-python aiortc aiohttp numpy sounddevice

# 4. 配置(环境变量或改 tools/gm_config.py)
#    GLASSMATE_HOME=LiveTalking路径

# 5. 启动服务+桌宠
python tools/apply_outfit.py  # 首次会构建默认avatar
python client/desktop_pet.py
```

详细部署教程（含所有坑）：[docs/install.md](docs/install.md)

## 换装玩法

```bash
# 生成新服装(需要ComfyUI+SDXL+Qwen-Image-Edit模型)
python tools/change_outfit.py "白色JK制服，黑色过膝袜" --name jk制服

# 一键换上(重建avatar+自动重启服务)
python tools/apply_outfit.py jk制服
```

或直接在桌宠窗口点 👗 打开衣橱，图形界面操作。

## 社区 / Community

遇到问题、想交流玩法、或需要 **一键整合包 / 远程部署 / 定制专属形象** 服务，欢迎加作者微信（备注 `GlassMate`）：

<p align="center">
  <img src="docs/wechat.jpg" width="240" alt="WeChat QR"/>
</p>

- 🐛 部署踩坑、Bug 反馈 → 提 [Issue](../../issues) 或加微信
- 💬 玩家交流群 / 形象素材分享 → 加微信拉你进群
- 🛠️ 付费服务：整合包（免配置解压即用）、远程部署、定制形象+音色克隆 → 微信详聊

> Star ⭐ 这个项目是对作者最大的支持！

**English**: Need a ready-to-run bundle, remote deployment, or a custom avatar/voice? Add the author on WeChat (QR above) with the note `GlassMate`. Bug reports are best filed as [Issues](../../issues).

## 免责声明

本项目仅供学习交流。使用者须遵守当地法律法规：
- 禁止生成、传播违法违规内容
- 禁止未经授权使用他人肖像/声音（定制形象仅限本人授权素材）
- 模型权重请遵守各自开源协议，本仓库不分发任何模型文件

## License

MIT © 2026 GlassMate contributors
上游组件遵循各自协议（LiveTalking MIT / ComfyUI GPL-3.0 / 各模型见其许可证）

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=whatmryang/glassmate-ai&type=Date)](https://star-history.com/#whatmryang/glassmate-ai&Date)
