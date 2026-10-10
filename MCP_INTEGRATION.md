# MCP 集成说明

## 一、接入信息

| 项 | 值 |
|---|---|
| MCP Server | 麦当劳中国官方 MCP 服务 |
| 接入地址 | `https://mcp.mcd.cn` |
| 传输协议 | Streamable HTTP |
| 鉴权方式 | 请求头 `Authorization: Bearer <Token>` |
| Token 申请 | [https://open.mcd.cn/mcp](https://open.mcd.cn/mcp)，手机号登录后控制台激活 |
| 限流 | 600 次 / 分钟，超限返回 429 |
| 配置示例 | `mcp-config.example.json`（仅含环境变量占位符） |

---

## 二、实际使用的 Tool

| Tool | 用途 | 流程 | 业务价值 |
|---|---|---|---|
| `now-time-info` | 获取当前日期时间 | A / B / C | 所有倒计时计算的基准，避免模型凭记忆猜日期 |
| `query-my-account` | 积分账户信息 | A / B | 取 `availablePoint` 可用、`frozenPoint` 冻结、`currentMouthExpirePoint` 本月将过期、`nextMouthExpirePoint` 下月将过期、`expiredPoint` 已过期 |
| `query-my-coupons` | 我的优惠券列表 | A / C | 返回格式化文本，含优惠内容、有效期区间、领取时间、**到期标签**（如「今日到期」） |
| `available-coupons` | 麦麦省可领券列表 | A | 按「已领取 / 未领取」状态筛出漏领的券 |
| `query-lottery-info` | 积分抽奖活动信息 | B | `drawPoint` 单次消耗积分、`drawTypeText` 消耗规则、`drawDecision` 资源判定、`prizes[]` 奖品池 |
| `mall-points-products` | 麦麦商城商品列表 | B | 筛 `point > 0` 且 `status = 2` 且 `downTime` 未过期的商品，取最低兑换门槛 |
| `mall-product-detail` | 商城商品详情 | B | 补商品详情（需 `spuId`） |
| `query-nearby-stores` | 附近门店 | C | 确认券的可用门店范围 |
| `query-meals` | 当前在售餐品 | C | 组合消耗方案时的选品依据 |
| `calculate-price` | 价格计算 | C | **实测**券叠加后的应付金额，不凭常识推断优惠规则 |

---

## 三、调用流程

### 流程 A · 资产盘点

```
now-time-info  →  query-my-account  →  query-my-coupons  →  available-coupons
    基准时间          四项积分              券列表              未领的券
                                              ↓
                                    按剩余天数排序 → 紧迫度四级分级
```

### 流程 B · 积分去向决策

```
（先完成流程 A）
query-lottery-info  →  mall-points-products  →  mall-product-detail
   奖品池 + 消耗规则        兑换候选集              现金价 / 积分价
        ↓                        ↓
   抽奖侧折算价值          兑换侧折算价值
        └────────→  对比 → 结论（差距 ≤20% 时优先兑换）
```

### 流程 C · 消耗方案

```
（取流程 A 中 7 天内到期的券）
query-nearby-stores  →  query-meals  →  calculate-price
     可用门店              在售餐品         实测抵扣后金额
```

---

## 四、刻意不默认调用的 Tool

| Tool | 原因 |
|---|---|
| `auto-bind-coupons` | 一键领券属写操作，仅在用户明确要求时才调用 |
| `draw-lottery` | 抽奖消耗积分且不可逆，仅在用户确认后调用 |
| `create-order` / `cancel-order` | 涉及真实交易，本 Skill 只做决策建议，不下单 |
| `mall-create-order` | 同上，积分兑换下单不由 Skill 代劳 |

设计原则：**只读优先，写操作必须经用户确认。**

---

## 五、实测确认的两个关键约束

这两条是实机调用后确认的，不是从文档推测的，Skill 的设计直接建立在此之上。

### 1. 抽奖奖品池没有概率字段

`query-lottery-info` 的 `prizes[]` 只有三个字段：`name`、`imageUrl`、`typeText`。
**没有中奖概率、没有权重、没有库存量。**

因此任何「期望值」都只能按等概率粗估。Skill 的规则是：粗估可以，但必须在输出里标注
「官方未公布概率，此为等概率估算，实际期望值大概率显著低于此」。

### 2. 积分的现金汇率算不出来

`mall-points-products` 返回 `point` 和 `price`，但实测两类商品互斥：

| 商品类型 | `point` | `price` |
|---|---|---|
| 纯积分兑换（如「18.8 元 2 份麦辣鸡翅」兑换资格） | 200 | 0 |
| 纯现金购买（如生日派对、品鉴会） | 0 | 138 |

不存在 `point > 0` 且 `price > 0` 的商品，所以「现金价 ÷ 积分价」的汇率无解。

Skill 因此放弃绝对汇率，改用机会成本对比：取最低积分门槛的上架商品作为锚点，
只回答「积分够不够换」，不回答「积分值多少钱」。

### 3. `status = 2` 不等于还能兑

实测发现 `status = 2`（上架）的商品里，有些 `downTime` 已经过去大半年。
只按 `status` 筛选会把最低兑换门槛算成 1 积分。必须同时校验 `downTime`。

### 4. 通用规则

任何字段拿不到，就在输出里说明拿不到，不做填充、不做估算后当事实陈述。
