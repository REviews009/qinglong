#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
南网在线自动签到脚本
青龙面板适用
"""

import os
import sys
import json
import time
import requests
from datetime import datetime

# ============ 配置区域 ============

# 从环境变量读取配置
TOKEN = os.environ.get("NANWANG_TOKEN", "")
UTDID = os.environ.get("NANWANG_UTDID", "")
USERID = os.environ.get("NANWANG_USERID", "")
UA = os.environ.get("NANWANG_UA", "NanWangOnline/5.0.0 (iPhone; iOS 16.0; Scale/3.00)")

# 基础配置
BASE_URL = "https://95598.csg.cn"
PRODUCT_ID = "PRI6AA2207221609_IOS-default"
PRODUCT_VERSION = "1.0.0.0"

# 签到接口（需要根据实际抓包修改）
# 以下为占位示例，请替换为真实的签到接口
SIGN_URL = f"{BASE_URL}/mp/mpaas/api/sign/doSign"  # 示例，需替换

# ============ 通知函数 ============

def send_notify(title, content):
    """调用青龙通知"""
    try:
        # 新版青龙 2.10+
        notify_dir = "/ql/data/scripts"
        if not os.path.exists(f"{notify_dir}/sendNotify.js"):
            notify_dir = "/ql/scripts"
        
        if os.path.exists(f"{notify_dir}/sendNotify.js"):
            import subprocess
            cmd = f'''cd "{notify_dir}" && node -e "const {{ sendNotify }} = require('./sendNotify'); sendNotify('{title}', '{content}').catch(e => console.error('通知失败:', e.message));"'''
            subprocess.run(cmd, shell=True, capture_output=True)
    except Exception as e:
        print(f"通知发送失败: {e}")

# ============ 签到核心 ============

class NanWangSign:
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            "Host": "95598.csg.cn",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh-Hans;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "User-Agent": UA,
            "utdId": UTDID,
            "userId": USERID,
            "productId": PRODUCT_ID,
            "productVersion": PRODUCT_VERSION,
            "Content-Type": "application/json",
        }
        if TOKEN:
            self.headers["Cookie"] = TOKEN
            self.headers["Authorization"] = f"Bearer {TOKEN}"
    
    def get_common_params(self):
        """获取通用请求参数"""
        return {
            "utdId": UTDID,
            "userId": USERID,
            "productId": PRODUCT_ID,
            "productVersion": PRODUCT_VERSION,
            "timestamp": str(int(time.time() * 1000)),
        }
    
    def check_login(self):
        """检查登录状态"""
        try:
            # 查询用户信息接口（示例，需根据实际抓包调整）
            url = f"{BASE_URL}/mp/mpaas/api/user/info"
            params = self.get_common_params()
            
            resp = self.session.get(url, headers=self.headers, params=params, timeout=10)
            data = resp.json()
            
            if data.get("code") == 200 or data.get("success"):
                print("✅ 登录状态有效")
                return True
            else:
                print(f"❌ 登录状态异常: {data}")
                return False
                
        except Exception as e:
            print(f"❌ 检查登录失败: {e}")
            return False
    
    def do_sign(self):
        """执行签到"""
        try:
            print(f"\n{'='*50}")
            print(f"🕐 开始签到: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*50}\n")
            
            # 先检查登录
            if not self.check_login():
                return False, "登录状态失效"
            
            # 获取签到状态（示例接口，需替换）
            # status_url = f"{BASE_URL}/mp/mpaas/api/sign/status"
            # status_resp = self.session.get(status_url, headers=self.headers, timeout=10)
            # print(f"签到状态: {status_resp.text}")
            
            # 执行签到（示例接口，需替换为实际签到接口）
            # 根据抓包日志，南网在线使用 mPaaS 框架，签到可能是 rubikBehavior 或 trackEvent
            sign_data = {
                **self.get_common_params(),
                "bizCode": "sign",
                "event": "dailySign",
                # 根据实际抓包补充更多参数
            }
            
            # 实际签到请求（需要替换为真实接口）
            resp = self.session.post(
                SIGN_URL,
                headers=self.headers,
                json=sign_data,
                timeout=10
            )
            
            result = resp.json()
            print(f"📤 签到响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
            
            if result.get("code") == 200 or result.get("success"):
                msg = result.get("message", "签到成功")
                print(f"✅ 签到成功: {msg}")
                return True, msg
            else:
                msg = result.get("message", "签到失败")
                print(f"❌ 签到失败: {msg}")
                return False, msg
                
        except requests.exceptions.Timeout:
            return False, "请求超时"
        except requests.exceptions.ConnectionError:
            return False, "连接失败"
        except Exception as e:
            return False, f"异常: {str(e)}"
    
    def query_points(self):
        """查询积分（示例，需根据实际接口调整）"""
        try:
            url = f"{BASE_URL}/mp/mpaas/api/points/query"
            params = self.get_common_params()
            
            resp = self.session.get(url, headers=self.headers, params=params, timeout=10)
            data = resp.json()
            
            if data.get("code") == 200:
                points = data.get("data", {}).get("points", "未知")
                print(f"💎 当前积分: {points}")
                return points
            return "查询失败"
        except Exception as e:
            print(f"❌ 查询积分失败: {e}")
            return "查询失败"

# ============ 主程序 ============

def main():
    print("=" * 60)
    print("     南网在线自动签到脚本")
    print("=" * 60)
    
    # 检查必要配置
    if not all([TOKEN, UTDID, USERID]):
        msg = "❌ 缺少必要环境变量，请检查 NANWANG_TOKEN / NANWANG_UTDID / NANWANG_USERID"
        print(msg)
        send_notify("南网在线签到", msg)
        sys.exit(1)
    
    signer = NanWangSign()
    success, msg = signer.do_sign()
    
    # 查询积分
    points = signer.query_points()
    
    # 构建通知内容
    today = datetime.now().strftime("%Y-%m-%d")
    if success:
        title = f"✅ 南网在线签到成功 [{today}]"
        content = f"签到结果: {msg}\n当前积分: {points}\n签到时间: {datetime.now().strftime('%H:%M:%S')}"
    else:
        title = f"❌ 南网在线签到失败 [{today}]"
        content = f"失败原因: {msg}\n当前积分: {points}\n请检查配置或抓包更新接口"
    
    print(f"\n{'='*60}")
    print(content)
    print(f"{'='*60}")
    
    send_notify(title, content)
    
    # 退出码
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()