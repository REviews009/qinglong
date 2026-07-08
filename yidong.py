# -*- coding=UTF-8 -*-
# ===================================================
# 中国移动云盘 - 青龙单文件版 (修复版 2026-07-08)
# 基于 Surge 抓包分析，全面适配新版 API (m.mcloud.139.com)
# 
# 环境变量: ydyp_ck
# 格式: 完整的 Cookie 字符串 (从 Surge/Charles 抓包中复制)
# 多账号使用 @ 分隔
#
# 获取方式:
# 1. 使用 Surge/Charles 抓包移动云盘 App
# 2. 进入"签到"页面
# 3. 找到任意请求 (如 infoV3 或 taskListV2)
# 4. 复制请求头中的 Cookie 完整内容
# 5. 粘贴到青龙环境变量 ydyp_ck 中
#
# 示例 Cookie 格式:
# JSESSIONID=xxx;jwtToken=eyJhbG...;userDomainId=1039...;cookieToken=YZsid...;cookieTokenKey=bW9iaWxl...;smidV2=2026...;_c_WBKFRo=...
#
# ⚠️ 注意: Cookie 会过期(约几小时)，需要定期更新！
# =====================================================

import asyncio
import json
import os
import random
import re
import time
from datetime import datetime

import httpx

# ===== 青龙单文件版内置函数 =====
def fn_print(msg):
    print(msg)

def get_env(name, split="@"):
    value = os.getenv(name, "")
    if not value:
        return []
    return value.split(split)

try:
    from sendNotify import send_notification_message_collection
except Exception:
    def send_notification_message_collection(msg):
        pass
# ===== 青龙单文件版内置函数结束 =====

ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MCloudApp/13.0.1 iPhone AppLanguage/zh-CN"

ydyp_ck = get_env("ydyp_ck", "@")

# 调试模式 - 打印详细请求信息
DEBUG = os.getenv("ydyp_debug", "false").lower() == "true"


def parse_cookie(cookie_str):
    """解析 Cookie 字符串为字典"""
    cookies = {}
    for item in cookie_str.split(';'):
        item = item.strip()
        if '=' in item:
            key, value = item.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def extract_account_from_jwt(jwt_token):
    """从 jwtToken 中提取信息"""
    try:
        import base64
        parts = jwt_token.split('.')
        if len(parts) >= 2:
            payload = parts[1]
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            data = json.loads(decoded)

            # 解析 sub 字段
            sub_str = data.get('sub', '{}')
            sub_data = json.loads(sub_str)

            # 获取 userDomainId
            user_domain_id = sub_data.get('userDomainId', '')

            # 获取 areaCode (省份)
            area_code = sub_data.get('areaCode', '')

            # 获取 provCode
            prov_code = sub_data.get('provCode', '')

            # 获取 deviceid
            device_id = sub_data.get('deviceid', '')

            # 获取加密的 account
            account_enc = sub_data.get('account', '')

            return {
                'userDomainId': user_domain_id,
                'areaCode': area_code,
                'provCode': prov_code,
                'deviceid': device_id,
                'account_enc': account_enc,
                'exp': data.get('exp', 0),
                'iat': data.get('iat', 0)
            }
    except Exception as e:
        if DEBUG:
            fn_print(f"[DEBUG] JWT 解析异常: {e}")
    return {}


def extract_phone_from_cookie_token_key(ctk):
    """从 cookieTokenKey 中提取手机号"""
    try:
        import base64
        decoded = base64.b64decode(ctk)
        text = decoded.decode('utf-8', errors='ignore')
        # 格式: mobile:手机号:...
        parts = text.split(':')
        if len(parts) >= 2:
            return parts[1]
    except:
        pass
    return ""


