"""插件配置。

所有配置项均为可选，未配置时使用默认值。
NoneBot2 会从 .env / .env.prod 读取这些变量（环境变量名大小写不敏感）。
"""
import json
from pathlib import Path
from typing import Dict
from pydantic import BaseModel


class Config(BaseModel):
    # 对外可达的站点根地址（必须为浏览器可访问的地址，建议 HTTPS，
    # 否则浏览器 HTML5 定位可能被禁用，只能走手动输入坐标）。
    arcade_public_base_url: str = ""

    # 搜索半径（公里）。
    arcade_search_radius_km: float = 10.0

    # 最多展示 / 推送多少家机厅。
    arcade_max_results: int = 10

    # 默认每枚币价格（元）。
    arcade_default_coin_price: float = 1.0

    # 连锁品牌价目表，JSON 字符串，例如：
    #   {"风云再起": 1.0, "城市英雄": 0.75, "汤姆熊": 1.2}
    # 匹配规则：机厅名称包含该关键字即命中（按顺序取第一个命中）。
    arcade_chain_coin_prices: str = ""

    # 团购平台（美团 / 抖音）套餐价表。支持两种写法：
    # 1) 内联 JSON：
    #      ARCADE_DEAL_COIN_PRICES = {"风云再起上海人民广场店": 0.5,
    #                                  "城市英雄XX店": {"price": 0.6, "source": "抖音"}}
    # 2) JSON 文件（推荐，方便增量维护）：
    #      ARCADE_DEAL_COIN_PRICES_FILE = /path/to/deal_coin_prices.json
    # 文件与内联 JSON 会合并，内联优先。
    # 匹配规则：机厅名称包含该关键字即命中（按顺序取第一个命中）。
    # 建议用 scripts/build_deal_prices.py 从美团/抖音生成该 JSON。
    arcade_deal_coin_prices: str = ""
    arcade_deal_coin_prices_file: str = ""

    # 是否从机厅/游戏评论中正则抽取“每币价格 / 折扣”信息。
    arcade_use_coin_price_heuristics: bool = True

    # 综合评分权重（会自动归一化，因此相对大小才是关键）。
    arcade_weight_distance: float = 0.4
    arcade_weight_count: float = 0.3
    arcade_weight_price: float = 0.3

    # 距离衰减尺度（公里）。距离为 0 时该项得满分 1；
    # 距离等于该值时得分降为 0.5。
    arcade_distance_scale_km: float = 3.0

    # 机台数“饱和”阈值：达到该数量即得满分的机台数维度。
    arcade_count_saturate: int = 4

    # 单局成本衰减尺度（元）。成本为 0 时得满分；
    # 成本等于该值时得 0.5 分。
    arcade_price_scale_yuan: float = 6.0

    # 定位链接 token 的有效期（秒）。
    arcade_token_ttl_seconds: int = 600

    def _parse_json_map(self, raw: str) -> Dict:
        raw = (raw or "").strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def chain_prices(self) -> Dict[str, float]:
        """连锁品牌价目表（内联 JSON），值均为 float 价格。"""
        return {
            str(k): float(v)
            for k, v in self._parse_json_map(self.arcade_chain_coin_prices).items()
            if not isinstance(v, (dict, list))
        }

    def deal_prices(self) -> Dict:
        """团购（美团/抖音）套餐价表：先读文件，再用内联 JSON 覆盖。

        值可以是 float（价格）或 dict{"price": float, "source": "美团"/"抖音"}。
        """
        result: Dict = {}
        path = (self.arcade_deal_coin_prices_file or "").strip()
        if path:
            p = Path(path)
            if p.exists():
                try:
                    result.update(self._parse_json_map(p.read_text(encoding="utf-8")))
                except Exception:
                    pass
        result.update(self._parse_json_map(self.arcade_deal_coin_prices))
        return result


from nonebot import get_plugin_config

# 插件全局配置实例。
plugin_config = get_plugin_config(Config)
