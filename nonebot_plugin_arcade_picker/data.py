"""Nearcade 数据访问层。"""
from typing import Any, Dict, List
import httpx

BASE_HOST = "nearcade.cn"
USER_AGENT = "Mozilla/5.0 (compatible; ArcadePickerBot/1.0)"


async def discover_nearby(lat: float, lng: float, radius_km: float) -> Dict[str, Any]:
    """调用 Nearcade 发现接口，按经纬度返回附近机厅。

    返回结构示例：
    {"shops": [{...}], "location": {...}, "radius": 10, ...}
    """
    params = {
        "latitude": str(lat),
        "longitude": str(lng),
        "radius": str(radius_km),
    }
    url = f"https://{BASE_HOST}/api/discover"
    async with httpx.AsyncClient(
        timeout=20.0, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def search_shops(keyword: str, page: int = 1, limit: int = 5) -> Dict[str, Any]:
    """按关键词搜索机厅（备用 / 扩展功能）。"""
    params = {"q": keyword, "page": str(page), "limit": str(limit)}
    url = f"https://{BASE_HOST}/api/shops"
    async with httpx.AsyncClient(
        timeout=20.0, headers={"User-Agent": USER_AGENT}
    ) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
