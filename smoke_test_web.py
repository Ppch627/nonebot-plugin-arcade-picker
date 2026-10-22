import os
os.environ.setdefault("DRIVER", "~fastapi")
os.environ.setdefault("HOST", "127.0.0.1")
os.environ.setdefault("PORT", "18080")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("ARCADE_DEAL_COIN_PRICES", '{"风云再起上海人民广场店": {"price": 0.5, "source": "美团"}}')

import asyncio

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

import nonebot_plugin_arcade_picker  # noqa: F401  导入即注册路由
from nonebot_plugin_arcade_picker.web import new_token, _peek_token, consume_token

import httpx
from nonebot import get_app

app = get_app()


async def main():
    token = new_token(123456789, 987654321)
    assert _peek_token(token) is not None, "token 创建失败"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        r0 = await c.get("/arcade/locate?token=bad")
        assert r0.status_code == 200 and "无效或已过期" in r0.text, "无效 token 处理失败"

        r1 = await c.get(f"/arcade/locate?token={token}")
        assert r1.status_code == 200, "定位页状态码异常"
        assert "navigator.geolocation" in r1.text, "定位页缺少定位 JS"
        print(f"[OK] 定位页渲染成功，长度 {len(r1.text)}")

        r2 = await c.post("/arcade/result", json={"token": token, "lat": 31.2304, "lng": 121.4737})
        assert r2.status_code == 200, f"结果页状态码异常: {r2.status_code}"
        assert "舞萌" in r2.text, "结果页缺少舞萌信息"
        print(f"[OK] 结果页渲染成功，长度 {len(r2.text)}")
        print("     结果页含“风云再起”:", "风云再起" in r2.text)
        print("     结果页含“美团”:", "美团" in r2.text)

        assert consume_token(token) is None, "token 应已被消费"

    print("\nSMOKE TEST PASSED")


asyncio.run(main())
