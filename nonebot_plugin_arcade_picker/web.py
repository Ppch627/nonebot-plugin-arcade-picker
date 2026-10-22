"""Web 路由：定位页、结果页、token 管理、QQ 结果推送。

页面路由直接挂载在 NoneBot2 的 FastAPI app 上。
"""
import html
import json
import secrets
import time
from typing import Any, Dict, List, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse
from nonebot import get_app, get_bot, logger
from nonebot.adapters.onebot.v11 import MessageSegment

from .config import plugin_config
from .core import Candidate, build_candidates, price_source_label, score_candidates
from . import data

app = get_app()

# token -> {"user_id": ..., "group_id": ..., "expires": ...}
_tokens: Dict[str, Dict[str, Any]] = {}


def new_token(user_id: Any, group_id: Optional[Any] = None) -> str:
    ttl = int(plugin_config.arcade_token_ttl_seconds)
    token = secrets.token_urlsafe(16)
    _tokens[token] = {
        "user_id": int(user_id),
        "group_id": int(group_id) if group_id is not None else None,
        "expires": time.time() + ttl,
    }
    return token


def _peek_token(token: str) -> Optional[Dict[str, Any]]:
    item = _tokens.get(token)
    if not item:
        return None
    if time.time() > item["expires"]:
        _tokens.pop(token, None)
        return None
    return item


def consume_token(token: str) -> Optional[Dict[str, Any]]:
    item = _peek_token(token)
    if item:
        _tokens.pop(token, None)
    return item


def _render_page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        "body{font-family:-apple-system,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;"
        "max-width:760px;margin:0 auto;padding:20px;color:#1f2933;background:#f5f7fa}"
        "h1{font-size:22px}h2{font-size:18px;margin:18px 0 8px}"
        ".card{background:#fff;border-radius:12px;padding:16px 18px;margin:10px 0;box-shadow:0 1px 3px rgba(0,0,0,.08)}"
        ".row{display:flex;flex-wrap:wrap;gap:6px 14px;margin:4px 0;font-size:14px;color:#52606d}"
        ".tag{background:#eef2f7;border-radius:6px;padding:2px 8px;font-size:12px;color:#52606d}"
        ".badge{font-weight:600}.open{color:#0b8f23}.closed{color:#c0392b}"
        ".score{font-size:26px;font-weight:700;color:#0b6bcb}"
        "a{color:#0b6bcb;text-decoration:none}button{background:#0b6bcb;color:#fff;border:0;"
        "border-radius:8px;padding:10px 18px;font-size:15px;cursor:pointer}"
        "input{border:1px solid #cbd2d9;border-radius:8px;padding:9px 10px;font-size:14px;margin:4px 0;width:200px}"
        ".muted{color:#7b8794;font-size:13px}.note{background:#fff8e1;border-radius:8px;padding:10px 12px;font-size:13px;color:#8a6d3b}"
        "</style></head><body>"
        f"<h1>{html.escape(title)}</h1>{body}</body></html>"
    )


def render_error(message: str) -> str:
    body = (
        f"<div class='card'><p>{html.escape(message)}</p></div>"
        "<p class='muted'>请回到 QQ 对话中重新发送“附近机厅”获取新链接。</p>"
    )
    return _render_page("定位查询", body)


