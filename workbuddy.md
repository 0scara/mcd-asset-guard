# workbuddy.md

本文件记录 `mcd-asset-guard` 在腾讯 WorkBuddy 中的开发对话上下文，
用于核验本项目是否真实使用 WorkBuddy 开发（麦当劳程序员创意开发大赛 WorkBuddy 联动奖励条件）。

## 一、基本信息

| 项 | 内容 |
|---|---|
| 项目名称 | mcd-asset-guard · 麦当劳权益到期管家 |
| 开发工具 | 腾讯 WorkBuddy |
| MCP 接入方式 | WorkBuddy 侧边栏【专家·技能·连接器】→【连接器】→【自定义连接器】→【配置 MCP】 |
| MCP 服务名 | `mcd-mcp`（streamablehttp，`https://mcp.mcd.cn`） |
| Skill 安装位置 | `~/.workbuddy/skills/mcd-asset-guard/SKILL.md` |
| 开发日期 | 2026-10-09 |

---

## 二、对话上下文（关键轮次）

### 轮次 1 · 需求调研

**用户**：查询 https://github.com/M-China/mcd-developer-innovation-challenge 这个活动，分析我们能做什么

**WorkBuddy**：抓取活动 README、`activityGuidelines.md`、`RANKING.md` 及 `mcd-mcp-server` 仓库，
梳理出赛程、奖励、报名门槛、必交文件清单，并比对当时榜单（榜首 13★、全榜 12 个项目），
给出结论：本质是 Star 拉票赛而非技术评审赛，但竞争稀疏、保底门槛极低；
同时标出红海与蓝海选题区。

### 轮次 2 · 方案设计

**用户**：选定「积分与券生命周期管理」方向，目标保底进前 100

**WorkBuddy**：确定 Skill 载体为 WorkBuddy `SKILL.md`（而非 Python 服务），
理由是活动本身即 Skill 大赛，且用 WorkBuddy 开发才能提交本文件领取积分。
完成三条流程设计（A 资产盘点 / B 积分去向决策 / C 消耗方案）、
紧迫度四级分级、输出格式模板，并制作 Logo、banner、架构图三份视觉资产。

### 轮次 3 · MCP 接入与实机联调

**用户**：提供 MCP Token

**WorkBuddy**：写入 `~/.workbuddy/mcp.json` 完成连接器配置，
随后实机调用 `tools/list` 拉取全部 35 个工具，
并逐个探测核心工具的入参与返回结构。

### 轮次 4 · 依据实测结果修正设计

**WorkBuddy**：实测推翻了两处按文档推测的设计，并回写至 `SKILL.md`：

1. `query-lottery-info` 的 `prizes[]` 不含中奖概率字段 → 期望值只能等概率粗估且必须标注
2. 商城积分商品与现金商品互斥（`point>0,price=0` / `point=0,price>0`）→ 积分汇率无解，改机会成本对比

### 轮次 5 · 冒烟测试与再修正

**用户**：我怎么测试

**WorkBuddy**：产出 `tools/smoke_test.py`（只读，6 项），首次运行 5/6 通过——
`mall-points-products` 解析失败。两处修正：

1. JSON 提取改用 `raw_decode` 逐位置试解（响应正文混有 `{data[].spuName}` 模板占位符）
2. 筛选条件补上 `downTime > 今天`：`status = 2` 只表示上架，不代表仍在兑换期，
   漏掉这层会把最低兑换门槛算成 1 积分（正确值 50 积分）

复测 6/6 通过。

### 轮次 6 · 验收

**用户**：我测试通过了

**WorkBuddy**：整理本文件，进入提交阶段。

---

## 三、MCP 实机调用记录

通过 WorkBuddy 接入的 `mcd-mcp` 连接器，实际调用并验证的工具：

| Tool | 调用结果 |
|---|---|
| `tools/list` | 返回 35 个工具，本项目用到其中 10 个 |
| `now-time-info` | 取到 `data.date`（2026-10-09）作为倒计时基准 |
| `query-my-account` | 取到 `availablePoint` / `frozenPoint` / `currentMouthExpirePoint` / `expiredPoint` 等 |
| `query-my-coupons` | 返回格式化券列表，含有效期与「今日到期」标签 |
| `available-coupons` | 返回含「已领取 / 未领取」状态 |
| `query-lottery-info` | `drawPoint` 单次消耗积分、`drawDecision`、`prizes[]` |
| `mall-points-products` | 用于计算最低兑换门槛 |

冒烟测试输出（真实运行）：

```
流程 A · 资产盘点      PASS  now-time-info / query-my-account / query-my-coupons / available-coupons
流程 B · 积分去向决策  PASS  query-lottery-info / mall-points-products
6/6 项通过
```

---

## 四、结论

本项目全程在腾讯 WorkBuddy 中完成：需求分析、方案设计、视觉资产制作、
MCP 连接器配置与实机联调、冒烟测试与缺陷修正。
所有 MCP 调用均通过 WorkBuddy 配置的 `mcd-mcp` 连接器发起，非离线构造数据。
