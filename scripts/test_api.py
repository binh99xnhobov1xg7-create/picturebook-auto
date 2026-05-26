"""单张图烟雾测试：验证 API Key + 模型 ID + 网络通畅。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import JIMENG_API_KEY, JIMENG_BASE_URL, JIMENG_MODEL, STYLE_DIR  # noqa: E402
from seedream_client import generate_image  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

print(f"key  : {JIMENG_API_KEY[:12]}…  (len={len(JIMENG_API_KEY)})")
print(f"base : {JIMENG_BASE_URL}")
print(f"model: {JIMENG_MODEL}")

dest = Path(__file__).resolve().parents[1] / "outputs" / "_smoke" / "test.png"
prompt = (
    "Warm watercolor children's book illustration, low saturation, soft wash, "
    "rounded lines, 4:3 horizontal. A friendly orange tabby cat sitting on a "
    "green grass meadow under blue sky. Reserve 10%-15% clean blank area at "
    "top-right for caption (no text in image)."
)
try:
    out = generate_image(prompt=prompt, dest=dest, mock=False, label="smoke")
    print(f"OK -> {out}  ({out.stat().st_size // 1024} KB)")
except Exception as e:
    print(f"FAIL: {e}")
    sys.exit(1)
