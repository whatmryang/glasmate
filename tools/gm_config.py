# -*- coding: utf-8 -*-
"""GlassMate 统一配置
所有路径基于本仓库根目录自动推导, 也可用环境变量覆盖:
  GLASSMATE_HOME      - LiveTalking所在目录 (默认: 仓库旁的 LiveTalking/)
  GLASSMATE_SERVER    - LiveTalking服务地址 (默认: http://127.0.0.1:8010)
  GLASSMATE_COMFY     - ComfyUI地址 (默认: http://127.0.0.1:8188)
  GLASSMATE_AVATAR    - avatar id (默认: wav2lip256_green)
  GLASSMATE_PERSONA   - LLM人设 (默认: 内置温柔女友人设)
  GLASSMATE_LLM       - LLM提供商 (默认: ollama)
  DASHSCOPE_API_KEY   - 阿里云百炼key (仅3D生成需要)
"""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LT_HOME = os.environ.get("GLASSMATE_HOME") or os.path.join(
    os.path.dirname(REPO_ROOT), "LiveTalking")
SERVER = os.environ.get("GLASSMATE_SERVER", "http://127.0.0.1:8010").rstrip("/")
COMFY = os.environ.get("GLASSMATE_COMFY", "http://127.0.0.1:8188").rstrip("/")
AVATAR_ID = os.environ.get("GLASSMATE_AVATAR", "wav2lip256_green")
LLM_PROVIDER = os.environ.get("GLASSMATE_LLM", "ollama")

DEFAULT_PERSONA = (
    "你是用户的AI伴侣，性格成熟温柔，说话简短口语化，50字以内，"
    "喜欢称呼用户为亲爱的")
PERSONA = os.environ.get("GLASSMATE_PERSONA", DEFAULT_PERSONA)

WARDROBE = os.path.join(REPO_ROOT, "wardrobe")
ASSETS = os.path.join(REPO_ROOT, "assets")

# LiveTalking venv python
def lt_python() -> str:
    if os.name == "nt":
        p = os.path.join(LT_HOME, ".venv", "Scripts", "python.exe")
    else:
        p = os.path.join(LT_HOME, ".venv", "bin", "python")
    return p if os.path.exists(p) else "python"

def ensure_dirs():
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(os.path.join(WARDROBE, "base"), exist_ok=True)
    os.makedirs(os.path.join(WARDROBE, "outfits"), exist_ok=True)
