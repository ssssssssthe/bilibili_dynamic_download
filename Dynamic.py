"""
哔哩哔哩动态自动缓存核心程序
作者: 艾
基于 AutoDownBUPDynamic 项目开发

功能说明:
- 自动监控指定UP主的动态更新
- 下载动态中的图片和视频
- 支持自动评论功能
- 文件整理和移动功能
- 日志记录和管理

主要特性:
1. 自动检测登录状态和Cookie有效性
2. 支持二维码扫码登录
3. 智能重试机制和错误处理
4. 文件去重和命名规范化
5. 视频音频合并处理
"""

import tkinter as tk
from tkinter import messagebox
import pyqrcode
import requests
import requests.utils
import os
import time
import subprocess
import json
import csv
import sys
import urllib3
import shutil
import glob
from bs4 import BeautifulSoup
from datetime import datetime

# 尝试导入lxml解析器，如果失败则使用默认解析器
try:
    import lxml.etree as etree
except ImportError:
    etree = None

# 导入重试机制相关模块
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# 禁用urllib3的SSL警告
urllib3.disable_warnings()

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

# 确定程序运行的基础目录
if getattr(sys, 'frozen', False):
    # 如果是exe环境，使用exe所在目录
    BASEDIR = os.path.dirname(sys.executable)
else:
    # 如果是开发环境，使用脚本所在目录
    BASEDIR = os.path.dirname(os.path.realpath(sys.argv[0]))

# 获取系统文件编码
sys_encoding = sys.getfilesystemencoding()
print(f"基础目录: {BASEDIR}")

