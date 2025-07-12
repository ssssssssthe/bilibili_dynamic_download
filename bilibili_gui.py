"""
哔哩哔哩动态自动缓存GUI程序
作者: 艾
基于 AutoDownBUPDynamic 项目开发

功能说明:
- 提供图形化界面管理B站动态缓存
- 支持扫码登录B站账号
- 可配置监控的UP主列表和检查间隔
- 实时显示运行日志
- 支持配置文件的保存和重置

主要特性:
1. GUI界面操作，无需命令行
2. 在保存到目录后增加了一次移动操作
3. 会下载UP的全部动态然后检查更新
4. 支持二维码登录和自动评论功能
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
import sys
import threading
import subprocess
import webbrowser
from datetime import datetime
import requests

class BilibiliCacheGUI:
    """
    哔哩哔哩动态自动缓存GUI主类
    
    负责创建和管理整个图形用户界面，包括：
    - 控制面板（启动/停止监控、登录等）
    - 配置管理（基本配置、高级配置、JSON编辑器）
    - 日志显示面板
    - 扫码登录功能
    """
    def __init__(self, root):
        """
        初始化GUI应用程序
        
        Args:
            root: tkinter主窗口对象
        """
        self.root = root
        self.root.title("哔哩哔哩动态自动缓存")
        self.root.geometry("1000x850")
        self.root.resizable(True, True)
        
        # 设置窗口居中显示
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() // 2) - (1000 // 2)
        y = (self.root.winfo_screenheight() // 2) - (850 // 2)
        self.root.geometry(f"1000x850+{x}+{y}")
        
        # 确保窗口在最前面显示
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        
        # 设置窗口图标
        if os.path.exists('favicon.ico'):
            self.root.iconbitmap('favicon.ico')
        
        # 配置文件路径设置
        self.config_path = 'static/config.json'           # 用户配置文件路径
        self.default_config_path = 'static/default_config.json'  # 默认配置文件路径
        
        # 全局状态变量
        self.dynamic_process = None    # 动态监控进程对象
        self.dynamic_thread = None     # 动态监控线程对象
        self.is_running = False        # 监控运行状态标志
        
        # 初始化用户界面和加载配置
        self.init_ui()
        self.load_config()
        
    def init_ui(self):
        """
        初始化用户界面
        
        创建主窗口的布局结构：
        - 顶部：标题栏
        - 左侧：控制面板（启动/停止、登录等）
        - 右侧：配置管理面板（基本配置、高级配置、JSON编辑器）
        - 底部：日志显示面板
        """
        # 创建主框架容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # 配置网格权重，使界面元素能够自适应调整大小
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)  # 右侧配置面板可扩展
        main_frame.rowconfigure(2, weight=1)     # 底部日志面板可扩展
        
        # 创建标题标签
        title_label = ttk.Label(main_frame, text="哔哩哔哩动态自动缓存", 
                               font=('Microsoft YaHei', 16, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # 创建各个功能面板
        self.create_control_panel(main_frame)    # 左侧控制面板
        self.create_config_panel(main_frame)     # 右侧配置面板
        self.create_log_panel(main_frame)        # 底部日志面板
        
    def create_control_panel(self, parent):
        """
        创建左侧控制面板
        
        包含以下功能按钮：
        - 监控状态显示
        - 启动/停止监控
        - 扫码登录
        - 配置管理（保存/重置）
        - 文件管理（打开目录/日志）
        - 项目信息显示
        
        Args:
            parent: 父容器组件
        """
        control_frame = ttk.LabelFrame(parent, text="控制面板", padding="10")
        control_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        
        # 监控状态显示标签
        self.status_label = ttk.Label(control_frame, text="状态: 未运行", 
                                     font=('Microsoft YaHei', 10))
        self.status_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # 监控控制按钮组
        self.start_btn = ttk.Button(control_frame, text="启动监控", 
                                   command=self.start_dynamic, width=15)
        self.start_btn.grid(row=1, column=0, pady=5)
        
        self.stop_btn = ttk.Button(control_frame, text="停止监控", 
                                  command=self.stop_dynamic, width=15, state='disabled')
        self.stop_btn.grid(row=1, column=1, pady=5)
        
        # 账号登录按钮
        self.login_btn = ttk.Button(control_frame, text="扫码登录", 
                                   command=self.manual_login, width=15)
        self.login_btn.grid(row=2, column=0, pady=5)
        
        # 配置管理按钮组
        ttk.Button(control_frame, text="保存配置", 
                  command=self.save_config, width=15).grid(row=3, column=0, pady=5)
        ttk.Button(control_frame, text="重置配置", 
                  command=self.reset_config, width=15).grid(row=3, column=1, pady=5)
        
        # 文件管理按钮组
        ttk.Button(control_frame, text="打开数据目录", 
                  command=self.open_data_dir, width=15).grid(row=4, column=0, pady=5)
        ttk.Button(control_frame, text="打开日志文件", 
                  command=self.open_log_file, width=15).grid(row=4, column=1, pady=5)
        
        # 日志管理按钮组
        ttk.Button(control_frame, text="清空日志", 
                  command=self.clear_log, width=15).grid(row=5, column=0, pady=5)
        
        # 目录设置按钮
        ttk.Button(control_frame, text="设置数据目录", 
                  command=self.set_data_dir, width=15).grid(row=5, column=1, pady=5)

        # 作者和说明
        info_text1 = "作者: 艾"
        info_text2 = "基于 "
        info_text3 = "区别：\nGUI界面\n在保存到目录后增加了一次移动\n会下载UP的全部动态然后检查更新"

        # 第一行
        info_label1 = tk.Label(control_frame, text=info_text1, font=("Microsoft YaHei", 8), fg="#888888", justify="left", anchor="w")
        info_label1.grid(row=6, column=0, columnspan=2, sticky="w", pady=(20, 0))

        # 第二行：基于 + 超链接 + 开发（放在一个Frame里）
        def open_github(event=None):
            import webbrowser
            webbrowser.open("https://github.com/Vita-314/AutoDownBUPDynamic")

        info_row2 = tk.Frame(control_frame)
        info_row2.grid(row=7, column=0, columnspan=3, sticky="w")

        info_label2 = tk.Label(info_row2, text="基于 ", font=("Microsoft YaHei", 8), fg="#888888")
        info_label2.pack(side="left")

        link_label = tk.Label(info_row2, text="AutoDownBUPDynamic", font=("Microsoft YaHei", 8, "underline"), fg="#3366cc", cursor="hand2")
        link_label.pack(side="left")
        link_label.bind("<Button-1>", open_github)

        info_label3 = tk.Label(info_row2, text=" 开发", font=("Microsoft YaHei", 8), fg="#888888")
        info_label3.pack(side="left")

        # 其余说明
        info_label4 = tk.Label(control_frame, text=info_text3, font=("Microsoft YaHei", 8), fg="#888888", justify="left", anchor="w")
        info_label4.grid(row=8, column=0, columnspan=3, sticky="w")
        
    def create_config_panel(self, parent):
        """
        创建右侧配置管理面板
        
        包含三个主要部分：
        1. 基本配置页：UP主ID、检查间隔、基本开关
        2. 高级配置页：目录设置、二维码配置、日志配置等
        3. JSON配置编辑器：直接编辑配置文件
        
        Args:
            parent: 父容器组件
        """
        config_frame = ttk.LabelFrame(parent, text="配置管理", padding="10")
        config_frame.grid(row=1, column=1, sticky="nsew")
        config_frame.columnconfigure(0, weight=1)
        config_frame.rowconfigure(0, weight=3)  # 配置标签页占3份
        config_frame.rowconfigure(2, weight=2)  # JSON编辑器占2份

        # 创建配置标签页容器
        notebook = ttk.Notebook(config_frame)
        notebook.grid(row=0, column=0, sticky="nsew")

        # 基本配置标签页
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="基本配置")
        self.create_basic_config(basic_frame)

        # 高级配置标签页（带滚动条支持）
        adv_container = ttk.Frame(notebook)
        adv_container.grid_rowconfigure(0, weight=1)
        adv_container.grid_columnconfigure(0, weight=1)
        
        # 创建滚动画布和滚动条
        adv_canvas = tk.Canvas(adv_container, highlightthickness=0)
        adv_scrollbar = ttk.Scrollbar(adv_container, orient="vertical", command=adv_canvas.yview)
        adv_scrollable_frame = ttk.Frame(adv_canvas)
        
        # 绑定滚动事件
        adv_scrollable_frame.bind(
            "<Configure>",
            lambda e: adv_canvas.configure(scrollregion=adv_canvas.bbox("all"))
        )
        adv_canvas.create_window((0, 0), window=adv_scrollable_frame, anchor="nw")
        adv_canvas.configure(yscrollcommand=adv_scrollbar.set)
        adv_canvas.grid(row=0, column=0, sticky="nsew")
        adv_scrollbar.grid(row=0, column=1, sticky="ns")
        
        # 创建高级配置内容
        self.create_advanced_config(adv_scrollable_frame)
        notebook.add(adv_container, text="高级配置")

        # JSON配置编辑器（直接编辑配置文件）
        json_label = ttk.Label(config_frame, text="JSON配置编辑器:")
        json_label.grid(row=1, column=0, sticky="w", pady=(5, 0))
        self.config_text = scrolledtext.ScrolledText(config_frame, height=15, width=60)
        self.config_text.grid(row=2, column=0, sticky="nsew", pady=(0, 0))

    def create_basic_config(self, parent):
        """创建基本配置界面"""
        # UP主ID列表
        ttk.Label(parent, text="UP主ID列表 (每行一个):").grid(row=0, column=0, sticky="w", pady=5)
        self.bupid_text = scrolledtext.ScrolledText(parent, height=5, width=40)
        self.bupid_text.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # 检查间隔
        ttk.Label(parent, text="检查间隔 (秒):").grid(row=2, column=0, sticky="w", pady=5)
        self.interval_var = tk.StringVar(value="120")
        ttk.Entry(parent, textvariable=self.interval_var, width=10).grid(row=2, column=1, sticky="w", pady=5)
        
        # 自动下载
        self.autodownload_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="自动下载视频", variable=self.autodownload_var).grid(row=3, column=0, sticky="w", pady=5)
        
        # 首次下载
        self.downatfirst_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="首次运行时下载", variable=self.downatfirst_var).grid(row=3, column=1, sticky="w", pady=5)
        
        # 记录日志
        self.islog_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="记录日志", variable=self.islog_var).grid(row=4, column=0, sticky="w", pady=5)
        
    def create_advanced_config(self, parent):
        """创建高级配置界面"""
        # 数据目录
        ttk.Label(parent, text="数据目录:").grid(row=0, column=0, sticky="w", pady=5)
        self.datadir_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.datadir_var, width=40).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(parent, text="浏览", command=self.browse_data_dir).grid(row=0, column=2, padx=(5, 0), pady=5)

        # 最终目录
        ttk.Label(parent, text="最终目录:").grid(row=1, column=0, sticky="w", pady=5)
        self.final_dir_var = tk.StringVar()
        ttk.Entry(parent, textvariable=self.final_dir_var, width=40).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(parent, text="浏览", command=self.browse_final_dir).grid(row=1, column=2, padx=(5, 0), pady=5)

        # 合并后移动
        self.move_after_combine_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="合并后移动文件", variable=self.move_after_combine_var).grid(row=2, column=0, sticky="w", pady=5)

        # 自动评论开关
        self.enable_autocomment_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="启用自动评论", variable=self.enable_autocomment_var).grid(row=3, column=0, sticky="w", pady=5)

        # 自动评论内容
        ttk.Label(parent, text="自动评论内容:").grid(row=4, column=0, sticky="w", pady=5)
        self.autocomment_text = scrolledtext.ScrolledText(parent, height=3, width=40)
        self.autocomment_text.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # 二维码配置
        ttk.Label(parent, text="二维码配置:", font=('Microsoft YaHei', 10, 'bold')).grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 5))
        ttk.Label(parent, text="二维码缩放 (1-12):").grid(row=7, column=0, sticky="w", pady=5)
        self.qrcode_scale_var = tk.StringVar(value="8")
        ttk.Entry(parent, textvariable=self.qrcode_scale_var, width=10).grid(row=7, column=1, sticky="w", pady=5)
        ttk.Label(parent, text="二维码边框 (像素):").grid(row=8, column=0, sticky="w", pady=5)
        self.qrcode_border_var = tk.StringVar(value="20")
        ttk.Entry(parent, textvariable=self.qrcode_border_var, width=10).grid(row=8, column=1, sticky="w", pady=5)
        ttk.Label(parent, text="显示大小 (像素):").grid(row=9, column=0, sticky="w", pady=5)
        self.qrcode_display_size_var = tk.StringVar(value="180")
        ttk.Entry(parent, textvariable=self.qrcode_display_size_var, width=10).grid(row=9, column=1, sticky="w", pady=5)
        self.qrcode_use_pil_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(parent, text="使用PIL优化显示", variable=self.qrcode_use_pil_var).grid(row=10, column=0, sticky="w", pady=5)

        # 日志清理配置
        ttk.Label(parent, text="日志清理配置:", font=('Microsoft YaHei', 10, 'bold')).grid(row=11, column=0, columnspan=2, sticky="w", pady=(10, 5))
        ttk.Label(parent, text="清理间隔 (天):").grid(row=12, column=0, sticky="w", pady=5)
        self.log_clean_interval_var = tk.StringVar(value="7")
        ttk.Entry(parent, textvariable=self.log_clean_interval_var, width=10).grid(row=12, column=1, sticky="w", pady=5)
        ttk.Label(parent, text="最大日志大小 (MB):").grid(row=13, column=0, sticky="w", pady=5)
        self.max_log_size_var = tk.StringVar(value="10")
        ttk.Entry(parent, textvariable=self.max_log_size_var, width=10).grid(row=13, column=1, sticky="w", pady=5)
        self.backup_log_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(parent, text="清理前备份日志", variable=self.backup_log_var).grid(row=14, column=0, sticky="w", pady=5)

    def create_log_panel(self, parent):
        """创建底部日志面板"""
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(10, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(1, weight=1)
        
        # 日志控制按钮
        log_control_frame = ttk.Frame(log_frame)
        log_control_frame.grid(row=0, column=0, sticky="ew")
        
        ttk.Button(log_control_frame, text="刷新日志", 
                  command=self.refresh_log).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(log_control_frame, text="清空日志", 
                  command=self.clear_log).pack(side=tk.LEFT, padx=(0, 10))
        
        # 日志文件大小显示
        self.log_size_label = ttk.Label(log_control_frame, text="日志大小: 0 KB")
        self.log_size_label.pack(side=tk.RIGHT)
        
        # 日志显示区域
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=80)
        self.log_text.grid(row=1, column=0, sticky="nsew")
        
        # 初始加载日志
        self.refresh_log()
        
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                with open(self.default_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            
            # 更新界面显示
            self.update_ui_from_config(config)
            
        except Exception as e:
            messagebox.showerror("错误", f"加载配置文件失败: {str(e)}")
    
    def update_ui_from_config(self, config):
        """从配置更新界面"""
        # 基本配置
        self.bupid_text.delete(1.0, tk.END)
        if 'bupid' in config:
            self.bupid_text.insert(1.0, '\n'.join(map(str, config['bupid'])))
        
        self.interval_var.set(str(config.get('interval-sec', 120)))
        self.autodownload_var.set(config.get('autodownload', True))
        self.downatfirst_var.set(config.get('down-atfirst', True))
        self.islog_var.set(config.get('is_log', True))
        
        # 高级配置
        self.datadir_var.set(config.get('datadir', ''))
        self.final_dir_var.set(config.get('final_dir', ''))
        self.move_after_combine_var.set(config.get('move_after_combine', False))
        self.enable_autocomment_var.set(config.get('enable_autocomment', True))
        
        self.autocomment_text.delete(1.0, tk.END)
        self.autocomment_text.insert(1.0, config.get('autocomment', ''))
        
        # 二维码配置
        self.qrcode_scale_var.set(str(config.get('qrcode_scale', 8)))
        self.qrcode_border_var.set(str(config.get('qrcode_border_size', 20)))
        self.qrcode_display_size_var.set(str(config.get('qrcode_display_size', 180)))
        self.qrcode_use_pil_var.set(config.get('qrcode_use_pil', True))
        
        # 日志清理配置
        self.log_clean_interval_var.set(str(config.get('log_clean_interval_days', 7)))
        self.max_log_size_var.set(str(config.get('max_log_size_mb', 10)))
        self.backup_log_var.set(config.get('backup_log_before_clean', False))
        
        # JSON编辑器
        self.config_text.delete(1.0, tk.END)
        self.config_text.insert(1.0, json.dumps(config, ensure_ascii=False, indent=4))
    
    def save_config(self):
        """保存配置"""
        try:
            # 从界面获取配置
            config = self.get_config_from_ui()
            
            # 保存到文件
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            messagebox.showinfo("成功", "配置已保存")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")
    
    def get_config_from_ui(self, preserve_auth=True):
        """从界面获取配置"""
        config = {}
        
        # 基本配置
        bupid_text = self.bupid_text.get(1.0, tk.END).strip()
        config['bupid'] = [int(x.strip()) for x in bupid_text.split('\n') if x.strip()]
        
        config['interval-sec'] = int(self.interval_var.get())
        config['autodownload'] = self.autodownload_var.get()
        config['down-atfirst'] = self.downatfirst_var.get()
        config['is_log'] = self.islog_var.get()
        
        # 高级配置
        config['datadir'] = self.datadir_var.get()
        config['final_dir'] = self.final_dir_var.get()
        config['move_after_combine'] = self.move_after_combine_var.get()
        config['enable_autocomment'] = self.enable_autocomment_var.get()
        config['autocomment'] = self.autocomment_text.get(1.0, tk.END).strip()
        
        # 二维码配置
        config['qrcode_scale'] = int(self.qrcode_scale_var.get())
        config['qrcode_border_size'] = int(self.qrcode_border_var.get())
        config['qrcode_display_size'] = int(self.qrcode_display_size_var.get())
        config['qrcode_use_pil'] = self.qrcode_use_pil_var.get()
        
        # 日志清理配置
        config['log_clean_interval_days'] = int(self.log_clean_interval_var.get())
        config['max_log_size_mb'] = int(self.max_log_size_var.get())
        config['backup_log_before_clean'] = self.backup_log_var.get()
        
        # 根据参数决定是否保留认证信息
        if preserve_auth:
            try:
                if os.path.exists(self.config_path):
                    with open(self.config_path, 'r', encoding='utf-8') as f:
                        old_config = json.load(f)
                        for key in ['headers', 'Cookies', 'refresh_token']:
                            if key in old_config:
                                config[key] = old_config[key]
            except (FileNotFoundError, json.JSONDecodeError, KeyError):
                pass
        
        return config
    
    def reset_config(self):
        """重置配置"""
        # 询问重置类型
        result = messagebox.askyesnocancel("重置配置", 
                                         "选择重置类型：\n\n"
                                         "是 - 完全重置（包括清除登录信息）\n"
                                         "否 - 保留登录信息重置\n"
                                         "取消 - 取消操作")
        
        if result is None:  # 取消
            return
        
        try:
            if os.path.exists(self.default_config_path):
                with open(self.default_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                if result:  # 完全重置
                    # 清除认证信息
                    if 'Cookies' in config:
                        config['Cookies']['SESSDATA'] = ""
                    if 'refresh_token' in config:
                        config['refresh_token'] = ""
                    # 完全重置时关闭日志功能
                    config['is_log'] = False
                    messagebox.showinfo("成功", "配置已完全重置（登录信息已清除，日志功能已关闭）")
                else:  # 保留登录信息重置
                    # 保留原有的认证信息
                    try:
                        if os.path.exists(self.config_path):
                            with open(self.config_path, 'r', encoding='utf-8') as f:
                                old_config = json.load(f)
                                for key in ['headers', 'Cookies', 'refresh_token']:
                                    if key in old_config:
                                        config[key] = old_config[key]
                    except (FileNotFoundError, json.JSONDecodeError, KeyError):
                        pass
                    messagebox.showinfo("成功", "配置已重置（登录信息已保留）")
                
                self.update_ui_from_config(config)
                
                # 立即保存重置后的配置
                try:
                    os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                    with open(self.config_path, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    messagebox.showerror("错误", f"保存重置配置失败: {str(e)}")
            else:
                messagebox.showerror("错误", "默认配置文件不存在")
        except Exception as e:
            messagebox.showerror("错误", f"重置配置失败: {str(e)}")
    
    def start_dynamic(self):
        """启动动态监控"""
        if self.is_running:
            return

        # 启动前检查登录状态
        try:
            # 读取配置文件
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                with open(self.default_config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            sessdata = config.get('Cookies', {}).get('SESSDATA', '')
            refresh_token = config.get('refresh_token', '')
            if not sessdata or not refresh_token:
                messagebox.showwarning("未登录", "请先扫码登录！")
                self.manual_login()
                return
        except Exception as e:
            messagebox.showerror("错误", f"读取配置文件失败: {e}")
            return

        try:
            # 保存当前配置
            self.save_config()
            # 启动监控线程
            self.dynamic_thread = threading.Thread(target=self.run_dynamic)
            self.dynamic_thread.daemon = True
            self.dynamic_thread.start()
            self.is_running = True
            self.status_label.config(text="状态: 运行中")
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.add_log("监控已启动")
        except Exception as e:
            messagebox.showerror("错误", f"启动失败: {str(e)}")
    
    def stop_dynamic(self):
        """停止动态监控"""
        if not self.is_running:
            return
        
        try:
            if self.dynamic_process:
                if sys.platform == 'win32':
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.dynamic_process.pid)])
                else:
                    os.kill(self.dynamic_process.pid, 9)
                self.dynamic_process = None
            
            self.is_running = False
            self.status_label.config(text="状态: 已停止")
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            
            self.add_log("监控已停止")
            
        except Exception as e:
            messagebox.showerror("错误", f"停止失败: {str(e)}")
    
    def run_dynamic(self):
        """运行Dynamic.py"""
        try:
            self.dynamic_process = subprocess.Popen(
                [sys.executable, 'Dynamic.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='ignore'
            )
            
            while self.dynamic_process and self.dynamic_process.poll() is None:
                if self.dynamic_process.stdout is not None:
                    line = self.dynamic_process.stdout.readline()
                    if line is not None:
                        self.add_log(line.strip())
            
        except Exception as e:
            self.add_log(f"运行错误: {str(e)}")
    
    def add_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}\n"
        
        # 在主线程中更新UI
        self.root.after(0, lambda: self.log_text.insert(tk.END, log_entry))
        self.root.after(0, lambda: self.log_text.see(tk.END))
    
    def refresh_log(self):
        """刷新日志显示"""
        try:
            if os.path.exists('log.txt'):
                with open('log.txt', 'r', encoding='utf-8') as f:
                    content = f.read()
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(1.0, content)
                self.log_text.see(tk.END)
                
                # 更新日志文件大小显示
                file_size = os.path.getsize('log.txt')
                if file_size < 1024:
                    size_text = f"日志大小: {file_size} B"
                elif file_size < 1024 * 1024:
                    size_text = f"日志大小: {file_size / 1024:.1f} KB"
                else:
                    size_text = f"日志大小: {file_size / (1024 * 1024):.1f} MB"
                self.log_size_label.config(text=size_text)
            else:
                self.log_size_label.config(text="日志大小: 文件不存在")
        except Exception as e:
            self.add_log(f"读取日志失败: {str(e)}")
    
    def clear_log(self):
        """清空日志"""
        if messagebox.askyesno("确认", "确定要清空日志吗？"):
            try:
                with open('log.txt', 'w', encoding='utf-8') as f:
                    f.write('')
                self.log_text.delete(1.0, tk.END)
                self.add_log("日志已清空")
            except Exception as e:
                messagebox.showerror("错误", f"清空日志失败: {str(e)}")
    
    def open_data_dir(self):
        """打开数据目录"""
        config = self.get_config_from_ui()
        data_dir = config.get('datadir', '')
        if data_dir and os.path.exists(data_dir):
            os.startfile(data_dir)
        else:
            messagebox.showinfo("提示", "数据目录未设置或不存在")
    
    def open_log_file(self):
        """打开日志文件"""
        if os.path.exists('log.txt'):
            os.startfile('log.txt')
        else:
            messagebox.showinfo("提示", "日志文件不存在")
    
    def set_data_dir(self):
        """设置数据目录"""
        directory = filedialog.askdirectory(title="选择数据目录")
        if directory:
            self.datadir_var.set(directory)
    
    def browse_data_dir(self):
        """浏览数据目录"""
        directory = filedialog.askdirectory(title="选择数据目录")
        if directory:
            self.datadir_var.set(directory)
    
    def browse_final_dir(self):
        """浏览最终目录"""
        directory = filedialog.askdirectory(title="选择最终目录")
        if directory:
            self.final_dir_var.set(directory)

    def manual_login(self):
        """
        手动扫码登录功能
        
        创建一个独立的登录窗口，包含：
        1. 二维码显示区域
        2. 状态提示信息
        3. 登录流程控制
        4. 临时文件清理
        
        登录流程：
        1. 获取B站二维码接口
        2. 生成并显示二维码
        3. 轮询检查扫码状态
        4. 保存登录信息到配置文件
        """
        try:
            # 创建独立的登录窗口
            login_window = tk.Toplevel(self.root)
            login_window.title("B站扫码登录")
            login_window.geometry("320x420")  # 设置窗口大小
            login_window.resizable(False, False)  # 禁止调整大小
            login_window.transient(self.root)  # 设置为主窗口的临时窗口
            login_window.grab_set()  # 模态窗口，阻止其他窗口操作
            
            # 窗口居中显示
            login_window.update_idletasks()
            x = (login_window.winfo_screenwidth() // 2) - (320 // 2)
            y = (login_window.winfo_screenheight() // 2) - (420 // 2)
            login_window.geometry(f"320x420+{x}+{y}")

            # 创建标题标签
            title_label = tk.Label(login_window, text="请使用B站App扫码登录", font=("Microsoft YaHei", 14, "bold"))
            title_label.pack(pady=(20, 10))

            # 创建状态显示标签
            status_var = tk.StringVar(value="正在生成二维码...")
            status_label = tk.Label(login_window, textvariable=status_var, font=("Microsoft YaHei", 10), fg="blue")
            status_label.pack(pady=(0, 10))

            # 创建二维码显示区域
            qr_frame = tk.Frame(login_window, width=200, height=200)
            qr_frame.pack(pady=(0, 20))
            qr_frame.pack_propagate(False)  # 固定框架大小
            qr_label = tk.Label(qr_frame, bg="white")
            qr_label.pack(expand=True, fill="both")

            # 定义清理临时文件的函数
            def cleanup_qrcode_files():
                """
                清理二维码相关的临时文件
                
                删除以下文件：
                - temp_qrcode.png: 原始二维码图片
                - test_qrcode_with_border.png: 处理后的二维码图片
                """
                try:
                    qrcode_path = os.path.join(os.path.dirname(__file__), 'temp_qrcode.png')
                    if os.path.exists(qrcode_path):
                        os.remove(qrcode_path)
                except:
                    pass
                try:
                    processed_path = os.path.join(os.path.dirname(__file__), 'test_qrcode_with_border.png')
                    if os.path.exists(processed_path):
                        os.remove(processed_path)
                except:
                    pass

            # 按钮区域
            button_frame = tk.Frame(login_window)
            button_frame.pack(pady=(0, 20))
            cancel_btn = tk.Button(button_frame, text="取消", command=lambda: [cleanup_qrcode_files(), login_window.destroy()], width=15)
            cancel_btn.pack()

            def perform_login():
                try:
                    import requests
                    import pyqrcode
                    import os
                    import time
                    import json
                    sess = requests.Session()
                    sess.headers.update({
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    })
                    status_var.set("正在获取二维码...")
                    login_window.update()
                    rep = sess.get('https://passport.bilibili.com/x/passport-login/web/qrcode/generate')
                    print("二维码接口返回：", rep.text)
                    if rep.text.strip() == "":
                        status_var.set("网络请求失败，未获取到二维码数据！\n请检查网络或代理设置。")
                        return
                    try:
                        rep_json = rep.json()
                    except Exception as e:
                        status_var.set(f"二维码接口返回异常: {e}\n内容: {rep.text[:100]}")
                        return
                    if rep_json.get('code', -1) != 0:
                        status_var.set(f"获取二维码失败: {rep_json.get('message', '未知错误')}")
                        return
                    qrcode_url = rep_json['data']['url']
                    token = rep_json['data']['qrcode_key']
                    
                    # 获取二维码配置参数
                    config = self.get_config_from_ui()
                    qrcode_scale = config.get('qrcode_scale', 8)
                    qrcode_border_size = config.get('qrcode_border_size', 20)
                    qrcode_display_size = config.get('qrcode_display_size', 180)
                    qrcode_use_pil = config.get('qrcode_use_pil', True)
                    
                    # 生成二维码图片（使用配置的scale值）
                    qrcode_path = os.path.join(os.path.dirname(__file__), 'temp_qrcode.png')
                    pyqrcode.create(qrcode_url).png(qrcode_path, scale=qrcode_scale)
                    
                    # 显示二维码（根据配置选择处理方式）
                    qr_displayed = False
                    
                    # 方法1: 如果配置启用PIL，尝试使用PIL处理图片
                    if qrcode_use_pil and not qr_displayed:
                        try:
                            # 尝试多种PIL导入方式
                            try:
                                from PIL import Image, ImageTk, ImageOps
                            except ImportError:
                                try:
                                    import PIL
                                    from PIL import Image, ImageTk, ImageOps
                                except ImportError:
                                    raise ImportError("PIL/Pillow not available")
                            
                            img = Image.open(qrcode_path)
                            # 添加白边并调整大小
                            img = ImageOps.expand(img, border=qrcode_border_size, fill='white')
                            # 使用高质量重采样方法调整图片大小
                            img = img.resize((qrcode_display_size, qrcode_display_size), Image.Resampling.LANCZOS)
                            
                            # 转换为PhotoImage
                            photo = ImageTk.PhotoImage(img)
                            qr_label.config(image=photo)
                            perform_login.photo = photo  # 保持引用
                            
                            # 保存处理后的二维码用于调试
                            processed_path = os.path.join(os.path.dirname(__file__), 'test_qrcode_with_border.png')
                            img.save(processed_path)
                            
                            print("✅ 使用PIL处理二维码成功")
                            qr_displayed = True
                            
                        except Exception as pil_error:
                            print(f"PIL处理失败: {pil_error}")
                            # 如果PIL失败，继续尝试默认方式
                    
                    # 方法2: 使用默认的tkinter方式
                    if not qr_displayed:
                        try:
                            from tkinter import PhotoImage
                            photo = PhotoImage(file=qrcode_path)
                            qr_label.config(image=photo)
                            perform_login.photo = photo  # 保持引用
                            print("✅ 使用默认方式显示二维码成功")
                            qr_displayed = True
                        except Exception as tk_error:
                            print(f"默认方式也失败: {tk_error}")
                    
                    # 如果所有方法都失败
                    if not qr_displayed:
                        status_var.set("二维码显示失败，请检查依赖库\n建议安装: pip install Pillow")
                        return
                    
                    status_var.set("请使用B站App扫码")
                    
                    def poll_qrcode():
                        while True:
                            try:
                                if not login_window.winfo_exists():
                                    break
                                rst = sess.get(f'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={token}')
                                j = rst.json()
                                code = j['data']['code']
                                if code == 0:
                                    status_var.set("扫码成功，正在登录...")
                                    login_window.update()
                                    config = self.get_config_from_ui()
                                    config['refresh_token'] = j['data']['refresh_token']
                                    cookies = {}
                                    for co in rst.cookies:
                                        cookies[co.name] = co.value
                                    config['Cookies'] = cookies
                                    os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
                                    with open(self.config_path, 'w', encoding='utf-8') as f:
                                        json.dump(config, f, ensure_ascii=False, indent=4)
                                    # 清理二维码临时文件
                                    cleanup_qrcode_files()
                                    status_var.set("登录成功！")
                                    self.add_log("扫码登录成功")
                                    login_window.after(2000, login_window.destroy)
                                    break
                                elif code == 86038:
                                    status_var.set("二维码已失效，请重新获取")
                                    # 清理二维码临时文件
                                    cleanup_qrcode_files()
                                    break
                                elif code == 86090:
                                    status_var.set("等待扫码...")
                                elif code == 86101:
                                    status_var.set("已扫码，等待确认...")
                                else:
                                    status_var.set(f"未知状态: {code}")
                            except Exception as e:
                                status_var.set(f"网络错误: {e}")
                                # 清理二维码临时文件
                                cleanup_qrcode_files()
                                break
                            time.sleep(2)
                    
                    import threading
                    poll_thread = threading.Thread(target=poll_qrcode, daemon=True)
                    poll_thread.start()
                    
                except Exception as e:
                    status_var.set(f"登录失败: {e}")
                    self.add_log(f"扫码登录失败: {e}")
                    # 清理二维码临时文件
                    cleanup_qrcode_files()
            perform_login()
            
        except Exception as e:
            self.add_log(f"扫码登录失败: {e}")
            messagebox.showerror("错误", f"启动登录失败: {str(e)}")

def main():
    # 检查是否为exe环境
    if getattr(sys, 'frozen', False):
        # 如果是exe环境，使用exe所在目录
        application_path = os.path.dirname(sys.executable)
        os.chdir(application_path)
        print(f"切换到exe目录: {application_path}")
    
    # 创建主窗口
    root = tk.Tk()
    app = BilibiliCacheGUI(root)
    
    # 启动应用
    root.mainloop()

if __name__ == '__main__':
    main() 