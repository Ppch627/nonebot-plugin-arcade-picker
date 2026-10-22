# nonebot-plugin-arcade-picker

一个 NoneBot2 插件：当用户发送“查询附近机厅”的指令时，机器人回复一个**定位网页**，
网页通过 HTML5 定位拿到用户的实时位置，再据此查询附近的**舞萌DX**机厅，
并综合 **距离 / 舞萌DX机台数 / 单局价格** 计算出一家“最适合前往”的机厅推送给用户。

数据与思路参考了以下开源项目（感谢）：

- [YuuzukiRin/nonebot_plugin_mai_arcade](https://github.com/YuuzukiRin/nonebot_plugin_mai_arcade) —— 机厅人数/附近机厅查找，Nearcade API 用法
- [Yuri-YuzuChaN/nonebot-plugin-maimaidx](https://github.com/Yuri-YuzuChaN/nonebot-plugin-maimaidx) —— 舞萌DX 的 NoneBot2 插件
- [Diving-Fish/mai-bot](https://github.com/Diving-Fish/mai-bot) —— 最早的 mai bot 开源项目
- 机厅数据：[Nearcade](https://nearcade.cn)（`/api/discover`、`/api/shops`）

---

## 功能流程

```
用户发指令“附近机厅”
   └─> Bot 回复一条带 token 的链接: https://<你的域名>/arcade/locate?token=xxx
         └─> 用户用手机打开，HTML5 定位获取 lat/lng（非 HTTPS 时降级为手动输入坐标）
               └─> 页面 POST /arcade/result
                     └─> 调用 Nearcade 拉取附近机厅
                           └─> 筛选含“舞萌DX”的机厅
                                 └─> 计算综合评分并排序
                                       ├─> 网页展示排行榜 + 地图导航链接
                                       └─> 把 Top5 推送回 QQ 对话
```

## 综合评分公式（可调）

```
综合评分 = 100 × (Wd·Sd + Wc·Sc + Wp·Sp) / (Wd + Wc + Wp)

Sd 距离分  = 1 / (1 + 距离km / 距离尺度)            # 越近越高
Sc 机台数分 = min(舞萌DX台数, 饱和值) / 饱和值        # 越多越高
Sp 价格分  = 1 / (1 + 单局成本元 / 价格尺度)          # 越便宜越高

单局成本 = 单局投币数 × 每枚币价格
已打烊的机厅 综合评分 × 0.5
```

权重 `Wd/Wc/Wp` 默认 `0.4 / 0.3 / 0.3`（会自动归一化，改相对大小即可），
全部可在 `.env` 中配置。

## 币价从哪来

“每枚币价格”在机厅数据库里通常没有标准字段，本插件按以下优先级取值：

| 优先级 | 来源 | 说明 |
|---|---|---|
| 1 | 评论 | 从机厅/游戏评论里正则抽取 `1元/币`、`1元一币`、`每币1元`、`1元/2币`、`80币39.9元` 等 |
| 2 | 团购（美团/抖音） | 按店名子串匹配价表（见下） |
| 3 | 连锁价目表 | `ARCADE_CHAIN_COIN_PRICES`，按品牌关键字匹配 |
| 4 | 默认价 | `ARCADE_DEFAULT_COIN_PRICE`，兜底 |

其中**美团 / 抖音**是最贴近实际成交价的参考（两者常有“游戏币套餐/代金券”，
例如“80 币 39.9 元”），但平台反爬强、需要登录，因此用**半自动脚本**维护：

```bash
# 按店名逐个打开美团/抖音搜索页，人工填入套餐价
python scripts/build_deal_prices.py --shop "风云再起上海人民广场店" "城市英雄XX店"

# 按经纬度先拉取附近机厅名单，再逐个校准
python scripts/build_deal_prices.py --nearby 31.2304 121.4737 --radius 10

# 只校准抖音，并指定输出文件
python scripts/build_deal_prices.py --shop "某店" --platform douyin --out deal_coin_prices.json
```

脚本会在浏览器中打开 `美团/抖音` 的搜索页（关键词 = 机厅名 + 游戏币），你人工查看套餐后输入：

- `39.9 80` —— 表示 80 个币卖 39.9 元（自动算出单币价 0.49875 元）
- `=0.5` —— 直接指定单币价 0.5 元
- `s` / 回车 —— 跳过

生成的 JSON 形如 `deal_coin_prices.example.json`，然后在 `.env` 中配置：

```dotenv
ARCADE_DEAL_COIN_PRICES_FILE=/绝对路径/deal_coin_prices.json
```

## 安装

1. 建一个 NoneBot2 项目（或在你现有项目里）安装插件：

```bash
pip install nonebot2[fastapi] nonebot-adapter-onebot httpx
```

然后把本目录下的 `nonebot_plugin_arcade_picker/` 复制到你的插件目录
（通常是 `src/plugins/`），或在 `pyproject.toml` 的 `[tool.nonebot]` 里注册：

```toml
[tool.nonebot]
plugins = ["nonebot_plugin_arcade_picker"]
```

2. 按 `.env.example` 填写配置，**至少**配置：

```dotenv
DRIVER=~fastapi
HOST=0.0.0.0
PORT=8080
ARCADE_PUBLIC_BASE_URL=https://你的公网域名
```

3. 连接一个 OneBot V11 实现（NapCat / Lagrange / go-cqhttp 均可），
将反向 WebSocket 上报地址指向你的 NoneBot（例如 `ws://127.0.0.1:8080/onebot/v11/ws`）。

4. 启动：

```bash
nb run
```

## 指令

| 指令 | 说明 |
|---|---|
| `附近机厅` / `查机厅` / `附近舞萌` / `机厅推荐` / `找机厅` | 回复定位网页，返回附近机厅推荐 |

## 本地测试（无需 QQ）

不需要 QQ 账号也能把完整流程跑一遍：

```bash
# 1) 首次：创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\python.exe -m pip install "nonebot2[fastapi]" nonebot-adapter-onebot httpx

# 2) 一键自动化测试（11 项断言：路由/结果页/指令/美团抖音脚本）
.venv\Scripts\python.exe -X utf8 test_full.py

# 3) 核心逻辑 + 真实机厅数据冒烟（不依赖 NoneBot）
python -X utf8 test_core.py

# 4) 本地演示服务器：浏览器里体验完整流程（定位 -> 推荐结果页）
.venv\Scripts\python.exe demo.py
```

第 4 步启动后，用浏览器打开它打印出的
`http://127.0.0.1:18080/arcade/locate?token=...` 链接并允许定位，即可看到结果页；
也可用打印出的 curl 命令以固定坐标直接测结果接口（按 Ctrl+C 停止）。

## 配置项一览

见 `.env.example`。关键项：

| 配置 | 默认 | 说明 |
|---|---|---|
| `ARCADE_PUBLIC_BASE_URL` | 空 | **必填**，HTTPS 公网地址 |
| `ARCADE_SEARCH_RADIUS_KM` | 10 | 搜索半径 |
| `ARCADE_MAX_RESULTS` | 10 | 最多推荐数 |
| `ARCADE_DEFAULT_COIN_PRICE` | 1.0 | 默认单币价 |
| `ARCADE_CHAIN_COIN_PRICES` | 空 | 连锁价目表 JSON |
| `ARCADE_DEAL_COIN_PRICES` / `_FILE` | 空 | 美团/抖音价表 |
| `ARCADE_WEIGHT_DISTANCE/COUNT/PRICE` | 0.4/0.3/0.3 | 评分权重 |
| `ARCADE_DISTANCE_SCALE_KM` | 3.0 | 距离衰减尺度 |
| `ARCADE_COUNT_SATURATE` | 4 | 机台数饱和值 |
| `ARCADE_PRICE_SCALE_YUAN` | 6.0 | 价格衰减尺度 |

## 常见问题

- **打开网页定位失败**：HTML5 定位要求 **HTTPS**（localhost 除外）。请用域名 + 反代
  （如 Nginx/Caddy + 免费证书）暴露 `ARCADE_PUBLIC_BASE_URL`，并确保 QQ 内置浏览器允许定位。
  插件已在非 HTTPS 场景提供“手动输入坐标”降级。
- **定位授权后没反应**：检查公网地址是否可达、反向代理是否转发 `/arcade/*` 路径。
- **推荐结果偏近/偏贵**：调 `ARCADE_WEIGHT_*` 权重与 `ARCADE_*_SCALE` 尺度即可。
- **美团/抖音价表不生效**：价表按“店名子串”匹配，请确认关键字与 Nearcade 返回的
  机厅名一致；评论里的显式“X元/币”优先级更高，会覆盖价表。

## 目录结构

```
nonebot_plugin_arcade_picker/
├── __init__.py        # 指令匹配、生成定位链接
├── config.py          # 配置 + 美团/抖音价表读取
├── core.py            # 筛选、币价解析、综合评分（不依赖 NoneBot）
├── data.py            # Nearcade API 访问
├── web.py             # FastAPI 路由、定位页/结果页、QQ 推送
scripts/
└── build_deal_prices.py  # 美团/抖音团购价半自动校准
```

## 许可

MIT