# --------------------------------------------------------------------------
# 定位页
# --------------------------------------------------------------------------
def render_locate(token: str) -> str:
    token_js = json.dumps(token)
    body = (
        "<div class='note'>"
        "本页面会调用浏览器的 HTML5 定位来获取你的实时位置。<br>"
        "请确认使用的是 <b>HTTPS</b> 链接，并在浏览器/QQ 内置浏览器弹出的授权框中点击“允许”。"
        "</div>"
        "<div class='card'>"
        "<p id='status' class='muted'>正在获取你的位置…</p>"
        "<button onclick='locate()'>重新定位</button>"
        "</div>"
        "<div class='card' id='manual' style='display:none'>"
        "<h2>手动输入坐标</h2>"
        "<p class='muted'>自动定位失败时，可在手机地图 App 中查看当前坐标后填入。</p>"
        "<input id='lat' type='text' placeholder='纬度，如 31.2304'>"
        "<input id='lng' type='text' placeholder='经度，如 121.4737'><br>"
        "<button onclick='submitManual()'>按坐标查询</button>"
        "</div>"
        "<script>"
        f"var TOKEN={token_js};"
        "function post(lat,lng){"
        "fetch('/arcade/result',{method:'POST',headers:{'Content-Type':'application/json'},"
        "body:JSON.stringify({token:TOKEN,lat:lat,lng:lng})})"
        ".then(function(r){return r.text();})"
        ".then(function(t){document.open();document.write(t);document.close();})"
        ".catch(function(e){document.getElementById('status').innerText='请求失败：'+e;});}"
        "function showManual(){document.getElementById('manual').style.display='block';}"
        "function locate(){"
        "document.getElementById('status').innerText='正在获取你的位置…';"
        "if(!navigator.geolocation){document.getElementById('status').innerText='浏览器不支持定位，请手动输入坐标';showManual();return;}"
        "navigator.geolocation.getCurrentPosition("
        "function(p){post(p.coords.latitude,p.coords.longitude);},"
        "function(err){document.getElementById('status').innerText='自动定位失败：'+err.message+'，请手动输入坐标';showManual();},"
        "{enableHighAccuracy:true,timeout:15000,maximumAge:30000});}"
        "function submitManual(){"
        "var lat=parseFloat(document.getElementById('lat').value);"
        "var lng=parseFloat(document.getElementById('lng').value);"
        "if(isNaN(lat)||isNaN(lng)){alert('请输入有效的经纬度');return;}"
        "post(lat,lng);}"
        "locate();"
        "</script>"
    )
    return _render_page("📍 查询附近舞萌DX机厅", body)


# --------------------------------------------------------------------------
# 结果页
# --------------------------------------------------------------------------
def render_results(cands: List[Candidate], lat: float, lng: float) -> str:
    if not cands:
        return _render_page(
            "附近机厅结果",
            "<div class='card'>附近没有收录到舞萌DX机厅，试试扩大搜索范围或换一个位置。</div>",
        )

    wd = plugin_config.arcade_weight_distance
    wc = plugin_config.arcade_weight_count
    wp = plugin_config.arcade_weight_price
    parts: List[str] = []
    parts.append(
        "<div class='note'>"
        f"综合评分 = 100 × ({wd:.2f}×距离分 + {wc:.2f}×机台数分 + {wp:.2f}×价格分)，"
        "距离/价格越低、机台越多分越高，已打烊机厅折半。"
        "</div>"
    )
    medals = ["🥇", "🥈", "🥉"]
    for c in cands:
        if c.coins_per_play is not None and c.cost_per_play is not None:
            price_str = f"{c.coins_per_play}币 × {c.coin_price:.2f}元/币({price_source_label(c.coin_price_source)}) ≈ {c.cost_per_play:.2f}元/局"
        else:
            price_str = "币数未知"
        status = (
            "<span class='badge open'>🟢 营业中</span>"
            if c.is_open
            else "<span class='badge closed'>🔴 已打烊</span>"
        )
        medal = medals[c.order - 1] if c.order <= 3 else f"{c.order}."
        amap = f"https://uri.amap.com/marker?position={c.lng},{c.lat}&name={c.name}"
        rows = [
            f"<span class='tag'>距离 {c.distance_km:.2f} km</span>",
            f"<span class='tag'>舞萌DX {c.quantity} 台</span>",
            f"<span class='tag'>单局 {price_str}</span>",
            status,
        ]
        if c.metro:
            rows.append(f"<span class='tag'>最近地铁 {html.escape(c.metro)}</span>")
        if c.attendance:
            rows.append(f"<span class='tag'>上报人数 {c.attendance}</span>")
        link = f"<a href='{html.escape(c.shop_url)}' target='_blank'>机厅详情</a>" if c.shop_url else ""
        map_link = f"<a href='{html.escape(amap)}' target='_blank'>地图导航</a>"
        parts.append(
            "<div class='card'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center'>"
            f"<h2 style='margin:0'>{medal} {html.escape(c.name)}</h2>"
            f"<div class='score'>{c.score}</div>"
            "</div>"
            f"<div class='row'>{' '.join(rows)}</div>"
            f"<div class='row muted'>📍 {html.escape(c.address)}</div>"
            f"<div class='row'>{link}　{map_link}</div>"
            "</div>"
        )
    parts.append("<p class='muted'>完整推荐也已推送回 QQ 对话。</p>")
    return _render_page("🎮 附近舞萌DX机厅推荐", "".join(parts))


