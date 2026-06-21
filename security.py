#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""尚唯云册 - 安全访问控制
实现局域网/广域网权限分离
"""

import os
import re
import json
from datetime import datetime
from typing import Dict, List, Optional


class AccessControl:
    """访问控制器"""
    
    # 局域网 IP 范围
    LAN_RANGES = [
        '192.168.',    # 192.168.0.0/16
        '10.',         # 10.0.0.0/8
        '172.16.',     # 172.16.0.0/12
        '172.17.',
        '172.18.',
        '172.19.',
        '172.20.',
        '172.21.',
        '172.22.',
        '172.23.',
        '172.24.',
        '172.25.',
        '172.26.',
        '172.27.',
        '172.28.',
        '172.29.',
        '172.30.',
        '172.31.',
        '127.0.0.1',   # 本地回环
        'localhost',
        '::1',         # IPv6 本地回环
    ]
    
    # 私密相册关键词（需要权限才能访问）
    PRIVATE_KEYWORDS = [
        '证件', '身份证', '护照', '驾照',
        '医疗', '病历', '诊断',
        '合同', '协议', '机密',
        '密码', '账号',
    ]
    
    def __init__(self):
        self.access_log = []
        self.blocked_ips = set()
    
    def is_lan_ip(self, ip: str) -> bool:
        """判断是否为局域网 IP"""
        if not ip:
            return False
        
        # 清理 IP（移除端口）
        ip = ip.split(':')[0]
        
        # 检查是否在局域网范围
        for prefix in self.LAN_RANGES:
            if ip.startswith(prefix):
                return True
        
        return False
    
    def is_private_album(self, album_name: str) -> bool:
        """判断是否为私密相册"""
        album_lower = album_name.lower()
        
        for keyword in self.PRIVATE_KEYWORDS:
            if keyword in album_lower:
                return True
        
        return False
    
    def check_access(self, ip: str, path: str, user_agent: str = '') -> Dict:
        """
        检查访问权限
        
        返回：
            {
                'allowed': bool,
                'reason': str,
                'is_lan': bool,
                'is_private': bool
            }
        """
        is_lan = self.is_lan_ip(ip)
        
        # 检查是否被封锁
        if ip in self.blocked_ips:
            return {
                'allowed': False,
                'reason': 'IP已被封锁',
                'is_lan': is_lan,
                'is_private': False
            }
        
        # 检查私密内容
        is_private = self.is_private_album(path)
        
        # 广域网访问私密内容 → 拒绝
        if not is_lan and is_private:
            self._log_access(ip, path, False, '广域网访问私密内容')
            return {
                'allowed': False,
                'reason': '广域网禁止访问私密内容',
                'is_lan': is_lan,
                'is_private': is_private
            }
        
        # 允许访问
        self._log_access(ip, path, True, '正常访问')
        return {
            'allowed': True,
            'reason': '允许访问',
            'is_lan': is_lan,
            'is_private': is_private
        }
    
    def _log_access(self, ip: str, path: str, allowed: bool, reason: str):
        """记录访问日志"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'ip': ip,
            'path': path,
            'allowed': allowed,
            'reason': reason,
            'is_lan': self.is_lan_ip(ip)
        }
        
        self.access_log.append(log_entry)
        
        # 保持日志不超过 1000 条
        if len(self.access_log) > 1000:
            self.access_log = self.access_log[-1000:]
    
    def block_ip(self, ip: str, reason: str = ''):
        """封锁 IP"""
        self.blocked_ips.add(ip)
        self._log_access(ip, '', False, f'IP已封锁: {reason}')
    
    def unblock_ip(self, ip: str):
        """解封 IP"""
        self.blocked_ips.discard(ip)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.access_log)
        allowed = sum(1 for log in self.access_log if log['allowed'])
        blocked = total - allowed
        lan_count = sum(1 for log in self.access_log if log['is_lan'])
        wan_count = total - lan_count
        
        return {
            'total_access': total,
            'allowed': allowed,
            'blocked': blocked,
            'lan_access': lan_count,
            'wan_access': wan_count,
            'blocked_ips': list(self.blocked_ips)
        }
    
    def get_recent_logs(self, count: int = 20) -> List[Dict]:
        """获取最近的访问日志"""
        return self.access_log[-count:] if self.access_log else []


class GatewaySecurity:
    """Gateway 安全中间件"""
    
    def __init__(self):
        self.acl = AccessControl()
        self.rate_limit = {}  # IP → 请求次数
    
    def check_request(self, client_ip: str, path: str) -> Dict:
        """检查请求"""
        # 速率限制（防止恶意爬虫）
        if not self._check_rate_limit(client_ip):
            return {
                'allowed': False,
                'reason': '请求过于频繁，请稍后再试',
                'status_code': 429
            }
        
        # 访问控制
        result = self.acl.check_access(client_ip, path)
        
        if not result['allowed']:
            return {
                'allowed': False,
                'reason': result['reason'],
                'status_code': 403
            }
        
        return {
            'allowed': True,
            'status_code': 200
        }
    
    def _check_rate_limit(self, ip: str, max_requests: int = 100) -> bool:
        """检查速率限制"""
        now = datetime.now().timestamp()
        
        # 清理过期记录（1分钟前）
        self.rate_limit = {
            k: v for k, v in self.rate_limit.items()
            if now - v['first_seen'] < 60
        }
        
        # 检查当前 IP
        if ip not in self.rate_limit:
            self.rate_limit[ip] = {
                'count': 1,
                'first_seen': now
            }
            return True
        
        self.rate_limit[ip]['count'] += 1
        
        return self.rate_limit[ip]['count'] <= max_requests
    
    def get_security_report(self) -> Dict:
        """生成安全报告"""
        stats = self.acl.get_stats()
        
        return {
            'access_control': stats,
            'rate_limited_ips': [
                ip for ip, data in self.rate_limit.items()
                if data['count'] > 50
            ]
        }


# 测试
if __name__ == '__main__':
    acl = AccessControl()
    
    print("=" * 60)
    print("访问控制测试")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        ('192.168.0.10', '/album/生活照'),
        ('192.168.0.10', '/album/证件照'),
        ('8.8.8.8', '/album/生活照'),
        ('8.8.8.8', '/album/证件照'),
        ('127.0.0.1', '/album/证件照'),
    ]
    
    for ip, path in test_cases:
        result = acl.check_access(ip, path)
        status = "✓ 允许" if result['allowed'] else "✗ 拒绝"
        print(f"\nIP: {ip:15} 路径: {path}")
        print(f"  结果: {status}")
        print(f"  原因: {result['reason']}")
        print(f"  局域网: {'是' if result['is_lan'] else '否'}")
        print(f"  私密: {'是' if result['is_private'] else '否'}")
    
    print("\n" + "=" * 60)
    print("统计信息:")
    stats = acl.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("=" * 60)
