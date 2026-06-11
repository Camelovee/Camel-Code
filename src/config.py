import os

from dotenv import load_dotenv

# 加载项目根目录 .env
load_dotenv()

# ── 大模型配置 ─────────────────────────────────────────────
MODEL_PROVIDER   = os.getenv("MODEL_PROVIDER", "anthropic")
MODEL_ID         = os.getenv("MODEL_ID", "deepseek-v4-flash")
MODEL_BASE_URL   = os.getenv("MODEL_BASE_URL", "")
MODEL_API_KEY    = os.getenv("MODEL_API_KEY", "")
MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "8000"))
MODEL_TEMPERATURE = float(os.getenv("MODEL_TEMPERATURE", "0.1"))

