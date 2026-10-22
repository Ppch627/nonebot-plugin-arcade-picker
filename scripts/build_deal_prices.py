"""从美团 / 抖音团购套餐价中，半自动生成“单币价格”表。

美团、抖音的团购页有较强的反爬与登录限制，全自动抓取不可靠，
因此本脚本采用“半自动”方式：
  1. 依次在默认浏览器中打开 美团 / 抖音 的搜索页（关键词 = 机厅名 + 游戏币）；
  2. 你人工查看套餐后，输入 “总价 币数”（如 `39.9 80`，表示 80 个币卖 39.9 元），
     或直接输入单币价（如 `=0.5`），或输入 `s` 跳过；
  3. 脚本计算单币价并写入 JSON（供插件 ARCADE_DEAL_COIN_PRICES_FILE 读取）。

用法：
  python scripts/build_deal_prices.py --shop "风云再起上海人民广场店" "城市英雄XX店"
  python scripts/build_deal_prices.py --list shops.txt
  python scripts/build_deal_prices.py --nearby 31.2304 121.4737 --radius 10
  python scripts/build_deal_prices.py --shop "某店" --platform douyin
  python scripts/build_deal_prices.py --shop "某店" --out deal_coin_prices.json
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

MEITUAN_SEARCH = "https://www.meituan.com/s/{q}"
DOUYIN_SEARCH = "https://www.douyin.com/search/{q}?type=general"


def _load_core():
    """绕过 nonebot 依赖，直接以文件方式加载 core 模块。"""
    path = os.path.join(REPO_ROOT, "nonebot_plugin_arcade_picker", "core.py")
    spec = importlib.util.spec_from_file_location("arcade_core", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def meituan_search_url(shop_name: str) -> str:
    q = urllib.parse.quote(f"{shop_name} 游戏币")
    return MEITUAN_SEARCH.format(q=q)


def douyin_search_url(shop_name: str) -> str:
    q = urllib.parse.quote(f"{shop_name} 游戏币")
    return DOUYIN_SEARCH.format(q=q)


def parse_price_input(text: str):
    """解析人工输入，返回 (单币价, None) 或 (None, 说明)。

    支持：
      - `39.9 80`   -> 0.49875（总价 39.9 元 / 80 币）
      - `=0.5`      -> 0.5（直接单币价）
      - `s`/`skip`  -> (None, "skip")
    """
    t = (text or "").strip()
    if not t:
        return None, "empty"
    if t.lower() in ("s", "skip"):
        return None, "skip"
    if t.startswith("="):
        try:
            return float(t[1:]), None
        except ValueError:
            return None, "invalid"
    m = re.match(r"^(\d+(?:\.\d+)?)\s+(\d+)$", t)
    if m:
        total = float(m.group(1))
        coins = int(m.group(2))
        if coins <= 0 or total <= 0:
            return None, "invalid"
        return round(total / coins, 6), None
    return None, "invalid"


def _nearby_shop_names(lat: float, lng: float, radius: float):
    core = _load_core()
    import urllib.request

    url = (
        "https://nearcade.cn/api/discover?"
        + urllib.parse.urlencode(
            {"latitude": str(lat), "longitude": str(lng), "radius": str(radius)}
        )
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; ArcadeDealBuilder/1.0)"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    names = []
    for shop in data.get("shops") or []:
        games = [g for g in (shop.get("games") or []) if core.is_maimai(g.get("name") or "")]
        if games:
            names.append(shop.get("name") or "")
    return names


def main(argv=None):
    ap = argparse.ArgumentParser(description="从美团/抖音半自动生成单币价格表")
    ap.add_argument("--shop", nargs="*", help="机厅名列表")
    ap.add_argument("--list", help="每行一个机厅名的文本文件")
    ap.add_argument("--nearby", nargs=2, type=float, metavar=("LAT", "LNG"), help="按经纬度从 Nearcade 拉取附近机厅")
    ap.add_argument("--radius", type=float, default=10.0, help="--nearby 的搜索半径(km)")
    ap.add_argument("--platform", choices=["all", "meituan", "douyin"], default="all")
    ap.add_argument("--out", default="deal_coin_prices.json", help="输出 JSON 路径")
    ap.add_argument("--no-open", action="store_true", help="只生成搜索链接，不自动打开浏览器")
    args = ap.parse_args(argv)

    names = list(args.shop or [])
    if args.list:
        with open(args.list, encoding="utf-8") as f:
            names += [ln.strip() for ln in f if ln.strip()]
    if args.nearby:
        names += _nearby_shop_names(args.nearby[0], args.nearby[1], args.radius)

    if not names:
        ap.error("请提供 --shop / --list / --nearby 中的至少一种")

    out_path = os.path.abspath(args.out)
    data = {}
    if os.path.exists(out_path):
        try:
            data = json.loads(open(out_path, encoding="utf-8").read())
        except Exception:
            data = {}

    platforms = ["meituan", "douyin"] if args.platform == "all" else [args.platform]
    print("=" * 60)
    print("在浏览器中查看套餐后，输入：")
    print("  39.9 80  -> 表示 80 个币卖 39.9 元（自动算单币价）")
    print("  =0.5     -> 直接指定单币价 0.5 元")
    print("  s / 回车 -> 跳过")
    print("=" * 60)

    for name in names:
        for plat in platforms:
            url = meituan_search_url(name) if plat == "meituan" else douyin_search_url(name)
            label = "美团" if plat == "meituan" else "抖音"
            print(f"\n[{label}] {name}")
            print(f"  搜索页: {url}")
            if not args.no_open:
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            try:
                raw = input(f"  {label}套餐（总价 币数 / =单价 / s 跳过）: ")
            except EOFError:
                raw = "s"
            price, flag = parse_price_input(raw)
            if price is not None:
                data[name] = {"price": price, "source": label}
                print(f"  ✅ 已记录：{price} 元/币（来源：{label}）")
            elif flag == "skip":
                print("  ⏭️  已跳过")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n已写入 {len(data)} 条记录 -> {out_path}")
    print("在 NoneBot 的 .env 中配置：")
    print(f'  ARCADE_DEAL_COIN_PRICES_FILE={out_path}')


if __name__ == "__main__":
    main()
