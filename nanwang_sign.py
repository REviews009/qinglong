#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
南网在线自动签到脚本 v2（Token版）
青龙面板适用

环境变量:
    NANWANG_TOKEN - x-auth-token 值（必填，更稳定）
    NANWANG_COOKIE - Cookie字符串（备用，可选）

推荐使用 NANWANG_TOKEN，因为:
    1. x-auth-token 在会话期间始终不变
    2. Cookie中的CAMSID会被服务端刷新，容易失效
    3. 只需要一个值，配置更简单
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# ============ 配置 ============
BASE_URL = "https://95598.csg.cn"
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/20A362 Ariver/1.0.15 NWZX/Portal Nebula WK WK RVKType(0) NebulaX/1.0.0"

# 签到任务ID（固定值）
TASK_ID = "654165b1z56x1bq1"

# ============ 通知 ============
def send_notify(title, content):
    """调用青龙通知"""
    try:
        notify_dir = "/ql/data/scripts"
        if not os.path.exists(f"{notify_dir}/sendNotify.js"):
            notify_dir = "/ql/scripts"

        if os.path.exists(f"{notify_dir}/sendNotify.js"):
            import subprocess
            cmd = f'cd "{notify_dir}" && node -e "const {{ sendNotify }} = require('./sendNotify'); sendNotify('{title}', '{content}').catch(e => console.error('通知失败:', e.message));"'
            subprocess.run(cmd, shell=True, capture_output=True)
    except Exception as e:
        print(f"通知发送失败: {e}")

# ============ 南网签到类 ============
class NanWangSign:
    def __init__(self, token, cookie=None):
        """
        初始化
        :param token: x-auth-token 值
        :param cookie: 可选，完整的Cookie字符串
        """
        self.token = token
        self.cookie = cookie or f"CAMSID={token}; bfsResponseHandleType=0"
        self.session = requests.Session()
        self.headers = {
            "Host": "95598.csg.cn",
            "Accept": "*/*",
            "Accept-Charset": "utf-8",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "User-Agent": UA,
            "need-crypto": "0",
            "x-auth-token": token,
            "Origin": "https://95598.csg.cn",
            "Referer": "https://0000000000000141.95598.csg.cn/0000000000000141/1.0.3.1/index.html",
        }

    def _request(self, method, url, json_data=None, params=None):
        """统一请求方法，自动处理Cookie"""
        try:
            # 每次请求都更新Cookie（如果需要）
            self.headers["Cookie"] = self.cookie

            if method.upper() == "GET":
                resp = self.session.get(url, headers=self.headers, params=params, timeout=15)
            else:
                resp = self.session.post(url, headers=self.headers, json=json_data, timeout=15)

            # 检查响应中的Set-Cookie，更新CAMSID
            if "Set-Cookie" in resp.headers:
                set_cookie = resp.headers.get("Set-Cookie", "")
                if "CAMSID=" in set_cookie:
                    new_camsid = set_cookie.split("CAMSID=")[1].split(";")[0]
                    self.cookie = f"CAMSID={new_camsid}; bfsResponseHandleType=0"
                    print(f"   🔄 Cookie已更新: CAMSID={new_camsid}")

            return resp.json()
        except requests.exceptions.Timeout:
            return {"sta": "-1", "message": "请求超时"}
        except requests.exceptions.ConnectionError:
            return {"sta": "-1", "message": "连接失败"}
        except Exception as e:
            return {"sta": "-1", "message": f"请求异常: {e}"}

    def check_account(self):
        """查询账户积分信息"""
        url = f"{BASE_URL}/mp/w2/szfw-points-txhsj/account/checkAccountIsExist"
        data = self._request("POST", url, {})

        if data.get("sta") == "00":
            info = data.get("data", {})
            return {
                "userId": info.get("userId", ""),
                "grantPoints": info.get("grantPoints", 0),
                "freezePoints": info.get("freezePoints", 0),
                "pointLevelId": info.get("pointLevelId", ""),
            }
        return None

    def get_sign_list(self):
        """获取签到列表，判断今天是否已签到"""
        url = f"{BASE_URL}/mp/w2/szfw-points-txhsj/taskInfo/taskSignList"
        data = self._request("POST", url, {})

        if data.get("sta") == "00":
            info = data.get("data", {})
            finish_status = info.get("taskFinishStatus", "0")
            return {
                "finished": finish_status == "1",
                "singCount": info.get("singCount", 0),
                "taskRuleId": info.get("taskRuleId", ""),
                "signGainPoints": info.get("signGainPoints", 1),
            }
        return None

    def do_sign(self):
        """执行签到"""
        url = f"{BASE_URL}/mp/w2/szfw-points-txhsj/taskInfo/signOperate"
        payload = {
            "taskId": TASK_ID,
            "thisGainPoints": 1
        }
        return self._request("POST", url, payload)

    def get_task_list(self):
        """获取任务列表"""
        url = f"{BASE_URL}/mp/w2/szfw-points-txhsj/taskInfo/taskInfoList"
        return self._request("POST", url, {})