# --------------------------------------------------------------------------
# QQ 推送
# --------------------------------------------------------------------------
async def push_to_qq(item: Dict[str, Any], cands: List[Candidate]) -> None:
    try:
        bot = get_bot()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[arcade-picker] 未找到 Bot 实例，跳过 QQ 推送: {exc}")
        return

    if not cands:
        msg = "附近没有收录到舞萌DX机厅，试试换一个位置。"
    else:
        lines = ["🎮 附近舞萌DX机厅推荐（按综合评分排序）：", ""]
        for c in cands[:5]:
            if c.coins_per_play is not None and c.cost_per_play is not None:
                price_str = f"{c.coins_per_play}币 × {c.coin_price:.2f}元/币({price_source_label(c.coin_price_source)}) ≈ {c.cost_per_play:.2f}元"
            else:
                price_str = "币数未知"
            status = "🟢营业中" if c.is_open else "🔴已打烊"
            line = f"{c.order}. {c.name}  [{status}]\n"
            line += f"   距离 {c.distance_km:.2f}km｜舞萌DX {c.quantity}台｜{price_str}｜评分 {c.score}"
            if c.metro:
                line += f"｜最近地铁 {c.metro}"
            lines.append(line)
        lines.append("")
        lines.append("完整榜单与地图导航请查看网页。")
        msg = "\n".join(lines)

    try:
        if item.get("group_id"):
            await bot.send_group_msg(
                group_id=int(item["group_id"]), message=MessageSegment.text(msg)
            )
        else:
            await bot.send_private_msg(
                user_id=int(item["user_id"]), message=MessageSegment.text(msg)
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[arcade-picker] QQ 推送失败: {exc}")


# --------------------------------------------------------------------------
# 路由
# --------------------------------------------------------------------------
@app.get("/arcade/locate", response_class=HTMLResponse)
async def locate_page(token: str = "") -> HTMLResponse:
    if not token or not _peek_token(token):
        return HTMLResponse(render_error("链接无效或已过期"))
    return HTMLResponse(render_locate(token))


@app.post("/arcade/result", response_class=HTMLResponse)
async def result_page(request: Request) -> HTMLResponse:
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return HTMLResponse(render_error("请求格式错误"))

    token = str(body.get("token") or "")
    item = consume_token(token)
    if not item:
        return HTMLResponse(render_error("链接无效或已过期，请回到QQ重新发送“附近机厅”"))

    try:
        lat = float(body.get("lat"))
        lng = float(body.get("lng"))
    except (TypeError, ValueError):
        return HTMLResponse(render_error("经纬度格式错误"))

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return HTMLResponse(render_error("经纬度超出有效范围"))

    try:
        raw = await data.discover_nearby(lat, lng, plugin_config.arcade_search_radius_km)
        shops = raw.get("shops") or []
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[arcade-picker] Nearcade 查询失败: {exc}")
        return HTMLResponse(render_error("机厅数据查询失败，请稍后再试"))

    cands = build_candidates(shops, plugin_config)
    score_candidates(cands, plugin_config)
    cands = cands[: int(plugin_config.arcade_max_results)]

    await push_to_qq(item, cands)
    return HTMLResponse(render_results(cands, lat, lng))
