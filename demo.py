"""本地演示服务器：无需 QQ / 无需公网 HTTPS，在浏览器里跑通完整流程。

运行（在项目根目录）：
    .venv\\Scripts\\python.exe demo.py
    或
    python demo.py

启动后会打印一个链接，用浏览器打开并允许定位，即可看到推荐结果页。
（http://127.0.0.1 属于安全上下文，浏览器允许 HTML5 定位。）
"""
import os
import sys

# 保证中文在 Windows 控制台正常显示
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

os.environ.setdefault("DRIVER", "~fastapi")
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "18080")
os.environ.setdefault("LOG_LEVEL", "INFO")
# 本地演示用一条美团价表，方便你看到“币价来源”标注
os.environ.setdefault(
    "ARCADE_DEAL_COIN_PRICES",
    '{"风云再起上海人民广场店": {"price": 0.5, "source": "美团"}}',
)

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()
nonebot.get_driver().register_adapter(OneBotV11Adapter)

import nonebot_plugin_arcade_picker  # noqa: F401  导入即注册路由
from nonebot_plugin_arcade_picker.web import new_token

browser_token = new_token(10001, None)
curl_token = new_token(10002, None)

print("=" * 64)
print("本地演示服务已启动，无需 QQ。")
print()
print("方式一（推荐，体验完整流程）：用浏览器打开下面链接并允许定位")
print(f"  http://127.0.0.1:18080/arcade/locate?token={browser_token}")
print()
print("方式二（用固定坐标直接测结果接口）：另开一个终端执行")
print(
    '  curl.exe -X POST "http://127.0.0.1:18080/arcade/result" '
    '-H "Content-Type: application/json" '
    f'-d "{{\\"token\\": \\"{curl_token}\\", \\"lat\\": 31.2304, \\"lng\\": 121.4737}}"'
)
print()
print("按 Ctrl+C 停止服务。")
print("=" * 64)

nonebot.run()
