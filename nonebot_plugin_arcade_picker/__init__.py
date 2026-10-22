"""附近机厅推荐插件入口。

指令：
  - 附近机厅 / 查机厅 / 附近舞萌 / 机厅推荐 / 找机厅
回复一条带 token 的定位网页链接，用户授权定位后，
插件按距离、舞萌DX机台数、单局价格综合评分推荐机厅，
并把榜单推送回 QQ 对话。
"""
from nonebot import on_command, logger
from nonebot.adapters.onebot.v11 import Bot, MessageEvent

from .config import plugin_config
from . import web  # noqa: F401  导入即注册 FastAPI 路由
from .web import new_token


nearby = on_command(
    "附近机厅",
    aliases={"查机厅", "附近舞萌", "机厅推荐", "找机厅"},
    priority=10,
    block=True,
)


@nearby.handle()
async def handle_nearby(bot: Bot, event: MessageEvent):
    user_id = event.user_id
    group_id = getattr(event, "group_id", None)

    token = new_token(user_id, group_id)

    base = (plugin_config.arcade_public_base_url or "").strip().rstrip("/")
    if not base:
        # 未配置公网地址时的兜底；此时浏览器定位通常不可用（非 HTTPS），
        # 页面会提供手动输入坐标的降级方案。
        base = "http://127.0.0.1:8080"
        logger.warning(
            "[arcade-picker] 未配置 ARCADE_PUBLIC_BASE_URL，使用兜底地址 "
            f"{base}。浏览器定位需要 HTTPS 公网地址。"
        )

    url = f"{base}/arcade/locate?token={token}"
    msg = (
        "请点击下面的链接授权定位，我会根据你的实时位置，"
        "综合“距离 / 舞萌DX机台数 / 单局价格”为你推荐附近最值得去的机厅：\n"
        f"{url}\n\n"
        "提示：请用手机打开，并在浏览器 / QQ 内置浏览器中允许定位。"
    )
    await nearby.finish(msg)
