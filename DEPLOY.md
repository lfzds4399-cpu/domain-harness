# DEPLOY checklist

从 0 到上实盘的步骤。每一步都要打勾再往下走。

## 阶段 0：本地跑通（DRY_RUN）

- [ ] `pip install -r requirements.txt`
- [ ] `python cli.py status` 能输出（无报错）
- [ ] `python cli.py scan --target 20` 能跑完
- [ ] `python cli.py watchlist --top 5` 能看到候选
- [ ] `python cli.py appraise example.ai` 能输出 score breakdown
- [ ] `python cli.py auto-register --dry` 能模拟决策

## 阶段 1：接 AI Council（免钱测试）

- [ ] 设 `ANTHROPIC_API_KEY` 环境变量（你 memory 里已有）
- [ ] 设 `DEEPSEEK_API_KEY`（trading 项目已用过）
- [ ] `python cli.py appraise neonledger.io --council` 看到 council_score
- [ ] 跑 `python cli.py scan` 验证高分候选会自动喂 council

## 阶段 2：开 Porkbun 账号（最便宜，$9.13/.com）

- [ ] 注册 https://porkbun.com 并完成支付方式绑定
- [ ] Account → API Access → Generate Key/Secret
- [ ] 编辑 `manifest.yaml`：
  ```yaml
  registrars:
    porkbun:
      enabled: true
      api_key: "pk1_..."
      secret_key: "sk1_..."
  ```
- [ ] **保持 mode: dry_run**，跑 `auto-register --dry` 验证决策不下单

## 阶段 3：第一笔实盘（手动）

- [ ] manifest 改 `mode: live`
- [ ] 选一个低风险候选（score ≥ 80 且你看着顺眼）
- [ ] `python cli.py buy <domain>` 走交互确认流程
- [ ] 检查 Porkbun 后台域名已到账
- [ ] 检查 `data/portfolio.json` 已记录
- [ ] 检查 `data/budget_state.json` 已扣减

## 阶段 4：cron 自动化

- [ ] **降低预算**：先把 `daily_limit` 设到 $30，月限 $200，跑一周看看
- [ ] 配 cron（见 README）
- [ ] 每天看 `logs/YYYY-MM-DD.jsonl` 验证决策没出错

## 阶段 5：销售上线

- [ ] 注册 Dan.com 卖家账号 + 申请 API key
- [ ] manifest 中 `sales.platforms.dan.enabled = true`
- [ ] 持有 ≥90 天的域名跑 `python cli.py review` 自动挂牌
- [ ] 收到买家询价：`python -c "from agents import sales; print(sales.negotiate_reply('xxx.com', 200))"`

## 监控/止损

| 信号 | 行动 |
|------|------|
| 一周买入 ≥10 个但平均 score < 75 | 提高 `min_score_auto_buy` 到 90 |
| 月预算用满但 0 销售 | 暂停 cron，进入观察期 |
| 某个注册商连续 3 天注册失败 | 在 manifest 里临时 disable |
| Porkbun 账户余额 < $50 | 充值或自动停止下单（reserve_threshold）|

## 已知坑

- **WHOIS 缓存**：DNS+RDAP 不是 100% 准；drop catch 场景必须接注册商 check API
- **拍卖不在自动流程内**：拍卖竞价永远人工拍板（manifest 里没启用）
- **续费成本**：注册便宜，续费贵；高分域名留 1-2 年没卖出要重新评估
- **法律**：持有商标相关域名可能被 UDRP 强制转移 + 罚款；别碰 apple/google/openai 等