# ============ 主程序 ============
def main():
    print("=" * 60)
    print("     南网在线自动签到脚本 v2 (Token版)")
    print("=" * 60)

    # 优先读取 TOKEN，其次读取 COOKIE
    token = os.environ.get("NANWANG_TOKEN", "").strip()
    cookie = os.environ.get("NANWANG_COOKIE", "").strip()

    if not token and not cookie:
        msg = """❌ 缺少环境变量！

请配置以下任一变量（推荐用 TOKEN）：

【推荐】NANWANG_TOKEN: 你的x-auth-token值
         优点: 更稳定，服务端不会刷新
         获取: 从任意请求头中提取 x-auth-token

【备用】NANWANG_COOKIE: 完整的Cookie字符串
         缺点: CAMSID会被刷新，容易失效
"""
        print(msg)
        send_notify("南网在线签到失败", "缺少环境变量 NANWANG_TOKEN 或 NANWANG_COOKIE")
        sys.exit(1)

    # 如果只有cookie没有token，尝试从cookie提取
    if not token and cookie:
        if "CAMSID=" in cookie:
            token = cookie.split("CAMSID=")[1].split(";")[0]
            print(f"📝 从Cookie提取Token: {token}")

    signer = NanWangSign(token, cookie)

    # 查询账户信息
    print("\n📋 查询账户信息...")
    account = signer.check_account()
    if not account:
        msg = "❌ Token失效或查询账户失败，请更新 NANWANG_TOKEN"
        print(msg)
        send_notify("南网在线签到失败", msg)
        sys.exit(1)

    print(f"   用户ID: {account['userId']}")
    print(f"   可用积分: {account['grantPoints']}")
    print(f"   冻结积分: {account['freezePoints']}")

    # 查询签到状态
    print("\n📋 查询签到状态...")
    sign_info = signer.get_sign_list()
    if not sign_info:
        msg = "❌ 获取签到状态失败"
        print(msg)
        send_notify("南网在线签到失败", msg)
        sys.exit(1)

    today = datetime.now().strftime("%Y-%m-%d")

    if sign_info["finished"]:
        msg = f"✅ 今日({today})已签到，无需重复签到"
        print(msg)
        print(f"   连续签到: {sign_info['singCount']} 天")

        account = signer.check_account()
        points = account["grantPoints"] if account else "未知"

        content = f"签到状态: 今日已签到\n连续签到: {sign_info['singCount']} 天\n当前积分: {points}"
        send_notify(f"✅ 南网在线签到 [{today}]", content)
        sys.exit(0)

    # 执行签到
    print(f"\n📝 执行签到...")
    result = signer.do_sign()

    if result.get("sta") == "00":
        gain_points = result.get("data", 1)
        msg = f"✅ 签到成功，获得 {gain_points} 积分"
        print(msg)

        time.sleep(1)
        account = signer.check_account()
        points = account["grantPoints"] if account else "未知"

        content = f"签到结果: 成功\n获得积分: {gain_points}\n当前积分: {points}"
        send_notify(f"✅ 南网在线签到成功 [{today}]", content)
        sys.exit(0)
    else:
        msg = f"❌ 签到失败: {result.get('message', '未知错误')}"
        print(msg)
        print(f"   响应: {json.dumps(result, ensure_ascii=False)}")

        send_notify(f"❌ 南网在线签到失败 [{today}]", msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
