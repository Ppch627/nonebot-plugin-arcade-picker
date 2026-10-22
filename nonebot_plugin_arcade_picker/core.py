"""核心业务逻辑：机厅筛选、币价解析、综合评分。

本模块不依赖 NoneBot，可单独用 Python 测试。
币价来源（优先级从高到低）：
  1. 评论中显式写出的“X元/币”等（来源=评论）；
  2. 团购套餐价表（美团/抖音，按店名子串匹配）；
  3. 连锁品牌价目表（来源=连锁价目表）；
  4. 全局默认价（来源=默认价）。
除团购价外，若评论中带“N折”会对基础价打折。
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

BASE_HOST = "nearcade.cn"

_COIN_RE = re.compile(r"(\d+)\s*币")
_DISCOUNT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*折")


def is_maimai(name: str) -> bool:
    """判断游戏名是否是舞萌（maimai）系列。"""
    n = (name or "").lower().replace(" ", "").replace("　", "")
    return "maimai" in n or "舞萌" in n


def _safe_int(v: Any) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        try:
            return int(float(v))
        except ValueError:
            return 0
    return 0


def parse_coins(cost: str) -> Optional[int]:
    """从“6币 / 18币”这类字符串中解析出单局投币数。"""
    m = _COIN_RE.search(cost or "")
    return int(m.group(1)) if m else None


def _explicit_coin_price(text: str) -> Optional[float]:
    """从评论文本中抽取“每枚币多少钱”的显式表达。

    支持：1元/币、1元一币、每币1元、1元/2币、2币/1元、美团80币39.9元 等。
    返回每枚币的价格（元）。
    """
    t = text or ""
    # 1元/币 或 1元一币
    m = re.search(r"(\d+(?:\.\d+)?)\s*元\s*(?:[/／]|一)\s*币", t)
    if m:
        return float(m.group(1))
    # 每币1元
    m = re.search(r"每\s*币\s*(\d+(?:\.\d+)?)\s*元", t)
    if m:
        return float(m.group(1))
    # 1元/2币 -> 每币 0.5 元
    m = re.search(r"(\d+(?:\.\d+)?)\s*元\s*[/／]\s*(\d+)\s*币", t)
    if m:
        n = float(m.group(2))
        return float(m.group(1)) / n if n else None
    # 80币39.9元 / 2币1元 -> 每币 39.9/80 元
    m = re.search(r"(\d+)\s*币\s*(?:[/／=＝])?\s*(\d+(?:\.\d+)?)\s*元", t)
    if m:
        n = float(m.group(1))
        return float(m.group(2)) / n if n else None
    return None


def _discount_from_comment(text: str) -> Optional[float]:
    """从“美团6折”这类表达中抽取折扣系数（0.6）。"""
    m = _DISCOUNT_RE.search(text or "")
    if not m:
        return None
    v = float(m.group(1))
    if 0 < v <= 10:
        return v / 10.0
    return None


def _deal_value(val: Any) -> Tuple[Optional[float], str]:
    """解析团购价表条目。

    val 可以是 float/数字（价格），或 dict{"price": ..., "source": "美团"/"抖音"}。
    返回 (价格, 来源标签)。
    """
    if isinstance(val, dict):
        try:
            price = float(val.get("price"))
        except (TypeError, ValueError):
            return None, "团购"
        source = str(val.get("source") or "团购")
        return price, source
    try:
        return float(val), "团购"
    except (TypeError, ValueError):
        return None, "团购"


def resolve_coin_price(
    shop: Dict[str, Any],
    game: Optional[Dict[str, Any]],
    default_price: float,
    chain_prices: Dict[str, float],
    deal_prices: Dict[str, Any],
    use_heuristics: bool = True,
) -> Tuple[float, str]:
    """确定某家机厅舞萌DX的单币价格（元）及来源标签。

    返回 (价格, 来源标签)。来源取值：评论 / 美团 / 抖音 / 团购 / 连锁价目表 / 默认价。
    """
    name = shop.get("name") or ""
    comment_parts = [shop.get("comment") or ""]
    if game:
        comment_parts.append(game.get("comment") or "")
    comment = " ".join(comment_parts).strip()

    base = float(default_price)
    source = "默认价"

    for key, price in chain_prices.items():
        if key and key in name:
            base = float(price)
            source = "连锁价目表"
            break

    for key, val in deal_prices.items():
        if key and key in name:
            deal_price, deal_source = _deal_value(val)
            if deal_price is not None and deal_price > 0:
                base = deal_price
                source = deal_source
            break

    if use_heuristics:
        explicit = _explicit_coin_price(comment)
        if explicit is not None and explicit > 0:
            return round(explicit, 4), "评论"

        discount = _discount_from_comment(comment)
        if discount is not None and source not in ("美团", "抖音", "团购"):
            base = base * discount

    return round(base, 4), source


def shop_web_url(shop: Dict[str, Any]) -> str:
    source = shop.get("source") or "bemanicn"
    sid = shop.get("id")
    if sid is None:
        return ""
    return f"https://{BASE_HOST}/shops/{source}/{sid}"


@dataclass
class Candidate:
    shop: Dict[str, Any] = field(repr=False)
    game: Dict[str, Any] = field(repr=False)
    name: str = ""
    address: str = ""
    distance_km: float = 0.0
    quantity: int = 0
    coins_per_play: Optional[int] = None
    coin_price: float = 1.0
    coin_price_source: str = "默认价"
    cost_per_play: Optional[float] = None
    is_open: bool = True
    attendance: int = 0
    lng: float = 0.0
    lat: float = 0.0
    metro: str = ""
    shop_url: str = ""
    score: float = 0.0
    order: int = 0


def build_candidates(shops: List[Dict[str, Any]], cfg) -> List[Candidate]:
    """把 Nearcade 返回的机厅列表转换为候选机厅（仅保留有舞萌DX的）。"""
    out: List[Candidate] = []
    for shop in shops:
        games = [g for g in (shop.get("games") or []) if is_maimai(g.get("name") or "")]
        if not games:
            continue
        # 一个店可能有多条舞萌记录，取数量最多的一条。
        game = max(games, key=lambda g: g.get("quantity") or 0)
        qty = int(game.get("quantity") or 0)
        coins = parse_coins(game.get("cost") or "")
        price, source = resolve_coin_price(
            shop,
            game,
            cfg.arcade_default_coin_price,
            cfg.chain_prices(),
            cfg.deal_prices(),
            cfg.arcade_use_coin_price_heuristics,
        )
        cost = round(coins * price, 2) if coins is not None else None

        loc = (shop.get("location") or {}).get("coordinates") or [0.0, 0.0]
        try:
            lng = float(loc[0])
            lat = float(loc[1])
        except (TypeError, ValueError, IndexError):
            lng, lat = 0.0, 0.0

        transit = shop.get("transit") or {}
        metro = transit.get("metro") or {}
        metro_name = metro.get("stationName") or metro.get("name") or ""

        out.append(
            Candidate(
                shop=shop,
                game=game,
                name=shop.get("name") or "未知机厅",
                address=(shop.get("address") or {}).get("detailed") or "地址未知",
                distance_km=float(shop.get("distance") or 0.0),
                quantity=qty,
                coins_per_play=coins,
                coin_price=price,
                coin_price_source=source,
                cost_per_play=cost,
                is_open=bool(shop.get("isOpen")),
                attendance=_safe_int(shop.get("totalAttendance")),
                lng=lng,
                lat=lat,
                metro=metro_name,
                shop_url=shop_web_url(shop),
            )
        )
    return out


def score_candidates(cands: List[Candidate], cfg) -> List[Candidate]:
    """计算并排序。

    综合评分 = 100 * (Wd*Sd + Wc*Sc + Wp*Sp) / (Wd+Wc+Wp)

    - Sd（距离，越大越好）= 1 / (1 + 距离 / 距离尺度)
    - Sc（机台数，越大越好）= min(台数, 饱和值) / 饱和值
    - Sp（价格，越便宜越好）= 1 / (1 + 单局成本 / 价格尺度)

    已打烊的机厅乘 0.5 的系数以示惩罚。
    """
    wd = float(cfg.arcade_weight_distance)
    wc = float(cfg.arcade_weight_count)
    wp = float(cfg.arcade_weight_price)
    total_w = wd + wc + wp
    if total_w <= 0:
        total_w = 1.0

    dist_scale = max(float(cfg.arcade_distance_scale_km), 0.001)
    count_sat = max(int(cfg.arcade_count_saturate), 1)
    price_scale = max(float(cfg.arcade_price_scale_yuan), 0.001)

    for c in cands:
        sd = 1.0 / (1.0 + c.distance_km / dist_scale)
        sc = min(c.quantity, count_sat) / float(count_sat)
        if c.cost_per_play is None:
            sp = 0.5  # 币数未知，取中性分
        else:
            sp = 1.0 / (1.0 + c.cost_per_play / price_scale)

        raw = 100.0 * (wd * sd + wc * sc + wp * sp) / total_w
        if not c.is_open:
            raw *= 0.5
        c.score = round(raw, 1)

    cands.sort(key=lambda c: (-c.score, c.distance_km))
    for i, c in enumerate(cands, 1):
        c.order = i
    return cands


def price_source_label(source: str) -> str:
    """把来源标签转成展示用文字。未知来源原样返回。"""
    return source
