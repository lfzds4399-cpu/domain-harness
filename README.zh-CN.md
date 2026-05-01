# domain-harness

自动化域名抢注 + 投资 + 出售的 harness 流水线。

**核心能力**
- **Discovery**：AI 生成可注册短域名 + 过期域名榜单抓取（每天 100~500 候选）
- **Valuation**：本地多维打分（长度/TLD/字典/可发音/关键词/惩罚） + Claude+DeepSeek AI Council 双盲复评
- **Acquisition**：多注册商适配（Porkbun / Cloudflare / Namecheap / GoDaddy），按优先级 fallback
- **Sales**：Dan / Afternic / Sedo 自动挂牌 + AI 议价回复
- **RiskGuard**：日预算 / 月预算 / 单域名 三层硬刹车

## 安装

```bash
cd "D:/作品/domain-harness"
pip install -r requirements.txt
```

## 快速试跑（DRY_RUN，不动钱）

```bash
# 1. 看状态
python cli.py status

# 2. 跑一次扫描（生成候选 → 估值 → 入 watchlist）
python cli.py scan --target 30

# 3. 看观察名单
python cli.py watchlist --top 10

# 4. 单域名估值
python cli.py appraise pay.com --council

# 5. 看预算
python cli.py budget

# 6. 试跑自动注册（DRY_RUN 不会真扣钱）
python cli.py auto-register --dry
```

## 上实盘的 4 步

1. **接 API key** — 在 `manifest.yaml` 里把 `registrars.porkbun.enabled` 改成 `true`，填上 `api_key` + `secret_key`（Porkbun 后台→Account→API Access）
2. **接 AI key**（可选但强烈推荐）— 设置环境变量
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-...
   export DEEPSEEK_API_KEY=sk-...
   ```
3. **改 mode** — `manifest.yaml` 里 `mode: dry_run` → `mode: live`
4. **第一笔手动确认** — `python cli.py buy mydomain.com`，先手动跑一笔验证流程，再考虑开 cron 全自动

## Cron 推荐配置（Linux/Mac）

```cron
# 每天 06:00 扫描 + 06:30 自动注册
0 6 * * * cd /path/to/domain-harness && python cli.py scan
30 6 * * * cd /path/to/domain-harness && python cli.py auto-register

# 每月 1 号 portfolio 回顾
0 9 1 * * cd /path/to/domain-harness && python cli.py review
```

## 安全开关

| 风险 | 防护 |
|------|------|
| 失控买买买 | `budget_guard` 三层硬刹车（日/月/单域名） |
| 重复买入 | `dup_check` 比对 portfolio.owned |
| 注册不可用域名 | `whois_check` DNS+RDAP 双确认 |
| AI 估值偏差 | `min_consensus` 双 AI 必须达成共识 |
| 注册商单点故障 | 多注册商按优先级 fallback |

## 项目结构

```
domain-harness/
├── manifest.yaml          # 全部配置（预算/TLD/评分/注册商/AI/销售）
├── cli.py                 # 顶层 CLI
├── core/                  # 配置/存储/日志
├── validators/            # budget_guard / dup_check / whois_check
├── agents/
│   ├── discovery_aigen.py     # AI 生成候选
│   ├── discovery_expired.py   # 过期域名抓榜
│   ├── valuation.py           # 本地多维打分
│   ├── valuation_council.py   # Claude+DeepSeek 复评
│   ├── acquisition.py         # 多注册商下单
│   └── sales.py               # 挂牌+议价
├── pipelines/
│   ├── daily_scan.py
│   ├── auto_register.py
│   └── portfolio_review.py
└── data/
    ├── portfolio.json     # 持仓+watchlist+黑名单+已售
    ├── budget_state.json  # 预算消耗
    └── scan_history.jsonl # 扫描历史（追加日志）
```

## 风险提示（必读）

1. **域名投资是长周期生意**——多数域名持有 1-3 年才能卖出，年回报中位数约 5%-15%
2. **Drop Catch 不是新手该碰的**——热门过期域名抢注竞争白热化，需要专业 catcher 服务（DropCatch/SnapNames），普通 API 抢不到
3. **Cloudflare Registrar 不接 drop catch**——只能续费/迁入，做投资请用 Porkbun/Namecheap
4. **Cybersquatting 风险**——别注册带商标的域名（apple/nike/openai 等），会被 UDRP 仲裁强制转移
5. **AI Council 评分不能盲信**——它只是参考，最终决策权在 manifest 的预算守卫

## 下一步可扩展的方向

- 接 Estibot API 做交叉估值
- 接 Wayback Machine 看历史快照（有过站点的域名 SEO 价值高）
- 接 Ahrefs/Moz 看 backlinks（DA/PA）
- GoDaddy Auctions 实时竞价 bot
- Telegram bot 推送高分候选 + 询价通知
- 自建 parking 页面（Vercel/Cloudflare Pages）
