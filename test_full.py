"""无真实 QQ 账号的完整自测。

覆盖：
  1. 核心解析函数（test_core.py 已覆盖，这里快速复测）
  2. 定位页路由（有效/无效 token）
  3. 结果页路由（真实 Nearcade 数据）
  4. 指令处理（模拟一次 QQ 群消息，校验回复内容与链接）
  5. 美团/抖音辅助脚本的 URL 生成与套餐价解析
"""
import os

os.environ.setdefault("DRIVER", "~fastapi")
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "18080")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault(
    "ARCADE_DEAL_COIN_PRICES",
    '{"风云再起上海人民广场店": {"price": 0.5, "source": "美团"}}',
)

import asyncio
import importlib.util
from types import SimpleNamespace

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebot.exception import FinishedException

nonebot.init()
nonebot.get_driver().register_adapter(OneBotV11Adapter)

import nonebot_plugin_arcade_picker  # noqa: F401  导入即注册路由
from nonebot_plugin_arcade_picker import handle_nearby
from nonebot_plugin_arcade_picker.web import new_token, _peek_token, consume_token

import httpx
from nonebot import get_app

app = get_app()

PASS = []


def ok(name):
    PASS.append(name)
    print(f"  [PASS] {name}")


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send(self, event=None, message=None, **kwargs):
        self.sent.append(message)


async def test_web():
    print("\n== 1. Web 定位页 / 结果页 ==")
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/arcade/locate?token=bad")
        assert r.status_code == 200 and "无效或已过期" in r.text
        ok("无效 token 被正确拒绝")

        token = new_token(10001, 20002)
        assert _peek_token(token) is not None
        r = await c.get(f"/arcade/locate?token={token}")
        assert r.status_code == 200
        assert "navigator.geolocation" in r.text
        assert "HTTPS" in r.text
        ok("定位页正常渲染（含 HTML5 定位 JS 与 HTTPS 提示）")

        r = await c.post("/arcade/result", json={"token": token, "lat": 31.2304, "lng": 121.4737})
        assert r.status_code == 200
        assert "舞萌" in r.text and "风云再起" in r.text and "美团" in r.text
        ok("结果页正常渲染（真实数据，含美团币价来源）")

        # 恶意/越界输入（换一个新 token，因为 result 会消费 token）
        bad_token = new_token(10001, 20002)
        r = await c.post("/arcade/result", json={"token": bad_token, "lat": 999, "lng": 0})
        assert r.status_code == 200 and "超出有效范围" in r.text
        ok("越界经纬度被拒绝")

        # token 一次性消费（前面 result 已消费过旧 token）
        assert consume_token(token) is None
        ok("token 一次性消费生效")


async def test_command():
    print("\n== 2. 指令处理（模拟群消息） ==")
    from nonebot.internal.matcher import current_bot, current_event

    fake = FakeBot()
    ev = SimpleNamespace(user_id=10001, group_id=20002)

    tb = current_bot.set(fake)
    te = current_event.set(ev)
    try:
        try:
            await handle_nearby(fake, ev)
        except FinishedException:
            pass
    finally:
        current_bot.reset(tb)
        current_event.reset(te)

    assert len(fake.sent) == 1, f"期望回复 1 条，实际 {len(fake.sent)}"
    reply = fake.sent[0]
    assert "arcade/locate?token=" in reply
    assert "授权定位" in reply or "定位" in reply
    print("  回复内容：")
    print("  " + reply.replace("\n", "\n  "))
    ok("指令正确生成定位链接并回复")


def test_helper_script():
    print("\n== 3. 美团/抖音辅助脚本 ==")
    path = os.path.join(os.path.dirname(__file__), "scripts", "build_deal_prices.py")
    spec = importlib.util.spec_from_file_location("build_deal_prices", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    import urllib.parse

    u = mod.meituan_search_url("风云再起上海人民广场店")
    assert "meituan.com/s/" in u and "游戏币" in urllib.parse.unquote(u)
    ok(f"美团搜索链接生成: {u}")

    u = mod.douyin_search_url("风云再起上海人民广场店")
    assert "douyin.com/search/" in u and "游戏币" in urllib.parse.unquote(u)
    ok(f"抖音搜索链接生成: {u}")

    p, flag = mod.parse_price_input("39.9 80")
    assert abs(p - 0.49875) < 1e-6 and flag is None
    ok("套餐价解析 39.9 80 -> 0.49875 元/币")

    p, flag = mod.parse_price_input("=0.5")
    assert abs(p - 0.5) < 1e-6
    ok("直接单价解析 =0.5 -> 0.5 元/币")

    p, flag = mod.parse_price_input("s")
    assert p is None and flag == "skip"
    ok("跳过指令解析正常")


async def main():
    await test_web()
    await test_command()
    test_helper_script()
    print(f"\n全部通过：{len(PASS)} 项 ✅")


asyncio.run(main())