class Dynamic:
    """
    哔哩哔哩动态自动缓存核心类
    
    负责：
    - 配置管理和加载
    - 登录状态验证
    - 动态数据获取和处理
    - 文件下载和管理
    - 日志记录
    """
    
    # 全局配置字典
    CONFIG = {}
    
    # 动态数据标准格式
    datajson = {
        'id': '',           # 动态ID
        'aid': '',          # 视频AID
        'comment_type': '', # 评论类型
        'type': '',         # 动态类型
        'title': '',        # 标题
        'text': '',         # 文本内容
        'imagepath': [],    # 图片路径列表
        'videopath': ''     # 视频路径
    }

    def main(self):
        """
        程序主入口方法
        
        执行流程：
        1. 初始化配置和登录状态
        2. 开始监控循环
        """
        self.init()
        self.start()

    def setconfig(self):
        """
        保存配置到文件
        
        将当前配置字典保存到static/config.json文件中
        """
        with open(BASEDIR+'/static/config.json', 'w', encoding='utf-8') as f:
            json.dump(self.CONFIG, f, ensure_ascii=False, indent=4)

    def check_cookie_valid(self):
        """检测当前cookie是否有效"""
        try:
            # 首先检查SESSDATA是否为空
            cookies = self.CONFIG.get('Cookies', {})
            sessdata = cookies.get('SESSDATA', '')
            if not sessdata or sessdata.strip() == '':
                self.log("SESSDATA为空，需要重新登录")
                return False
            
            # 检查refresh_token是否为空
            refresh_token = self.CONFIG.get('refresh_token', '')
            if not refresh_token or refresh_token.strip() == '':
                self.log("refresh_token为空，需要重新登录")
                return False
            
            # 检查API登录状态
            self.sess.headers = self.CONFIG['headers']
            self.sess.cookies = requests.utils.cookiejar_from_dict(cookies)
            resp = self.sess.get('https://api.bilibili.com/x/web-interface/nav', timeout=10)
            data = resp.json()
            
            is_login = data.get('data', {}).get('isLogin', False)
            if not is_login:
                self.log("API返回未登录状态")
                return False
            
            self.log("Cookie验证通过")
            return True
            
        except Exception as e:
            self.log(f"检测cookie有效性失败: {e}")
            return False

    def show_qrcode_window(self, qrcode_path):
        """弹出二维码窗口，扫码成功前不能关闭"""
        root = tk.Tk()
        root.title("请使用B站App扫码登录")
        root.geometry("350x400")
        root.resizable(False, False)
        label = tk.Label(root, text="请使用B站App扫码登录", font=("Microsoft YaHei", 12))
        label.pack(pady=10)
        img = tk.PhotoImage(file=qrcode_path)
        img_label = tk.Label(root, image=img)
        img_label.pack(pady=10)
        status_var = tk.StringVar(value="等待扫码...")
        status_label = tk.Label(root, textvariable=status_var, font=("Microsoft YaHei", 10))
        status_label.pack(pady=10)
        # 禁止关闭窗口
        root.protocol("WM_DELETE_WINDOW", lambda: None)
        return root, status_var

    def init(self):
        """
        初始化方法
        
        执行以下初始化操作：
        1. 加载配置文件
        2. 设置数据目录
        3. 验证登录状态
        4. 初始化UP主动态列表
        5. 配置网络请求参数
        6. 设置重试机制
        """
        # 初始化成员变量
        self.dyidlist = {}      # 存储UP主动态ID列表
        self.dir_path = BASEDIR # 数据存储目录
        self.sess = requests.Session()  # 创建会话对象
        
        # 加载配置文件
        json_path = os.path.join(BASEDIR, "static/config.json")
        with open(json_path, 'r', encoding='utf-8') as jf:
            self.CONFIG = json.load(jf)
        
        # 初始化评论状态（刚开始运行不评论，只有检测到更新时才评论）
        self.iscomment = False

        # 设置数据目录
        if (self.CONFIG['datadir'] != ''):
            self.dir_path = self.CONFIG['datadir']
            # 如果目录不存在，则创建目录
            if not os.path.exists(self.dir_path): 
                os.makedirs(self.dir_path)

        # 设置请求头
        self.log(self.CONFIG['headers'])
        self.sess.headers = self.CONFIG['headers']
        
        # 检查cookie有效性
        if not self.check_cookie_valid():
            self.log("Cookie无效或未设置，需扫码登录")
            self.login()
            # 登录后再次设置cookie
            self.sess.cookies = requests.utils.cookiejar_from_dict(self.CONFIG.get('Cookies', {}))
            if not self.check_cookie_valid():
                self.log("扫码登录失败，请重启程序")
                sys.exit(1)
        else:
            self.log("Cookie有效，已自动登录")
        
        # 初始化UP主动态列表
        self.log(self.CONFIG)
        for up in self.CONFIG['bupid']:
            self.updylist(up)
        
        # 配置重试机制
        retry_strategy = Retry(
            total=3,                    # 最大重试次数
            backoff_factor=1,           # 重试间隔因子
            status_forcelist=[429, 500, 502, 503, 504]  # 需要重试的HTTP状态码
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.sess.mount("https://", adapter)
        self.sess.mount("http://", adapter)
        
        # 更新请求头信息
        self.sess.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
            "Connection": "keep-alive"
        })
        
        # 设置默认配置项
        if 'final_dir' not in self.CONFIG:
            self.CONFIG['final_dir'] = ''
        if 'move_after_combine' not in self.CONFIG:
            self.CONFIG['move_after_combine'] = False


