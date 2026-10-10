#!/usr/bin/env python3
"""mcd-asset-guard 冒烟测试

只做只读调用，验证流程 A / B 依赖的 MCP 数据链路是否可用。
不涉及任何领券、下单、抽奖等写操作。

用法:
    export MCD_MCP_TOKEN=你的Token
    python3 tools/smoke_test.py
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

URL = "https://mcp.mcd.cn"


def call(name, args=None):
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
         "params": {"name": name, "arguments": args or {}}}
    ).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + os.environ["MCD_MCP_TOKEN"],
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode())
    if "error" in res:
        raise RuntimeError(res["error"])
    return res["result"]["content"][0]["text"]


def extract_json(text):
    """从带 Markdown 说明的响应里取出原始 JSON 对象。

    响应正文里混有 `{data[].spuName}` 这类模板占位符，贪婪正则会把它们一起吞掉，
    所以改成逐位置试解，取解出来的最长那一段。
    """
    dec = json.JSONDecoder()
    best, best_len = None, 0
    for i, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            obj, end = dec.raw_decode(text[i:])
        except ValueError:
            continue
        if end > best_len:
            best, best_len = obj, end
    return best


def check(label, fn):
    try:
        fn()
        print(f"  PASS  {label}")
        return True
    except Exception as e:
        print(f"  FAIL  {label} -> {e}")
        return False


def main():
    if not os.environ.get("MCD_MCP_TOKEN"):
        sys.exit("请先设置环境变量 MCD_MCP_TOKEN")

    ok = []

    print("流程 A · 资产盘点")
    now = None
    def t_now():
        nonlocal now
        d = extract_json(call("now-time-info"))
        assert d and "date" in str(d), "取不到日期"
        now = re.search(r'"date"\s*:\s*"([^"]+)"', json.dumps(d)).group(1)
    ok.append(check("now-time-info", t_now))

    acct = {}
    def t_acct():
        d = extract_json(call("query-my-account"))["data"]
        for k in ("availablePoint", "frozenPoint",
                  "currentMouthExpirePoint", "expiredPoint"):
            assert k in d, f"缺少字段 {k}"
        acct.update(d)
    ok.append(check("query-my-account", t_acct))

    def t_coupons():
        text = call("query-my-coupons")
        assert "优惠券" in text, "返回不像券列表"
    ok.append(check("query-my-coupons", t_coupons))

    def t_avail():
        text = call("available-coupons")
        assert "状态" in text, "返回里没有领取状态"
    ok.append(check("available-coupons", t_avail))

    print("\n流程 B · 积分去向决策")
    lot = {}
    def t_lottery():
        d = extract_json(call("query-lottery-info"))["data"]
        assert d["status"]["code"] == "SUCCESS", "活动状态: " + d["status"]["code"]
        lot.update(d)
    ok.append(check("query-lottery-info", t_lottery))

    def t_mall():
        data = extract_json(call("mall-points-products"))["data"]
        # status=2 只表示上架，不代表还能兑——有些商品 status 仍是 2 但 downTime 早已过去
        cutoff = now or ""
        cheapest = min((int(x["point"]) for x in data
                        if int(x["point"]) > 0
                        and x["status"] == 2
                        and x.get("downTime", "") > cutoff), default=None)
        assert cheapest, "没有仍在兑换期内的积分商品"
        lot["_minPoint"] = cheapest
    ok.append(check("mall-points-products", t_mall))

    print("\n" + "=" * 46)
    if acct:
        print(f"基准日期      {now}")
        print(f"可用积分      {acct['availablePoint']}")
        print(f"本月将过期    {acct['currentMouthExpirePoint']}")
        print(f"已过期        {acct['expiredPoint']}")
    if lot.get("drawPoint"):
        draw = int(lot["drawPoint"])
        avail = float(acct.get("availablePoint", 0))
        print(f"单次抽奖消耗  {draw} 积分")
        print(f"可抽次数      {int(avail // draw)} 次")
    if lot.get("_minPoint"):
        print(f"商城最低门槛  {lot['_minPoint']} 积分")
    print("=" * 46)

    failed = ok.count(False)
    print(f"\n{len(ok) - failed}/{len(ok)} 项通过")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
