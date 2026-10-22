"""不依赖 NoneBot 的核心逻辑验证脚本。

用法：python -X utf8 test_core.py
会用上海人民广场坐标拉取真实 Nearcade 数据，跑通筛选 + 评分。
"""
import importlib.util
import json
import os
import sys
import urllib.parse
import urllib.request
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(HERE, "nonebot_plugin_arcade_picker", "core.py")


def load_core():
    spec = importlib.util.spec_from_file_location("arcade_core", CORE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


core = load_core()

# ---- 单元级自检 ----
assert core.parse_coins("6币") == 6
assert core.parse_coins("18币") == 18
assert core.is_maimai("maimai DX") and core.is_maimai("舞萌DX")
assert not core.is_maimai("CHUNITHM")
assert abs(core._explicit_coin_price("美团80币39.9元") - 39.9 / 80) < 1e-6
assert abs(core._explicit_coin_price("1元/2币") - 0.5) < 1e-6
assert abs(core._explicit_coin_price("每币1元") - 1.0) < 1e-6
assert abs(core._discount_from_comment("美团6折") - 0.6) < 1e-6
print("[1/3] 基础解析函数自检通过")


# ---- 币价来源优先级自检 ----
def _shop(name, comment=""):
    return {"name": name, "comment": comment}


game = {"name": "maimai DX", "comment": ""}
chain = {"风云再起": 1.0}
deals = {
    "风云再起上海人民广场店": {"price": 0.5, "source": "美团"},
    "汤姆熊": {"price": 0.8, "source": "抖音"},
}
p, s = core.resolve_coin_price(_shop("风云再起上海人民广场店"), game, 1.0, chain, deals, True)
assert abs(p - 0.5) < 1e-6 and s == "美团", (p, s)
p, s = core.resolve_coin_price(_shop("汤姆熊欢乐世界"), game, 1.0, chain, deals, True)
assert abs(p - 0.8) < 1e-6 and s == "抖音", (p, s)
p, s = core.resolve_coin_price(_shop("风云再起徐家汇店"), game, 1.0, chain, deals, True)
assert abs(p - 1.0) < 1e-6 and s == "连锁价目表", (p, s)
p, s = core.resolve_coin_price(_shop("风云再起徐家汇店", "美团常驻6折"), game, 1.0, chain, deals, True)
assert abs(p - 0.6) < 1e-6 and s == "连锁价目表", (p, s)
p, s = core.resolve_coin_price(_shop("某店", "1元一币"), game, 1.0, {}, {}, True)
assert abs(p - 1.0) < 1e-6 and s == "评论", (p, s)
print("[2/3] 币价来源优先级自检通过")


# ---- 真实数据跑通 ----
class FakeCfg:
    arcade_default_coin_price = 1.0
    arcade_use_coin_price_heuristics = True
    arcade_weight_distance = 0.4
    arcade_weight_count = 0.3
    arcade_weight_price = 0.3
    arcade_distance_scale_km = 3.0
    arcade_count_saturate = 4
    arcade_price_scale_yuan = 6.0
    arcade_search_radius_km = 10.0
    arcade_max_results = 10

    @staticmethod
    def chain_prices():
        return {"风云再起": 1.0}

    @staticmethod
    def deal_prices():
        return {
            "风云再起上海人民广场店": {"price": 0.5, "source": "美团"},
        }


def main():
    cfg = FakeCfg()
    url = (
        "https://nearcade.cn/api/discover?"
        + urllib.parse.urlencode(
            {"latitude": "31.2304", "longitude": "121.4737", "radius": "10"}
        )
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ArcadeTest/1.0)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = json.loads(resp.read().decode("utf-8"))

    shops = raw.get("shops") or []
    print(f"Nearcade 返回机厅总数: {len(shops)}")

    cands = core.build_candidates(shops, cfg)
    core.score_candidates(cands, cfg)
    cands = cands[: cfg.arcade_max_results]

    print(f"其中含舞萌DX的机厅: {len(core.build_candidates(shops, cfg))} 家")
    print("\nTop {} 推荐（按综合评分）：".format(len(cands)))
    print(f"{'排名':<3}{'评分':<6}{'距离km':<8}{'台数':<5}{'币数':<5}{'单币价':<8}{'单局成本':<9}{'来源':<8}机厅名")
    for c in cands:
        coins = c.coins_per_play if c.coins_per_play is not None else "-"
        cost = f"{c.cost_per_play:.2f}" if c.cost_per_play is not None else "-"
        flag = "🟢" if c.is_open else "🔴"
        print(
            f"{c.order:<4}{c.score:<7}{c.distance_km:<9.2f}{c.quantity:<6}{str(coins):<6}"
            f"{c.coin_price:<9.3f}{cost:<10}{c.coin_price_source:<8}{flag}{c.name}"
        )
    print("\n[3/3] 真实数据跑通")


if __name__ == "__main__":
    main()