class MobileCloudDisk:
    def __init__(self, cookie_str):
        self.client = httpx.AsyncClient(verify=False, timeout=60)
        self.timestamp = str(int(round(time.time() * 1000)))

        # 解析完整 Cookie
        self.cookies_dict = parse_cookie(cookie_str)

        # 提取关键信息
        self.jwt_token = self.cookies_dict.get('jwtToken', '')
        self.jwt_info = extract_account_from_jwt(self.jwt_token) if self.jwt_token else {}

        # 获取手机号
        self.account = extract_phone_from_cookie_token_key(
            self.cookies_dict.get('cookieTokenKey', '')
        )
        if not self.account and self.jwt_info:
            # 尝试从其他字段获取
            pass

        self.encrypt_account = self.account[:3] + "*" * 4 + self.account[7:] if len(self.account) >= 11 else (self.account or "未知")

        # 获取 deviceId (从 thumbcache 或 jwt)
        self.device_id = self.cookies_dict.get('.thumbcache_45700955f71be4ef518b0a1af26a3f40', '')
        if not self.device_id:
            for key in self.cookies_dict:
                if 'thumbcache' in key:
                    self.device_id = self.cookies_dict[key]
                    break
        if not self.device_id and self.jwt_info:
            self.device_id = self.jwt_info.get('deviceid', '')

        # 检查 Cookie 完整性
        self.cookie_valid = self._validate_cookie()

        # 基础请求头
        self.base_headers = {
            'User-Agent': ua,
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Origin': 'https://m.mcloud.139.com',
            'Referer': 'https://m.mcloud.139.com/portal/mobilecloud/index.html?path=newsignin&sourceid=1002&enableShare=1',
        }

        # 带认证的请求头
        self.auth_headers = {
            **self.base_headers,
            'jwtToken': self.jwt_token,
            'appVersion': '13.0.1.0',
            'deviceId': self.device_id,
            'activityId': 'sign_in_3',
            'showLoading': 'true',
        }

        # 汇总信息
        self.summary = {
            "account": self.encrypt_account,
            "signed": False,
            "clouds": 0,
            "messages": []
        }

    def _validate_cookie(self):
        """验证 Cookie 是否完整"""
        required = ['jwtToken']
        missing = [k for k in required if k not in self.cookies_dict or not self.cookies_dict[k]]
        if missing:
            return False, f"缺少必要字段: {', '.join(missing)}"

        # 检查 jwtToken 是否过期
        if self.jwt_info:
            exp = self.jwt_info.get('exp', 0)
            now = int(time.time())
            if exp and exp < now:
                return False, f"jwtToken 已过期 (过期时间: {datetime.fromtimestamp(exp)})"

        return True, "Cookie 格式正确"

    def log(self, msg):
        fn_print(msg)
        self.summary["messages"].append(msg)

    def debug_print(self, msg):
        if DEBUG:
            fn_print(f"[DEBUG] {msg}")

    async def query_sign_in_status(self):
        """查询签到状态"""
        try:
            url = "https://m.mcloud.139.com/ycloud/signin/page/infoV3?client=app"
            self.debug_print(f"请求: {url}")
            self.debug_print(f"Headers: {json.dumps(self.auth_headers, ensure_ascii=False)[:200]}...")
            self.debug_print(f"Cookies keys: {list(self.cookies_dict.keys())}")

            response = await self.client.get(
                url=url,
                headers=self.auth_headers,
                cookies=self.cookies_dict
            )

            self.debug_print(f"响应状态: {response.status_code}")
            self.debug_print(f"响应内容: {response.text[:500]}")

            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    result = data.get("result", {})
                    cal = result.get("cal", [])
                    today = datetime.now().day
                    today_signed = False
                    today_clouds = 0

                    for day_info in cal:
                        if day_info.get("d") == today and day_info.get("currentMonth") == 1:
                            today_signed = day_info.get("s", False)
                            today_clouds = day_info.get("n", 0)
                            break

                    sign_count = result.get("signCount", 0)
                    total = result.get("total", 0)
                    self.summary["clouds"] = total

                    if today_signed:
                        self.summary["signed"] = True
                        self.log(f"✅ 今日已签到 | 连续{sign_count}天 | 云朵{total}个 | 今日+{today_clouds}")
                    else:
                        self.log(f"📝 今日未签到，尝试签到...")
                        await self.sign_in()
                else:
                    msg = data.get('msg', '未知错误')
                    self.log(f"❌ 查询签到状态失败：{msg}")
                    if "登录" in str(msg) or "未登录" in str(msg):
                        self.log(f"⚠️ Cookie 可能已过期，请重新抓包获取！")
                        self.log(f"⚠️ jwtToken 过期时间: {datetime.fromtimestamp(self.jwt_info.get('exp', 0)) if self.jwt_info.get('exp') else '未知'}")
            else:
                self.log(f"❌ 查询签到状态异常：HTTP {response.status_code}")
        except Exception as e:
            self.log(f"❌ 查询签到状态异常：{e}")

    async def sign_in(self):
        """签到"""
        try:
            response = await self.client.post(
                url="https://m.mcloud.139.com/ycloud/signin/page/doTaskPost",
                headers=self.auth_headers,
                cookies=self.cookies_dict,
                json={"client": "app", "deviceId": self.device_id}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    self.summary["signed"] = True
                    self.log(f"✅ 签到成功！")
                else:
                    self.log(f"⚠️ 签到结果：{data.get('msg')}")
            else:
                self.log(f"❌ 签到异常：HTTP {response.status_code}")
        except Exception as e:
            self.log(f"❌ 签到异常：{e}")

    async def get_task_list(self, group="day"):
        """获取任务列表"""
        try:
            response = await self.client.post(
                url="https://m.mcloud.139.com/ycloud/signin/task/taskListV2",
                headers=self.auth_headers,
                cookies=self.cookies_dict,
                json={
                    "marketname": "sign_in_3",
                    "clientVersion": "13.0.1",
                    "group": group
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    result = data.get("result", {})

                    group_names = {
                        "day": "📅 每日任务",
                        "month": "📆 每月任务", 
                        "time": "⏰ 限时任务",
                        "cloudEmail": "📧 邮箱任务",
                        "hidden": "🔒 隐藏任务",
                    }

                    group_name = group_names.get(group, group)
                    has_tasks = False

                    for task_type, tasks in result.items():
                        if not tasks:
                            continue
                        has_tasks = True
                        for task in tasks:
                            task_name = task.get("name", "未知任务")
                            task_status = task.get("state", "")
                            task_name = re.sub(r'<[^>]+>', '', task_name)

                            if task_status == "FINISH":
                                self.log(f"  ✅ {task_name}")
                            elif task_status == "WAIT":
                                self.log(f"  📝 {task_name}")
                            else:
                                self.log(f"  ⏳ {task_name} ({task_status})")

                    if not has_tasks:
                        self.log(f"  暂无任务")
                else:
                    self.log(f"❌ 获取任务列表失败：{data.get('msg')}")
            else:
                self.log(f"❌ 获取任务列表异常：HTTP {response.status_code}")
        except Exception as e:
            self.log(f"❌ 获取任务列表异常：{e}")

    async def get_quick_prize(self):
        """获取快捷奖励信息"""
        try:
            response = await self.client.get(
                url="https://m.mcloud.139.com/ycloud/signin/page/getQuickPrizeVo",
                headers=self.auth_headers,
                cookies=self.cookies_dict
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    result = data.get("result", {})
                    is_friday = result.get("isFriday", 0)
                    start_h = result.get("startHour", 10)
                    start_m = result.get("startMinute", 30)
                    end_h = result.get("endHour", 12)
                    end_m = result.get("endMinute", 30)
                    self.log(f"🎁 快捷奖励: {'周五' if is_friday else '非周五'} | {start_h}:{start_m:02d}-{end_h}:{end_m:02d}")
        except Exception as e:
            pass

    async def task_expansion(self):
        """任务扩展/云朵膨胀"""
        try:
            response = await self.client.get(
                url="https://m.mcloud.139.com/ycloud/signin/page/taskExpansion",
                headers=self.auth_headers,
                cookies=self.cookies_dict
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    result = data.get("result", {})
                    cur = result.get("curMonthBackup", False)
                    pre = result.get("preMonthBackup", False)
                    next_m = result.get("nextMonthTaskRecordCount", 0)
                    self.log(f"📈 备份: 本月{'✅' if cur else '❌'} | 上月{'✅' if pre else '❌'} | 下月+{next_m}朵")
        except Exception as e:
            pass

    async def receive_clouds(self):
        """领取云朵"""
        try:
            response = await self.client.get(
                url="https://m.mcloud.139.com/ycloud/signin/page/receive",
                headers=self.auth_headers,
                cookies=self.cookies_dict
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("code") == 0:
                    result = data.get("result", {})
                    receive = result.get("receive", 0)
                    total = result.get("total", 0)
                    self.summary["clouds"] = total
                    self.log(f"☁️ 云朵: 待领{receive}朵 | 总计{total}朵")
                else:
                    self.log(f"☁️ 云朵: {data.get('msg')}")
        except Exception as e:
            pass

    async def get_pop_info(self):
        """获取弹窗信息"""
        try:
            response = await self.client.post(
                url="https://m.mcloud.139.com/ycloud/signin/public/getPopInfo",
                headers=self.auth_headers,
                cookies=self.cookies_dict,
                json={"clientType": "iphone", "version": "13.0.1"}
            )
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                if result.get("showPop"):
                    self.log(f"🎉 有弹窗奖励！")
        except Exception as e:
            pass

    async def popup_check(self):
        """检查弹窗"""
        try:
            response = await self.client.get(
                url="https://m.mcloud.139.com/ycloud/signin/page/popup",
                headers=self.auth_headers,
                cookies=self.cookies_dict
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("result"):
                    self.log(f"🎈 有弹窗")
        except:
            pass

    async def journaling(self, module, optkeyword, sourceid="1002"):
        """上报访问日志"""
        try:
            await self.client.post(
                url="https://m.mcloud.139.com/ycloud/visitlog/journaling",
                headers=self.auth_headers,
                cookies=self.cookies_dict,
                data={
                    "module": module,
                    "optkeyword": optkeyword,
                    "sourceid": sourceid,
                    "marketName": "sign_in_3"
                }
            )
        except:
            pass

    async def run(self):
        """主执行流程"""
        self.log(f"\n{'='*60}")
        self.log(f"📱 用户【{self.encrypt_account}】")

        # Cookie 验证
        valid, msg = self.cookie_valid if isinstance(self.cookie_valid, tuple) else (True, "")
        if not valid:
            self.log(f"❌ {msg}")
            self.log(f"⚠️ 请检查环境变量 ydyp_ck 是否正确设置")
            self.log(f"{'='*60}\n")
            return self.summary

        self.log(f"✅ Cookie 验证通过")
        if self.jwt_info.get('exp'):
            exp_time = datetime.fromtimestamp(self.jwt_info['exp'])
            self.log(f"⏰ Token 过期时间: {exp_time.strftime('%Y-%m-%d %H:%M:%S')}")

        self.log(f"{'='*60}")

        await self.journaling("uservisit", "newsignin_index_client")

        self.log(f"\n📋 签到状态")
        await self.query_sign_in_status()

        self.log(f"\n🎈 弹窗检查")
        await self.get_pop_info()
        await self.popup_check()

        self.log(f"\n🎁 快捷奖励")
        await self.get_quick_prize()

        self.log(f"\n📅 每日任务")
        await self.get_task_list("day")

        self.log(f"\n📆 每月任务")
        await self.get_task_list("month")

        self.log(f"\n⏰ 限时任务")
        await self.get_task_list("time")

        self.log(f"\n📧 邮箱任务")
        await self.get_task_list("cloudEmail")

        self.log(f"\n📈 备份膨胀")
        await self.task_expansion()

        self.log(f"\n☁️ 云朵领取")
        await self.receive_clouds()

        await self.journaling("uservisit", "newsignin_index_receive_type")

        self.log(f"\n{'='*60}")
        self.log(f"✅ 用户【{self.encrypt_account}】完成 | 签到{'✅' if self.summary['signed'] else '❌'} | 云朵{self.summary['clouds']}朵")
        self.log(f"{'='*60}\n")

        return self.summary


async def main():
    if not ydyp_ck or ydyp_ck == ['']:
        fn_print("❌ 未配置环境变量 ydyp_ck")
        fn_print("")
        fn_print("📖 格式: 完整的 Cookie 字符串")
        fn_print("📖 获取方式: Surge/Charles 抓包移动云盘 App 的签到页面")
        fn_print("📖 多账号用 @ 分隔")
        fn_print("")
        fn_print("🔍 调试模式: 设置环境变量 ydyp_debug=true 可查看详细请求信息")
        return

    all_summaries = []
    for i, ck in enumerate(ydyp_ck):
        if ck.strip():
            try:
                fn_print(f"\n🚀 开始执行第 {i+1} 个账号...")
                disk = MobileCloudDisk(ck.strip())
                summary = await disk.run()
                all_summaries.append(summary)
            except Exception as e:
                fn_print(f"❌ 第 {i+1} 个账号执行异常：{e}")
                import traceback
                if DEBUG:
                    traceback.print_exc()

    # 汇总
    fn_print(f"\n{'='*60}")
    fn_print(f"📊 执行汇总 (共{len(all_summaries)}个账号)")
    fn_print(f"{'='*60}")
    for s in all_summaries:
        fn_print(f"  👤 {s['account']}: 签到{'✅' if s['signed'] else '❌'} | 云朵{s['clouds']}朵")

    # 通知
    try:
        msg = f"中国移动云盘签到 - {datetime.now().strftime('%Y/%m/%d')}\n"
        for s in all_summaries:
            msg += f"\n{s['account']}: 签到{'✅' if s['signed'] else '❌'} | 云朵{s['clouds']}朵"
        send_notification_message_collection(msg)
    except Exception as e:
        print(f"通知发送失败：{e}")


if __name__ == '__main__':
    asyncio.run(main())