# 登陆方法

    def login(self):
        """扫码登录，扫码成功前阻塞"""
        cook = {}
        # 获取二维码
        rep = self.sess.get('https://passport.bilibili.com/x/passport-login/web/qrcode/generate')
        rep_json = rep.json()
        qrcode_url = rep_json['data']['url']
        token = rep_json['data']['qrcode_key']
        qrcode_path = os.path.join(BASEDIR, 'qrcode.png')
        pyqrcode.create(qrcode_url).png(qrcode_path, scale=8)
        # 弹窗显示二维码
        root, status_var = self.show_qrcode_window(qrcode_path)
        def poll():
            while True:
                try:
                    rst = self.sess.get(f'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={token}')
                    j = rst.json()
                    code = j['data']['code']
                    if code == 0:
                        status_var.set("扫码成功，正在登录...")
                        self.log('登录成功')
                        self.CONFIG['refresh_token'] = j['data']['refresh_token']
                        for co in rst.cookies:
                            cook[co.name] = co.value
                        self.CONFIG['Cookies'] = cook
                        self.setconfig()
                        try:
                            os.remove(qrcode_path)
                        except Exception:
                            pass
                        root.destroy()
                        return True
                    elif code == 86038:
                        status_var.set("二维码已失效，请重启程序")
                        time.sleep(2)
                        continue
                    elif code == 86090:
                        status_var.set("等待扫码...")
                    elif code == 86101:
                        status_var.set("已扫码，等待确认...")
                    else:
                        status_var.set(f"未知状态: {code}")
                except Exception as e:
                    status_var.set(f"网络错误: {e}")
                time.sleep(2)
        import threading
        t = threading.Thread(target=poll, daemon=True)
        t.start()
        root.mainloop()










    def start(self):
        """
        开始监控循环
        
        主要功能：
        1. 定期检查日志清理
        2. 轮询所有UP主的动态更新
        3. 处理新动态的下载和评论
        4. 按配置间隔休眠
        
        循环流程：
        1. 检查是否需要清理日志
        2. 遍历所有UP主ID
        3. 获取每个UP主的最新动态
        4. 处理新动态（下载、评论等）
        5. 休眠指定时间间隔
        """
        last_clean_time = datetime.now()  # 记录上次日志清理时间
        
        while True:
            current_time = datetime.now()
            
            # 检查是否达到清空日志的时间间隔
            if self.should_clean_log(current_time, last_clean_time):
                self.clean_log()
                last_clean_time = current_time

            # 遍历所有配置的UP主ID
            for upid in self.CONFIG['bupid']:
                self.getdata(upid=upid)  # 获取UP主动态数据
                time.sleep(5)  # 每个UP主之间间隔5秒

            # 首次运行后启用自动评论功能
            if not self.iscomment:
                self.iscomment = True
                self.log('up id列表已更新 + 开始自动评论')
                self.CONFIG['down-atfirst'] = self.CONFIG['autodownload']
            
            # 按配置的间隔时间休眠
            time.sleep(self.CONFIG['interval-sec'])
    
    def should_clean_log(self, current_time, last_clean_time):
        """判断是否应该清理日志"""
        log_path = os.path.join(BASEDIR, "log.txt")
        
        # 如果日志文件不存在，不需要清理
        if not os.path.exists(log_path):
            return False
        
        # 获取日志文件大小（字节）
        file_size = os.path.getsize(log_path)
        
        # 获取配置中的清理设置
        clean_interval_days = self.CONFIG.get('log_clean_interval_days', 7)  # 默认7天
        max_log_size_mb = self.CONFIG.get('max_log_size_mb', 10)  # 默认10MB
        
        # 检查时间间隔（天数）
        days_since_last_clean = (current_time - last_clean_time).days
        
        # 检查文件大小（MB）
        file_size_mb = file_size / (1024 * 1024)
        
        # 如果超过时间间隔或文件大小限制，则清理
        if days_since_last_clean >= clean_interval_days or file_size_mb >= max_log_size_mb:
            self.log(f"准备清理日志文件 - 大小: {file_size_mb:.2f}MB, 距离上次清理: {days_since_last_clean}天")
            return True
        
        return False
    
    def clean_log(self):
        """清理日志文件"""
        log_path = os.path.join(BASEDIR, "log.txt")
        try:
            if os.path.exists(log_path):
                # 获取文件大小用于记录
                file_size = os.path.getsize(log_path)
                file_size_mb = file_size / (1024 * 1024)
                
                # 备份当前日志（可选）
                if self.CONFIG.get('backup_log_before_clean', False):
                    backup_path = os.path.join(BASEDIR, f"log_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
                    shutil.copy2(log_path, backup_path)
                    self.log(f"日志已备份到: {backup_path}")
                
                # 清空日志文件
                with open(log_path, 'w', encoding='utf-8') as f:
                    f.write('')  # 清空日志文件
                
                self.log(f"日志文件已清空 - 原大小: {file_size_mb:.2f}MB")
                
                # 记录清理信息到新的日志文件
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f'[{datetime.now().strftime("%m/%d %H:%M")}]: 日志文件已清空 - 原大小: {file_size_mb:.2f}MB\n')
                    
        except Exception as e:
            self.log(f"清空日志文件失败: {e}")

    def updylist(self, upid):
        """
        更新UP主动态ID列表
        
        从CSV文件中读取已缓存的动态ID列表，用于判断重复下载
        
        Args:
            upid: UP主ID
            
        功能：
        1. 创建UP主目录下的CSV文件路径
        2. 读取已缓存的动态ID列表
        3. 如果是首次运行，记录日志
        4. 设置首次下载标志
        """
        self.dyidlist[upid] = []  # 初始化UP主的动态ID列表
        file_path = os.path.join(self.dir_path, '{0}/{0}.csv'.format(upid))
        
        try:
            with open(file=file_path, mode='r') as c:
                r = csv.DictReader(c)
                for ro in r:
                    self.dyidlist[upid].append(ro['id'])  # 添加已缓存的动态ID
        except FileNotFoundError:
            self.log('首次运行')  # 首次运行时CSV文件不存在
            return
        
        # 设置首次下载标志
        self.CONFIG['down-atfirst'] = self.CONFIG['autodownload']

    def getdata(self, upid):
        url = 'https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space'
        params = {
            'host_mid': upid,
            'offset': '',  # 分页偏移量
            'page': 1      # 当前页码
        }
        
        try:
            # 添加超时和异常处理
            response = self.sess.get(url=url, params=params, timeout=(10, 30))
            data = response.json()
        except requests.exceptions.RequestException as e:
            self.log(f"请求UP主 {upid} 动态失败: {str(e)}")
            return
    
        has_more = True
        while has_more:
            data = self.sess.get(url=url, params=params, timeout=(10, 30)).json()
            
            # 未成功获取情况
            if data['code'] != 0:
                self.log(data)
                # 刷新下初始数据
                self.init()
                return
            
            # 检查是否有更多数据
            has_more = data['data'].get('has_more', False)
            if 'offset' in data['data']:
                params['offset'] = data['data']['offset']
            
            try:
                dytype = data['data']['items'][0]['modules']['module_tag']['text']
            except KeyError:
                self.log('up[{0}] 无置顶动态'.format(upid))
                dytype = ''
            
            # 如果数据第一条是置顶动态，那么暴力计算前两条是否是更新的
            if dytype == '置顶':
                if (self.dyidlist[upid] != [] and 
                    (data['data']['items'][0]['id_str'] in self.dyidlist[upid] and 
                     data['data']['items'][1]['id_str'] in self.dyidlist[upid])):
                    self.log('====')
                    if not has_more:  # 如果没有更多数据了才返回
                        return
                    continue  # 否则继续获取下一页
            
            # 如果没有更新，且没有更多数据了，则返回
            elif (self.dyidlist[upid] != [] and 
                  data['data']['items'][0]['id_str'] == self.dyidlist[upid][-1]):
                self.log('====')
                if not has_more:
                    return
                continue
            
            self.log(self.dyidlist[upid])
            for item in data['data']['items'][::-1]:
                dali = self.toDynamicData(item)
                try:
                    # 如果该动态已经获取，跳过
                    if dali['id'] in self.dyidlist[upid]:
                        continue
                except Exception:
                    self.log('QAQ')

                self.log('Data= id:{0},text:{1},imagepath:{2},videopath:{3},type:{4}'.format(
                    dali['id'], dali['text'], dali['imagepath'], dali['videopath'], dali['type']))

                csv_path = os.path.join(self.dir_path, '{0}/{0}.csv'.format(upid))
                folder_path = os.path.dirname(csv_path)
                # 如果文件夹不存在，创建文件夹
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                
                try:
                    if not os.path.isfile(csv_path):
                        with open(file=csv_path, mode='a', encoding='gbk', errors='ignore', newline='') as c:
                            w = csv.DictWriter(c, fieldnames=self.datajson.keys(), quoting=csv.QUOTE_ALL)
                            w.writeheader()
                            self.log(dali)
                            w.writerow(dali)
                    else:
                        with open(file=csv_path, mode='a', encoding='gbk', errors='ignore', newline='') as c:
                            csv.DictWriter(c, fieldnames=self.datajson.keys(), quoting=csv.QUOTE_ALL).writerow(dali)
                except PermissionError:
                    self.log('权限不足写入失败，或许其他程序占用')
                
                # 自动评论
                if self.iscomment and self.CONFIG['autocomment'] != '':
                    self.commentaction(dali['comment_type'], dali['aid'])
                # 第一次不缓存则跳过
                if not self.CONFIG['down-atfirst']:
                    continue
                # 设置不自动下载附件则跳过
                if not self.CONFIG['autodownload']:
                    continue
                self.downimage(upid, dali['id'], dali['imagepath'])
                # 新增：非视频动态也移动图片
                if dali['type'] != 'DYNAMIC_TYPE_AV' and self.CONFIG['move_after_combine'] and self.CONFIG['final_dir']:
                    self.move_files(None, upid)  # 只移动图片
                self.downvideo(upid, dali['videopath'])
            
            # 如果没有更多数据了，跳出循环
            if not has_more:
                break
            
            # 短暂延迟，避免请求过于频繁
            time.sleep(5)
        
        # 更新已缓存id列表
        self.updylist(upid)








    def downimage(self,upid,id,path):
        if path == '' : return

        for index,url  in enumerate(path):
            a = str(url).split('.')[-1]
            img_path = os.path.join(self.dir_path, f'{upid}/{id}_00{index+1}.{a}')
            img = self.sess.get(url).content
            with open(img_path,'wb') as file:
                file.write(img)

    def sanitize_filename(self, name):
        # 替换Windows不允许的文件名字符
        import re
        return re.sub(r'[\\/:*?"<>|]', '_', name)

    def get_web_title(self, url, max_retries=3):
        for attempt in range(max_retries):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = self.sess.get(url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string.strip() if soup.title and soup.title.string else "untitled"
                title = title.replace("_哔哩哔哩_bilibili", "").replace("_哔哩哔哩", "").replace("_bilibili", "")
                return title
            except Exception as e:
                if attempt == max_retries - 1:
                    self.log(f"获取标题失败: {e}")
                    return f"untitled_{str(url).split('/')[-2]}"
                time.sleep(2)

    def downvideo(self, upid, url, max_retries=3):
        if not url:
            return False

        # 确保upid和bvid是字符串
        upid = str(upid)
        bvid = url.split('/')[-2]
        web_title = self.get_web_title(url)
        safe_title = self.sanitize_filename(web_title)
        safe_bvid = self.sanitize_filename(bvid)
    
        # Initialize paths early to avoid UnboundLocalError
        video_path = os.path.join(self.dir_path, f'{upid}/{safe_bvid}_video.tmp')
        audio_path = os.path.join(self.dir_path, f'{upid}/{safe_bvid}_audio.tmp')

        for attempt in range(max_retries):
            try:
                self.log(f"[视频 {bvid}] 开始处理 (尝试 {attempt+1}/{max_retries})")
              
                # 获取视频页面（带重试）
                for i in range(3):
                    try:
                        res = self.sess.get(url, timeout=15)
                        res.raise_for_status()
                        break
                    except Exception as e:
                        if i == 2:
                            raise
                        time.sleep(3)
            
               # 解析视频信息 - 更健壮的JSON提取
                if etree is None:
                    raise ValueError("lxml库未安装，无法解析视频信息")
                _element = etree.HTML(res.content)
                script_content = _element.xpath('//head/script[contains(text(),"window.__playinfo__")]/text()')
                if not script_content:
                    raise ValueError("无法找到视频信息")
            
            # 更安全的JSON解析
                script_text = script_content[0].split('=', 1)[1].strip()
                if script_text.endswith(';'):
                    script_text = script_text[:-1]
            
                try:
                    video_json = json.loads(script_text)
                except json.JSONDecodeError as e:
                # 尝试修复常见的JSON问题
                    try:
                        script_text = script_text.replace('\n', '\\n').replace('\r', '\\r')
                        video_json = json.loads(script_text)
                    except:
                        raise ValueError(f"JSON解析失败: {str(e)}")

                try:
                    video_url = video_json['data']['dash']['video'][0]['baseUrl']
                    audio_url = video_json['data']['dash']['audio'][0]['baseUrl']
                except KeyError:
                    raise ValueError("无法解析视频/音频地址")

            # 准备目录
                os.makedirs(os.path.join(self.dir_path, upid), exist_ok=True)
            
            # 下载视频和音频
                if not self.downfile(url, video_url, video_path, max_retries=3):
                    raise RuntimeError("视频流下载失败")
            
                if not self.downfile(url, audio_url, audio_path, max_retries=3):
                    raise RuntimeError("音频流下载失败")

            # 合并文件
                final_path = os.path.join(self.dir_path, f'{upid}/{safe_title}_{safe_bvid}.mp4')
                self.combineVideoAudio(video_path, audio_path, final_path, safe_bvid)
            
                return True
            except Exception as e:
                self.log(f"[视频 {bvid}] 处理失败: {str(e)}")
                # 清理可能不完整的临时文件
                for f in [video_path, audio_path]:
                    if os.path.exists(f):
                        try:
                            os.remove(f)
                        except (OSError, PermissionError):
                            pass
                if attempt < max_retries - 1:
                    wait_time = min(10 * (attempt + 1), 60)
                    self.log(f"等待 {wait_time} 秒后重试...（将重新下载）")
                    time.sleep(wait_time)
                    continue
                else:
                    self.log(f"[视频 {bvid}] 处理最终失败，已放弃")
                    return False
        return False

    def combineVideoAudio(self, videopath, audiopath, outpath, bvid):
        try:
            dir = BASEDIR[0].upper() + BASEDIR[1:]
            dir = dir.replace("\\","/")
        
            # 确保输出目录存在
            os.makedirs(os.path.dirname(outpath), exist_ok=True)
        
            # 检查文件是否存在
            if not os.path.exists(videopath) or not os.path.exists(audiopath):
                raise Exception("音视频文件不存在")
        
            # 执行ffmpeg命令
            cmd = f'"{dir}/ffmpeg/bin/ffmpeg.exe" -y -i "{videopath}" -i "{audiopath}" -c copy "{outpath}"'
            result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
            if result.returncode != 0 or not os.path.exists(outpath):
                # 合并失败，清理临时文件
                self.log(f"FFmpeg错误: {result.stderr.decode('gbk') if result.stderr else '未知错误'}")
                try:
                    if os.path.exists(videopath): os.remove(videopath)
                    if os.path.exists(audiopath): os.remove(audiopath)
                except Exception as e:
                    self.log(f"合并失败时清理临时文件失败: {e}")
                raise Exception("合并音视频失败")
        
            self.log(f"视频合并成功: {bvid}")
        
            # 清理临时文件
            try:
                os.remove(videopath)
                os.remove(audiopath)
            except Exception as e:
                self.log(f"清理临时文件失败: {e}")
            
            # 合并成功后移动文件
            if self.CONFIG['move_after_combine'] and self.CONFIG['final_dir']:
                # 只有合并成功且目标文件存在才移动
                if os.path.exists(outpath):
                    dir_path, filename = os.path.split(outpath)
                    dyid = os.path.basename(dir_path)  # 获取upid目录名
                    self.move_files(outpath, dyid)  # 传入动态ID
                else:
                    self.log(f"合并后未找到目标文件: {outpath}，不执行移动")
        
        except Exception as e:
            self.log(f"合并音视频失败: {e}")
            # 合并失败时清理临时文件
            try:
                if os.path.exists(videopath): os.remove(videopath)
                if os.path.exists(audiopath): os.remove(audiopath)
            except Exception as e2:
                self.log(f"合并失败时清理临时文件失败: {e2}")
            raise

    def move_files(self, video_path, upid):
        try:
            final_dir = self.CONFIG['final_dir']
            if not final_dir:
                return
            # 只移动存在的文件
            if video_path and not os.path.exists(video_path):
                self.log(f"待移动文件不存在: {video_path}")
            elif video_path:
                # Create upid subdirectory in final_dir
                upid_dir = os.path.join(final_dir, str(upid))
                if not os.path.exists(upid_dir):
                    os.makedirs(upid_dir)
                # Move video file
                video_name = os.path.basename(video_path)
                dest_video = os.path.join(upid_dir, video_name)
                shutil.move(video_path, dest_video)
                self.log(f"视频已移动到: {dest_video}")
            # Move image files - using upid to find the source directory
            img_dir = os.path.join(self.dir_path, str(upid))
            img_pattern = os.path.join(img_dir, "*.jpg")  # Match all images
            for img_file in glob.glob(img_pattern):
                img_name = os.path.basename(img_file)
                dest_img = os.path.join(final_dir, str(upid), img_name)
                shutil.move(img_file, dest_img)
                self.log(f"图片已移动: {img_file} -> {dest_img}")
        except Exception as e:
            self.log(f"移动文件失败: {e}")

    def downfile(self, homeurl, url, filepath, session=None, max_retries=5, timeout=60):
        if session is None:
            session = self.sess
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Referer': homeurl
        }
    
        for attempt in range(max_retries):
            downloaded = 0
            try:
                # 断点续传检查
                if os.path.exists(filepath):
                    downloaded = os.path.getsize(filepath)
                    headers['Range'] = f'bytes={downloaded}-'
            
                with session.get(
                    url,
                    headers=headers,
                    stream=True,
                    timeout=(timeout, timeout*2)  # 连接超时和读取超时
                ) as response:
                    response.raise_for_status()
                 
                    total_size = int(response.headers.get('content-length', 0)) + downloaded
                    mode = 'ab' if downloaded else 'wb'
                
                    with open(filepath, mode) as f:
                        for chunk in response.iter_content(chunk_size=1024*1024):  # 1MB chunks
                            if chunk:  # 过滤keep-alive chunks
                                f.write(chunk)
                                downloaded += len(chunk)
            
                # 验证文件完整性
                if total_size > 0 and os.path.getsize(filepath) != total_size:
                    raise ValueError(f"文件不完整，期望大小:{total_size}，实际大小:{os.path.getsize(filepath)}")
                
                return True
            
            except requests.exceptions.Timeout as e:
                self.log(f"[尝试 {attempt+1}/{max_retries}] 下载超时: {url}")
                if attempt < max_retries - 1:
                    wait_time = min((attempt + 1) * 5, 30)  # 指数退避等待
                    time.sleep(wait_time)
                    continue
                raise
            except Exception as e:
                self.log(f"[尝试 {attempt+1}/{max_retries}] 下载错误: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    continue
                raise
    
        return False



    def toDynamicData(self,item):
        # 获取动态json的最终data格式
        da = self.datajson.copy()
        type = item['type']
        da['id'] = item['id_str']
        da['aid'] = item['basic']['comment_id_str']
        da['comment_type'] = item['basic']['comment_type']
        da['type'] = item['type']
        # 根据不同动态类型，处理数据
        # type: DYNAMIC_TYPE_AV 视频, DYNAMIC_TYPE_WORD 文字动态, DYNAMIC_TYPE_DRAW 图文动态, DYNAMIC_TYPE_ARTICLE 专栏, DYNAMIC_TYPE_FORWARD 转发动态

        if (type == 'DYNAMIC_TYPE_AV' ) : 
            a=''
            try: 
                a= item['modules']['module_dynamic']['desc']['text']
            except (KeyError, TypeError):
                pass
            if a != '' :  a= '投稿动态：'+a +'\n\n'
            da['title'] = a + item['modules']['module_dynamic']['major']['archive']['title']
            da['text'] =  item['modules']['module_dynamic']['major']['archive']['desc']
            da['imagepath'] = [item['modules']['module_dynamic']['major']['archive']['cover']]
            da['videopath'] = 'https:'+item['modules']['module_dynamic']['major']['archive']['jump_url']
            return da
            
        elif (type == 'DYNAMIC_TYPE_DRAW') : 
            da['title'] = '图文动态'
            da['text'] = item['modules']['module_dynamic']['desc']['text']
            da['imagepath'] = []
            if (item['modules']['module_dynamic']['major'] != None):
                for img in item['modules']['module_dynamic']['major']['draw']['items']:
                    da['imagepath'].append(img['src'])
            return da
        
        elif (type == 'DYNAMIC_TYPE_WORD') : 
            da['title'] = '文字动态'
            da['text'] = item['modules']['module_dynamic']['desc']['text']
            return da
        elif (type == 'DYNAMIC_TYPE_FORWARD'):
            da['title'] = '转发的动态链接：'+str(item['orig']['id_str'])
            da['text'] = item['modules']['module_dynamic']['desc']['text']
            return da

        else : 
            self.log('暂不支持的动态类型[{0}]'.format(type))
            da['text'] = '暂不支持的类型'
            return da   


    def commentaction(self,typeid,aid):
        js = {
            'type' : typeid,
            'oid' : aid,
            'message' : '',
            'plat' : 1,
            'csrf' : ''
        }
        js['csrf'] = self.sess.cookies.get('bili_jct')
        js['message'] = self.CONFIG['autocomment'] + '\n\n\n-------' + datetime.now().strftime('%m/%d %H:%M')
        rep = self.sess.post(url='https://api.bilibili.com/x/v2/reply/add',data=js).json()
        
        self.log(' {{ code: {0} , message: {1} }}'.format(rep['code'],rep['message']))
        
    def log(self, text):
        """
        记录日志信息
        
        将日志信息同时输出到控制台和写入log.txt文件
        
        Args:
            text: 要记录的日志文本内容
            
        功能：
        1. 控制台输出（带编码处理）
        2. 检查是否启用日志记录
        3. 写入日志文件（带时间戳）
        """
        # 控制台输出（处理编码问题）
        try:
            print('[{0}]: {1}\n'.format(datetime.now().strftime('%m/%d %H:%M'), text).encode('utf-8').decode(sys_encoding))
        except UnicodeEncodeError:
            print("编码错误")
            pass

        # 检查是否启用日志记录（默认启用）
        is_log_enabled = self.CONFIG.get('is_log', True)
        if not is_log_enabled:
            return 
        
        # 写入日志文件
        log_path = os.path.join(BASEDIR, "log.txt")
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write('[{0}]: {1}\n'.format(datetime.now().strftime('%m/%d %H:%M'), text))

if __name__ == '__main__':
    obj = Dynamic()
    obj.main()