"""
哔哩哔哩动态缓存管理模块
作者: 艾
基于 AutoDownBUPDynamic 项目开发

功能说明:
- 提供缓存状态管理
- 监控UP主动态更新
- 管理下载任务和存储空间
- 提供日志记录功能
- 支持多线程监控

主要特性:
1. 实时状态监控和统计
2. 存储空间使用情况跟踪
3. 线程安全的日志记录
4. 可配置的监控间隔
5. 优雅的启动和停止机制
"""

import os
import json
import time
import requests
import subprocess
import threading
from datetime import datetime

class BilibiliCache:
    """
    哔哩哔哩动态缓存管理类
    
    负责：
    - 配置文件的加载和管理
    - 动态监控任务的控制
    - 缓存状态统计
    - 日志记录和管理
    - 存储空间监控
    """
    def __init__(self, config_path='static/config.json'):
        """
        初始化缓存管理对象
        
        Args:
            config_path: 配置文件路径，默认为'static/config.json'
            
        初始化内容：
        - 加载配置文件
        - 设置运行状态标志
        - 初始化日志列表
        - 设置缓存统计变量
        - 设置存储空间限制
        """
        self.config_path = config_path
        self.load_config()
        self.running = False          # 运行状态标志
        self.logs = []                # 日志记录列表
        self.cached_video_count = 0   # 已缓存视频数量
        self.used_storage = 0         # 已使用存储空间（字节）
        self.max_storage = 100 * 1024 * 1024 * 1024  # 最大存储空间（100GB）
        
    def load_config(self):
        """
        加载配置文件
        
        从指定路径读取JSON格式的配置文件
        """
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
    
    def add_log(self, message, log_type='info'):
        """
        添加日志记录
        
        Args:
            message: 日志消息内容
            log_type: 日志类型（'info', 'error', 'warning', 'success'）
            
        功能：
        1. 添加时间戳
        2. 创建日志条目
        3. 添加到日志列表
        4. 限制日志数量（最多1000条）
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = {
            'time': timestamp,
            'message': message,
            'type': log_type
        }
        self.logs.append(log_entry)
        
        # 保持日志列表不超过1000条，避免内存占用过大
        if len(self.logs) > 1000:
            self.logs.pop(0)  # 移除最旧的日志
    
    def get_dynamic(self, uid):
        """
        获取指定UP主的动态列表
        
        Args:
            uid: UP主的用户ID
            
        Returns:
            list: 动态列表，如果获取失败返回None
            
        功能：
        1. 构建API请求URL
        2. 设置请求头（包含认证信息）
        3. 发送HTTP请求获取动态数据
        4. 解析响应数据
        5. 错误处理和日志记录
        """
        url = f'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space?host_mid={uid}'
        headers = {
            **self.config['headers'],
            'Cookie': '; '.join([f'{k}={v}' for k, v in self.config['Cookies'].items()])
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data['code'] == 0:
                    return data['data']['items']
            return None
        except Exception as e:
            self.add_log(f'获取动态失败: {str(e)}', 'error')
            return None
    
    def download_video(self, bvid):
        """
        下载视频（模拟实现）
        
        Args:
            bvid: 视频的BV号
            
        Returns:
            bool: 下载是否成功
            
        功能：
        1. 记录下载开始日志
        2. 模拟下载过程（实际应调用真实的下载逻辑）
        3. 更新缓存统计信息
        4. 记录下载完成日志
        """
        self.add_log(f'开始下载视频: {bvid}', 'info')
        time.sleep(5)  # 模拟下载时间
        
        # 更新缓存统计信息
        self.cached_video_count += 1
        # 假设每个视频平均大小为500MB
        self.used_storage += 500 * 1024 * 1024
        self.add_log(f'视频下载完成: {bvid} (缓存视频数: {self.cached_video_count})', 'success')
        return True
    
    def update_status(self):
        """
        更新并返回当前状态信息
        
        Returns:
            dict: 包含运行状态、缓存统计、存储使用等信息的字典
            
        返回信息包括：
        - 运行状态
        - 已缓存视频数量
        - 已使用存储空间
        - 最大存储空间
        - 磁盘使用百分比
        - 最后运行时间
        """
        # 计算磁盘使用百分比
        disk_percent = (self.used_storage / self.max_storage * 100) if self.max_storage > 0 else 0
        
        return {
            'is_running': self.running,
            'cached_video_count': self.cached_video_count,
            'used_storage': self.format_size(self.used_storage),
            'max_storage': self.format_size(self.max_storage),
            'disk_percent': round(disk_percent, 1),
            'last_run_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def format_size(self, size_bytes):
        """
        格式化存储大小显示
        
        Args:
            size_bytes: 字节数
            
        Returns:
            str: 格式化后的大小字符串（如 "1.5 GB"）
            
        自动选择合适的单位：B, KB, MB, GB, TB
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    def start_dynamic_monitor(self):
        """启动动态监控线程"""
        if not self.running:
            self.running = True
            self.add_log('自动缓存任务启动', 'info')
            
            # 启动监控线程
            self.monitor_thread = threading.Thread(target=self.monitor_dynamics)
            self.monitor_thread.daemon = True
            self.monitor_thread.start()
    
    def stop_dynamic_monitor(self):
        """停止动态监控"""
        if self.running:
            self.running = False
            self.add_log('自动缓存任务停止', 'warning')
    
    def toggle_running(self):
        """切换运行状态"""
        if self.running:
            self.stop_dynamic_monitor()
        else:
            self.start_dynamic_monitor()
    
    def monitor_dynamics(self):
        """监控UP主动态"""
        while self.running:
            try:
                for uid in self.config['bupid']:
                    if not self.running:
                        break
                    
                    self.add_log(f'检查UP主 {uid} 的动态...', 'info')
                    items = self.get_dynamic(uid)
                    
                    if items:
                        # 处理最新动态
                        for item in items[:3]:
                            if not self.running:
                                break
                            
                            if item['type'] == 'DYNAMIC_TYPE_AV':
                                bvid = item['modules']['module_dynamic']['major']['archive']['bvid']
                                self.download_video(bvid)
                
                # 等待间隔
                time.sleep(self.config['interval-sec'])
            except Exception as e:
                self.add_log(f'监控出错: {str(e)}', 'error')
                time.sleep(10)  # 出错后等待10秒再重试

# 启动Dynamic.py的辅助函数
def start_dynamic_monitor():
    """启动动态监控程序"""
    try:
        # 确保同目录下有Dynamic.py
        if os.path.exists('Dynamic.py'):
            # 启动新进程运行Dynamic.py
            subprocess.Popen(['python', 'Dynamic.py'])
            return True
        return False
    except Exception as e:
        print(f'启动Dynamic.py失败: {str(e)}')
        return False

# 示例用法
if __name__ == '__main__':
    cache = BilibiliCache()
    
    # 启动监控
    cache.start_dynamic_monitor()
    
    try:
        # 模拟运行一段时间
        time.sleep(30)
    finally:
        # 停止监控
        cache.stop_dynamic_monitor()