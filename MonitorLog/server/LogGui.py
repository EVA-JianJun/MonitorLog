#!/use/bin/dev python
# -*- coding: utf-8 -*-
# Python 3.x使用这行
import sys
import time
import queue
import psutil
#  import platform
import traceback
import threading
import win32con
import win32gui
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox
# from datetime import datetime
from tkinter import Toplevel, Message
from tkinter import Tk, Frame, Label, Button, Text, PhotoImage
from datetime import datetime, timedelta
from tkinter import RIDGE, LEFT, RIGHT, TOP, BOTH, INSERT, END
# NOTE 20200723 如果有客户端的内网ip一样, 但公网ip不同, 会造成冲突
# 系统是通过内网ip找到对应的公网ip, 然后通过公网ip找到gui标签进行修改的
# 如果有一样的内网ip需要使用多个log server服务端, 或者修改内网ip

# 消息类型文本,自己定义
LOG_TYPE_DICT = {
    # 普通消息
    '1'  : 'GN',
    # 交易端消息
    '2'  : 'TD',
    # 策略端消息
    '3'  : 'MD',
    # 历史服务器消息
    '5'  : 'DS',
    # 数据客户端消息
    '6'  : 'DC',
    # 数据客户端CTP消息
    '7'  : 'DSC',
    # 回测消息
    '8'  : 'BK',
    # 参数处理消息
    '9'  : 'GC',
    # 策略消息
    '10' : 'ST',
    # 远程策略消息
    '11' : 'RM',
    # 系统消息
    '14' : 'SYS',
}

class LogServerGui():

    def __init__(self, log_server_self, client_name_list, ip_dict={'127.0.0.1': '127.0.0.1'}, password=''):
        """ 系统参数 """
        # server服务本身
        self.log_server_self = log_server_self
        # ip_dict是内网为key,公网为values
        # 客户端IP列表(公网)
        self.ip_list = list(ip_dict.values())
        # 公网ip和内网ip字典
        self.ip_dict = ip_dict
        # key是公网ip, value是客户端名称
        self.client_name_dict = dict(zip(self.ip_list, client_name_list))
        # 存储客户端信息Label字典
        self.client_info_label_dict = dict()
        # 存储客户端时间字典
        self.client_time_dict = dict()
        # 邮箱通知信息
        self.mail_info_list = list()
        # 邮箱通知信息锁
        self.mail_info_lock = threading.Lock()
        # 邮件通知flag
        self.mail_flag = True
        # 命令行隐藏显示锁
        self.cmd_lock = threading.Lock()
        # 命令行隐藏显示flag
        self.cmd_show_flag = True
        # 错误消息队列
        self.show_message_queue = queue.Queue()
        # 禁用错误id用户输入文本
        self.disabled_id_user_text = ''
        # 禁用错误id列表
        self.disabled_id_list = list()
        # 禁用错误id时效字典
        self.disabled_id_enable_info_dict = dict()
        # 固化id集合
        self.disabled_id_pin_set = set()
        # 禁用id列表str
        self.id_list_str = ""

        # 计时, 每24小时重置错误id list
        self.disabled_time_run_n = 0

        # 初始化客户端时间
        for ip in self.ip_list:
            self.client_time_dict[ip] = datetime.now() - timedelta(minutes=1)

        # 日志序号
        self.log_num = 1
        # 插入日志锁
        self.log_lock = threading.Lock()
        # 刷新客户端信息锁
        self.refresh_client_info_lock = threading.Lock()

        """ 初始化主窗口 """
        self.root = Tk()
        if password == b'XyUyTki7jpbYJLoS':
            # 管理员
            self.root.title("SERVER LOG (admin)")
        else:
            self.root.title("SERVER LOG")
        try:
            self.root.iconbitmap('./ico/ico.ico')
        except Exception:
            pass
        # 设置窗口大小
        width = 1020

        # 动态设置高度
        height = 610 + 23 * len(self.ip_list)

        """
        if platform.version()[:2] == '10':
            # win10
            height = 652
        else:
            # win7
            height = 670
        """

        # 获取屏幕尺寸以计算布局参数，使窗口居屏幕中央
        self.screenwidth = self.root.winfo_screenwidth()
        self.screenheight = self.root.winfo_screenheight()
        alignstr = '%dx%d+%d+%d' % (width, height, (self.screenwidth-width)/2, (self.screenheight-height)/2)
        self.root.geometry(alignstr)
        # 设置窗口是否可变长、宽，True：可变，False：不可变
        self.root.resizable(width=True, height=True)
        # 在其他窗口之上
        #  self.root.attributes("-topmost", True)

        self.initWidgets()

        # 运行邮件状态自动切换服务
        self.mail_auto_switch()

        # 运行错误窗口显示服务
        self.show_message_server()

    def initWidgets(self):
        """ 初始化组件 """
        # 主标题框架
        self.title_frame = Frame(self.root)
        self.title_frame.pack(side=TOP)
        s_frame = Frame(self.root)
        s_frame.pack(side=TOP)

        ss_frame = Frame(s_frame)
        ss_frame.pack(side=LEFT)
        # 图片框架
        #  self.img_frame = Frame(ss_frame)
        #  self.img_frame.pack(side=RIGHT)

        # 客户端信息框架
        self.client_info_frame = Frame(ss_frame)
        self.client_info_frame.pack(side=TOP, pady=5, anchor='w')
        # 日志框架
        self.log_frame = Frame(ss_frame)
        self.log_frame.pack(side=TOP, pady=5)
        # 按钮框架
        self.button_frame = Frame(ss_frame)
        self.button_frame.pack(side=TOP, pady=2)

        """ 放置部件 """
        """ 放置标题 """
        # 设置窗口标题
        title_label = Label(self.title_frame, text="SERVER LOG", font=("Arial", 24, "bold"))
        title_label.pack()

        """ 放置客户端信息窗口 """
        # 设置客户端信息显示frame
        # 主Frame,这个信息不需要修改
        client_info_frame_main = Frame(self.client_info_frame)
        client_info_frame_main.pack(side=TOP)
        Label(client_info_frame_main, text="主机IP", relief=RIDGE, width=18).pack(side=LEFT)
        Label(client_info_frame_main, text="名称状态", relief=RIDGE, width=14).pack(side=LEFT)
        Label(client_info_frame_main, text="服务器时间", relief=RIDGE, width=20).pack(side=LEFT)
        Label(client_info_frame_main, text="网络", relief=RIDGE, width=25).pack(side=LEFT)
        Label(client_info_frame_main, text="CPU使用率", relief=RIDGE, width=10).pack(side=LEFT)
        Label(client_info_frame_main, text="内存使用率", relief=RIDGE, width=10).pack(side=LEFT)
        Label(client_info_frame_main, text="C盘使用率", relief=RIDGE, width=10).pack(side=LEFT)
        Label(client_info_frame_main, text="进程状态", relief=RIDGE, width=29).pack(side=LEFT)

        for ip in self.ip_list:
            client_info_frame = Frame(self.client_info_frame)
            client_info_frame.pack(side=TOP)
            self.client_info_label_dict[ip] = dict()

            label_dict = self.client_info_label_dict[ip]
            l_tmp = Label(client_info_frame, text=ip, relief=RIDGE, width=18)
            label_dict['ip'] = l_tmp
            l_tmp.pack(side=LEFT)
            # l_tmp = Label(client_info_frame, text="Offline", relief=RIDGE, width=14, fg='red')
            l_tmp = Label(client_info_frame, text=self.client_name_dict.get(ip, 'ERR'), relief=RIDGE, width=14, fg='red')
            label_dict['state'] = l_tmp
            l_tmp.pack(side=LEFT)
            l_tmp = Label(client_info_frame, text="", relief=RIDGE, width=20)
            label_dict['server_time'] = l_tmp
            l_tmp.pack(side=LEFT)
            l_tmp = Label(client_info_frame, text="", relief=RIDGE, width=25)
            label_dict['network'] = l_tmp
            l_tmp.pack(side=LEFT)
            l_tmp = Label(client_info_frame, text="", relief=RIDGE, width=10)
            label_dict['cpu_rate'] = l_tmp
            l_tmp.pack(side=LEFT)
            l_tmp = Label(client_info_frame, text="", relief=RIDGE, width=10)
            label_dict['memory_rate'] = l_tmp
            l_tmp.pack(side=LEFT)
            l_tmp = Label(client_info_frame, text="", relief=RIDGE, width=10)
            label_dict['disk_c_rate'] = l_tmp
            l_tmp.pack(side=LEFT)
            l_tmp = Label(client_info_frame, text="", relief=RIDGE, width=29)
            label_dict['process_status'] = l_tmp
            l_tmp.pack(side=LEFT)

            # 错误次数信息
            label_dict['server_time_err_times'] = 0
            label_dict['network_err_times'] = 0
            label_dict['cpu_rate_err_times'] = 0
            label_dict['memory_rate_err_times'] = 0
            label_dict['disk_c_rate_err_times'] = 0
            label_dict['process_status_err_times'] = 0

        """ 放置日志表格 """
        # 创建滚动条
        scroll = tk.Scrollbar(self.log_frame)
        # side是滚动条放置的位置，上下左右。fill是将滚动条沿着y轴填充
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        # 创建表格
        treeview = ttk.Treeview(self.log_frame, height=23, show="headings", columns=("ID", "ip", "log id", "type", "insert time", "info"))
        self.treeview = treeview
        # 配置几个颜色标签
        # Crimson 深红/猩红
        treeview.tag_configure('Crimson', background='Crimson')
        # Fuchsia 紫红/灯笼海棠
        treeview.tag_configure('Fuchsia', background='Fuchsia')
        # DarkOrchid 暗兰花紫
        treeview.tag_configure('DarkOrchid', background='DarkOrchid')
        # LightSkyBlue 亮天蓝色
        treeview.tag_configure('LightSkyBlue', background='LightSkyBlue')
        # MediumPurple 中紫色
        treeview.tag_configure('MediumPurple', background='MediumPurple')
        # MediumPurple 中紫色
        treeview.tag_configure('OrangeRed', background='OrangeRed')

        # 将文本框关联到滚动条上，滚动条滑动，文本框跟随滑动
        scroll.config(command=treeview.yview)
        # 将滚动条关联到文本框
        treeview.config(yscrollcommand=scroll.set)

        # 表示列,不显示
        treeview.column("ID", width=45, anchor='center')
        treeview.column("ip", width=100, anchor='center')
        treeview.column("log id", width=50, anchor='center')
        treeview.column("type", width=40, anchor='center')
        treeview.column("insert time", width=135, anchor='center')
        treeview.column("info", width=630, anchor='w')

        # 显示表头
        treeview.heading("ID", text="ID")
        treeview.heading("ip", text="ip")
        treeview.heading("log id", text="log id")
        treeview.heading("type", text="type")
        treeview.heading("insert time", text="insert time")
        treeview.heading("info", text="info")

        # 放置表格
        treeview.pack(side=LEFT, fill=BOTH)

        """ 放置按钮 """
        # 邮件开关
        self.ClkCnt=[0,0,0]
        self.button_lock = threading.Lock()
        self.lcClk = threading.local()
        #  self.mail_flag_button = Button(self.button_frame, text='邮件打开', font=('Arial', 11, 'bold'), bg='White', fg='Black', bd=2, width=8, command=self.switch_mail)
        self.mail_flag_button = Button(self.button_frame, text='邮件打开', font=('Arial', 11, 'bold'), bg='ForestGreen', fg='Black', bd=2, width=8)
        self.mail_flag_button.pack(side=RIGHT)
        # 绑定单机双击等动作函数
        self.mail_flag_button.bind("<Button-1>", self.one_button_click)
        self.mail_flag_button.bind("<Double-Button-1>", self.double_button_click)
        self.mail_flag_button.bind("<Triple-Button-1>", self.triple_button_click)
        # 显示邮件按钮
        show_mail_button = Button(self.button_frame, text='显示邮件', font=('Arial', 11, 'bold'), bd=2, width=8, command=self.show_mail)
        show_mail_button.pack(side=RIGHT)
        # 清空邮件按钮
        del_mail_button = Button(self.button_frame, text='清空邮件', font=('Arial', 11, 'bold'), bd=2, width=8, command=self.del_mail)
        del_mail_button.pack(side=RIGHT)
        # 显示隐藏命令行
        cmd_button = Button(self.button_frame, text='命令行', font=('Arial', 11, 'bold'), bd=2, width=8, command=self.cmd)
        cmd_button.pack(side=RIGHT)
        # 禁用错误ID按钮
        disabled_id_button = Button(self.button_frame, text='禁用错误', font=('Arial', 11, 'bold'), bd=2, width=8, command=self.show_disabled_id)
        disabled_id_button.pack(side=RIGHT)

        # 由于设计缺陷,按钮不能靠右,就放一个空标签让两按钮靠右
        Label(self.button_frame, text='', width=2, height=30).pack(side=RIGHT)
        # Label(self.button_frame, text="", width=105).pack(side=RIGHT)
        try:
            self.img_png = PhotoImage(file='ico/bg.png')
        except Exception:
            self.img_png = PhotoImage()
        Label(self.button_frame, image=self.img_png, width=720, height=30).pack(side=LEFT)
        # Label(self.button_frame, text="", width=105).pack(side=RIGHT)

    def filter_thr(self, clk):
        """ 过滤器线程 """
        self.lcClk.clk=clk
        slp=time.sleep
        tm=time.time
        t=tm()
        while tm()-t<0.3:
            self.button_lock.acquire()
            if self.ClkCnt[self.lcClk.clk-1]==0 :
                self.button_lock.release()
                return
            if max(self.ClkCnt)> self.lcClk.clk :
                self.ClkCnt[self.lcClk.clk-1]=0
                self.button_lock.release()
                return

            self.button_lock.release()
            slp(0.01)

        print('单双叁'[self.lcClk.clk-1],'击')
        self.switch_mail(self.lcClk.clk)
        self.ClkCnt[self.lcClk.clk-1]=0
        return

    def one_button_click(self, event):
        """ 单击按钮回调 """
        if self.ClkCnt[0]==0 :
            self.ClkCnt[0]=1
            threading.Thread(target=self.filter_thr, args=(1, )).start()

    def double_button_click(self, event):
        """ 双击按钮回调 """
        if self.ClkCnt[1]==0 :
            self.ClkCnt[1]=2
            threading.Thread(target=self.filter_thr, args=(2, )).start()

    def triple_button_click(self, event):
        """ 三击按钮回调 """
        if self.ClkCnt[2]==0 :
            self.ClkCnt[2]=3
            threading.Thread(target=self.filter_thr, args=(3, )).start()

    def switch_mail(self, cick_num):
        """ 切换邮件开关 """
        def switch_open():
            """ 切换到打开 """
            self.mail_flag = True
            self.mail_flag_button['text'] = '邮件打开'
            self.mail_flag_button['bg'] = 'ForestGreen'
            self.mail_flag_button['fg'] = 'Black'

        def switch_pause():
            """ 切换到暂停 """
            self.mail_flag = False
            self.mail_flag_button['text'] = '邮件暂停'
            self.mail_flag_button['bg'] = 'Orange'
            self.mail_flag_button['fg'] = 'Black'

        def switch_close():
            """ 切换到关闭 """
            self.mail_flag = False
            self.mail_flag_button['text'] = '邮件关闭'
            self.mail_flag_button['bg'] = 'Red'
            self.mail_flag_button['fg'] = 'Black'

        if self.mail_flag_button['text'] == '邮件打开':
            # 当前为邮件打开
            if cick_num == 1:
                # 单机 就暂停
                switch_pause()
            else:
                # 双击 就关闭
                switch_close()
        elif self.mail_flag_button['text'] == '邮件暂停':
            # 当前为邮件暂停
            if cick_num == 1:
                # 单机 就打开
                switch_open()
            else:
                # 双击 就关闭
                switch_close()
        else:
            # 当前为邮件关闭
            if cick_num == 1:
                # 单机 就暂停
                switch_pause()
            else:
                # 双击 就打开
                switch_open()

    def mail_auto_switch(self):
        """ 邮件状态自动切换守护线程 """
        # 如果用户暂时把邮件开关关闭,那么这个函数会在一定时间后自动打开邮件开关
        # 防止用户忘记打开邮件开关
        def sub():
            # 10s后自动隐藏命令行
            time.sleep(10)
            self.cmd()

            while True:
                try:
                    time.sleep(60)
                    # 每分钟检测一次
                    if self.mail_flag_button['text'] == '邮件暂停':
                        # 如果当前邮件开关是关闭的,启动下面的循环
                        #  print("debug: 检测到邮件暂停!")
                        time.sleep(3600)
                        # 等待1小时后
                        if self.mail_flag_button['text'] == '邮件暂停':
                            # 再检测到邮件暂停,那么运行切换函数会自动打开邮件开关
                            #  print("debug: 检测到邮件还是暂停!")
                            # 设置为邮件打开
                            self.switch_mail(1)
                        #  else:
                            #  print("debug: 检测到邮件又打开了!")
                    #  else:
                        #  print("debug: 检测到邮件打开!")
                except Exception as err:
                    traceback.print_exc()
                    print(err)

        t = threading.Thread(target=sub)
        t.setDaemon(True)
        t.start()

    def del_mail(self):
        """ 清空邮件 """
        self.mail_info_lock.acquire()
        try:
            # 邮件列表赋值为空列表
            self.mail_info_list = list()
        finally:
            self.mail_info_lock.release()
        """
        # 下面的功能弃用, 现在直接点击按钮后就清空, 不需要用户再选择
        if tk.messagebox.askyesno(title='警告!', message='是否清空邮件?'):
            # 用户选择清空邮件
            self.mail_info_lock.acquire()
            try:
                # 邮件列表赋值为空列表
                self.mail_info_list = list()
            finally:
                self.mail_info_lock.release()
        #  else:
            #  print("DEBUG: 不清空邮件!")
        pass
        """

    def show_mail(self):
        """ 显示邮件 """
        def center(win):
            # 让窗口居中显示(不知道为啥有时候无效)
            win.update_idletasks()
            width = win.winfo_width()
            height = win.winfo_height()
            x = (win.winfo_screenwidth() // 2) - (width // 2)
            y = (win.winfo_screenheight() // 2) - (height // 2)
            win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        top = Toplevel()
        try:
            top.iconbitmap('./ico/mail.ico')
        except Exception:
            pass
        # 设置窗口大小
        top.geometry("800x400")
        # 居中
        center(top)
        # 始终置顶
        top.attributes("-topmost", True)
        top.title('邮件缓存区')
        mail_info = '\n'.join(self.mail_info_list)
        text = Text(top, width=800, height=400, padx=5, pady=5)
        text.pack()
        text.insert(INSERT, mail_info)

    def show_disabled_id(self):
        """ 显示禁用错误ID """
        def center(win):
            # 让窗口居中显示(不知道为啥有时候无效)
            win.update_idletasks()
            width = win.winfo_width()
            height = win.winfo_height()
            x = (win.winfo_screenwidth() // 2) - (width // 2)
            y = (win.winfo_screenheight() // 2) - (height // 2)
            win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        def get_user_disabled_id():
            # 获取用户输入
            self.disabled_id_user_text = disabled_id_user_text = text.get('0.0', END)
            with open('disabled_id_user_text.txt', 'w') as fw:
                if self.disabled_id_user_text[-1] == "\n":
                    fw.write(self.disabled_id_user_text[:-1])
                else:
                    fw.write(self.disabled_id_user_text)
            # 处理换行,空白等字符
            disabled_id_user_text = disabled_id_user_text.replace(' ', '').replace('\n', ',')

            self.disabled_id_list = list()
            self.disabled_id_pin_set = set()
            self.id_list_str = '['
            for id_text in disabled_id_user_text.split(','):
                try:
                    id_text_int = id_text.split(":")[0].replace('*', '')
                except IndexError:
                    continue
                try:
                    log_id = int(id_text_int)
                except ValueError:
                    pass
                else:
                    try:
                        # 获取禁用id时效信息
                        # 27001 "ok[23:10-07:00]:ok[23:10-07:00]:no[23:10-07:00]"
                        self.disabled_id_enable_info_dict[log_id] = enable_info = id_text.split(":", 1)[1].replace('*', '')
                    except IndexError:
                        enable_info = ""

                    if '*' in id_text:
                        # 是固化错误id
                        self.disabled_id_pin_set.add(log_id)
                        self.id_list_str += "*{0} {1}, ".format(log_id, enable_info)
                    else:
                        self.id_list_str += "{0} {1}, ".format(log_id, enable_info)

                    self.disabled_id_list.append(log_id)
            self.id_list_str = self.id_list_str[:-2] + ']'

            statusbar_text = "输入禁用id, 使用逗号隔开id, 当前禁用的id列表为: {0}".format(self.id_list_str)
            statusbar.config(text=statusbar_text)

            print("用户输入字符串:\n{0}".format(self.disabled_id_user_text))
            print("禁用错误id时效字典:\n{0}".format(self.disabled_id_enable_info_dict))
            print("禁用错误id列表:\n{0}".format(self.disabled_id_list))

        top = Toplevel()
        try:
            top.iconbitmap('./ico/id.ico')
        except Exception:
            pass
        # 设置窗口大小
        top.geometry("800x400")
        # 居中
        center(top)
        # 始终置顶
        top.attributes("-topmost", True)
        top.title('禁用错误id')

        # 显示用户输入文本
        text = Text(top, width=115, height=25, padx=5, pady=5)
        text.pack()
        try:
            try:
                with open('disabled_id_user_text.txt', 'r', encoding="utf-8") as fr:
                    self.disabled_id_user_text = fr.read()
            except UnicodeDecodeError:
                with open('disabled_id_user_text.txt', 'r', encoding="GBK") as fr:
                    self.disabled_id_user_text = fr.read()
        except FileNotFoundError:
            pass
        text.insert(INSERT, self.disabled_id_user_text)
        # 显示保存按钮
        button = Button(top, text='保存', font=('Arial', 11, 'bold'), bd=2, width=6, pady=4, command=get_user_disabled_id)
        button.pack()
        # 显示进度条
        statusbar_text = "输入禁用id, 使用逗号隔开id, 当前禁用的id列表为: {0}".format(self.id_list_str)
        statusbar = tk.Label(top, text=statusbar_text, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)

    def cmd(self):
        """ 显示隐藏命令行窗口 """
        self.cmd_lock.acquire()
        try:
            # 找到第一个命令行
            find_flag = False
            QQ = win32gui.FindWindowEx(0, 0, "ConsoleWindowClass", None)
            for i in range(100):
                # 循环找100次
                title = win32gui.GetWindowText(QQ)
                # print(title, QQ)
                if "cmd.exe" in title or "run_server" in title:
                    # 说明是日志客户端命令行窗口
                    find_flag = True
                    print("找到命令行窗口: {0}".format(title))
                    break
                QQ = win32gui.FindWindowEx(0, QQ, "ConsoleWindowClass", None)

            if find_flag:
                if self.cmd_show_flag:
                    # 隐藏
                    print("隐藏, 窗口句柄: {0}".format(QQ))
                    self.cmd_show_flag = False
                    win32gui.ShowWindow(QQ, win32con.SW_HIDE)
                else:
                    # 显示
                    print("显示, 窗口句柄: {0}".format(QQ))
                    win32gui.ShowWindow(QQ,win32con.SW_SHOW)
                    self.cmd_show_flag = True
        except Exception as err:
            print("\033[0;36;41m隐藏显示命令行失败!\033[0m")
            traceback.print_exc()
            print(err)
        finally:
            self.cmd_lock.release()

    def check_client_status(self):
        """ 检查客户端状态 """
        def fun():
            while True:
                try:
                    time.sleep(5)
                    now = datetime.now()
                    for ip in self.client_time_dict:
                        datetime_client_time = self.client_time_dict[ip]
                        # 客户端信息标签字典
                        label_dict = self.client_info_label_dict[ip]
                        if (now.timestamp() - datetime_client_time.timestamp()) > 45:
                            if now.hour == 3:
                                # 如果当前时间是凌晨3点就忽略这次断线，客户端设置为每天3:30会重启
                                continue
                            # 客户端每15s发送一次心跳, 如果检测到30秒没收到就离线了
                            # 用公司电脑有时候可能是网络不好容易误判离线,把这个时间延长到了45s
                            if label_dict['state']["fg"] != 'red':
                                # 如果当前状态为在线
                                label_dict['state']['fg'] = 'red'
                                label_dict['state']["text"] = self.client_name_dict.get(ip, 'ERR')
                                #  self.show_message('客户端离线! IP: {0}'.format(ip))
                                self.show_message_queue.put('客户端离线! IP: {0}'.format(ip))
                        else:
                            label_dict['state']['fg'] = 'green'
                            label_dict['state']["text"] = self.client_name_dict.get(ip, 'ERR')
                except Exception as err:
                    #  self.show_message('检测客户端状态失败: {0}'.format(err))
                    self.show_message_queue.put('检测客户端状态失败: {0}'.format(err))

        t = threading.Thread(target=fun)
        t.setDaemon(True)
        t.start()

    def mail_send_server(self):
        """ 邮件通知发送服务 """
        def sub():
            err_send_mail_times = 0
            # 每45s发送一封
            sleep_time = 45
            while True:
                # 每15s检查一次邮件信息
                try:
                    # 控制频率, 每分钟最多发送2封
                    time.sleep(sleep_time)
                    self.disabled_time_run_n += 1
                    # 每24小时重置
                    if self.disabled_time_run_n % 1900 == 0:
                    # if True: # DEBUG
                        self.id_list_str = '['
                        disabled_id_list_tmp = []
                        for log_id in self.disabled_id_list:
                            if log_id in self.disabled_id_pin_set:
                                try:
                                    # 27001 "ok[23:10-07:00]:ok[23:10-07:00]:no[23:10-07:00]"
                                    enable_info = self.disabled_id_enable_info_dict[log_id]
                                except KeyError:
                                    enable_info = ""

                                disabled_id_list_tmp.append(log_id)
                                self.id_list_str += "*{0} {1}, ".format(log_id, enable_info)
                        self.disabled_id_list = disabled_id_list_tmp
                        self.id_list_str = self.id_list_str[:-2] + ']'

                    if not self.mail_flag:
                        # 如果邮件通知开关没有打开(关闭),就跳过下面的逻辑
                        continue
                    if self.mail_info_list:
                        # 如果有邮件信息
                        self.mail_info_lock.acquire()
                        try:
                            # 以换行符进行连接
                            send_info = '\n'.join(self.mail_info_list)
                            # 发送邮件
                            if self.log_server_self.MyMailM.sendmail(send_info):
                                # 如果发送成功, 邮件信息列表赋值为空
                                self.mail_info_list = list()
                                err_send_mail_times = 0
                                sleep_time = 45
                            else:
                                # 显示一个警告, 然后会向邮件信息列表中添加一个信息,下次又会尝试进行邮件发送
                                if err_send_mail_times < 3:
                                    # 只警告3次
                                    err_send_mail_times += 1
                                    self.show_message("邮件发送失败!")
                                else:
                                    # 表示连续3次发送失败了, 等待5分钟再发
                                    sleep_time = 300
                        finally:
                            self.mail_info_lock.release()
                except Exception as err:
                    print("\033[0;36;41m邮件信息发送系统错误!\033[0m")
                    traceback.print_exc()
                    print(err)

        t = threading.Thread(target=sub)
        t.setDaemon(True)
        t.start()

    def run(self):
        """ 运行窗口 """
        # self.test()

        self.mail_send_server()

        self.check_client_status()

        self.root.mainloop()

    def show_message_server(self):
        """ 显示错误信息窗口服务 """
        def sub():
            while True:
                try:
                    # 时间间隔为10秒
                    time.sleep(10)
                    # 没数据会阻塞在这，有数据会先取一个数据出来
                    all_message = '{0}\n'.format(self.show_message_queue.get())
                    # 然后如果有多余的数据会接着全部取出来
                    while not self.show_message_queue.empty():
                        # 如果不为空,就取出全部信息
                        all_message += '{0}\n'.format(self.show_message_queue.get())
                    if self.mail_flag:
                        # 邮件打开才会显示错误窗口
                        # 显示错误窗口
                        self.show_message(all_message)
                except Exception as err:
                    print("\033[0;36;41m错误窗口逻辑处理错误!\033[0m")
                    traceback.print_exc()
                    print(err)

        th = threading.Thread(target=sub)
        th.setDaemon(True)
        th.start()

    def show_message(self, info):
        """ 显示一个顶级窗口 """
        def center(win):
            # 让窗口居中显示(不知道为啥有时候无效)
            win.update_idletasks()
            width = win.winfo_width()
            height = win.winfo_height()
            x = (win.winfo_screenwidth() // 2) - (width // 2)
            y = (win.winfo_screenheight() // 2) - (height // 2)
            win.geometry('{}x{}+{}+{}'.format(width, height, x, y))

        top = Toplevel()
        try:
            top.iconbitmap('./ico/err.ico')
        except Exception:
            pass
        # 设置窗口大小
        top.geometry("200x100")
        # 居中
        center(top)
        # 始终置顶
        top.attributes("-topmost", True)
        top.title('错误')
        Message(top, text=info, padx=5, pady=5).pack()

        # 随便put进一个值发出警告音
        self.log_server_self.war_sound_queue.put(1)
        # 发送邮件通知
        #  self.log_server_self.MyMailM.sendmail(info)
        # 现在换成向邮件信息列表中append一个信息,由其他线程来进行邮件发送
        self.mail_info_list.append("{0}: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), info))

    def test(self):
        """ TK测试函数 """
        def fun():
            import time
            time.sleep(1)
            self.insert_log('192.168.0.174', 24028, "2019-12-04 15:36:06", "IG建设大街客观的说法窘迫招待费孤迥")
            time.sleep(1)
            self.insert_log('192.168.0.174', 27028, "2019-12-04 15:36:06", "感觉速度价格数量的结果看了但是")
            time.sleep(1)
            self.insert_log('192.168.0.174', 12006, "2019-12-04 15:36:06", "个卡萨丁胡感受到星际恐龙")

            client_info_dict = {'ip': '192.168.0.174',
                'type': 'heart',
                'client_info':
                    {
                        'user': [1, 'Administrator'],
                        'server_time': ['2020-01-14 10:40:06', '2020-01-07 09:06:24'],
                        'network': ['9.26 Kb/s', '1.56 Kb/s'], 'cpu_count': 4,
                        'cpu_rate': '18.4%',
                        'memory': ['47%', '8.34', '15.94'],
                        'disk':
                            {
                            'C:\\': {'total': 107375226880, 'used': 65918775296, 'free': 41456451584, 'percent': 61.4},
                            'D:\\': {'total': 72668409856, 'used': 31608078336, 'free': 41060331520, 'percent': 43.5},
                            'E:\\': {'total': 536871956480, 'used': 69684682752, 'free': 467187273728, 'percent': 13.0},
                            'F:\\': {'total': 1073742868480, 'used': 194474962944, 'free': 879267905536, 'percent': 18.1},
                            'G:\\': {'total': 389779812352, 'used': 145281527808, 'free': 244498284544, 'percent': 37.3}
                            },
                        'process_status' : ['OK', 'MD: 6 DS: 6'],
                    }
            }
            self.refresh_client_info(client_info_dict)
            client_info_dict = {'ip': '192.168.0.164',
                'type': 'heart',
                'client_info':
                    {
                        'user': [1, 'Administrator'],
                        'server_time': ['2020-01-14 10:40:06', '2020-01-07 09:06:24'],
                        'network': ['9.26 Kb/s', '1.56 Kb/s'], 'cpu_count': 4,
                        'cpu_rate': '18.4%',
                        'memory': ['47%', '8.34', '15.94'],
                        'disk':
                            {
                            'C:\\': {'total': 107375226880, 'used': 65918775296, 'free': 41456451584, 'percent': 61.4},
                            'D:\\': {'total': 72668409856, 'used': 31608078336, 'free': 41060331520, 'percent': 43.5},
                            'E:\\': {'total': 536871956480, 'used': 69684682752, 'free': 467187273728, 'percent': 13.0},
                            'F:\\': {'total': 1073742868480, 'used': 194474962944, 'free': 879267905536, 'percent': 18.1},
                            'G:\\': {'total': 389779812352, 'used': 145281527808, 'free': 244498284544, 'percent': 37.3}
                            },
                        'process_status' : ['ERR', 'MD: 6 DS: 6'],
                    }
            }
            self.refresh_client_info(client_info_dict)

        self.mythread = threading.Thread(target=fun)
        self.mythread.setDaemon(True)
        self.mythread.start()

    """ 用户 API """
    def insert_log(self, ip, log_id, insert_time, info):
        """ 插入一条log信息 """
        self.log_lock.acquire()
        try:
            # 尝试换算为公网IP
            ip = self.ip_dict.get(ip, ip)
            log_id_int = int(log_id)
            log_id = str(log_id)
            # 'xx x xxx' 107001
            # 'x  x xxx' 27001
            # 日志ID有两种长度,原先的设计缺陷导致的,所以下面用这个逻辑把需要的指示符提取出来
            log_type = log_id[-4:-3]
            it = log_id[:-4]

            # 判断日志出处
            info_type = LOG_TYPE_DICT.get(it, 'ERR')

            # tag用于改变表格颜色
            tag = None
            if log_type == '4':
                # 说明是错误消息
                #  self.show_message('客户端出现错误,错误ID: {0}'.format(log_id), info)
                if log_id_int not in self.disabled_id_list:
                    # 不在禁用id列表里才进行通知
                    self.show_message_queue.put('客户端出现错误,错误ID: {0}\n{1}'.format(log_id, info))
                else:
                    try:
                        # "ok[23:10-07:00]:ok[23:10-07:00]:no[23:10-07:00]"
                        try:
                            enable_info = self.disabled_id_enable_info_dict[log_id_int]
                        except KeyError:
                            pass
                        else:
                            for info_i in enable_info.split("]:"):
                                # ['ok[23:10-07:00', 'ok[23:10-07:00', 'no[23:10-07:00]']
                                ok_or_no, time_str = info_i.split("[")

                                hour_1 = int(time_str[:2])
                                minute_1 = int(time_str[3:5])
                                hour_2 = int(time_str[6:8])
                                minute_2 = int(time_str[9:11])

                                now = datetime.now()
                                date1 = now.replace(hour=hour_1, minute=minute_1, second=0, microsecond=0)
                                date2 = now.replace(hour=hour_2, minute=minute_2, second=0, microsecond=0)
                                # print(date1, date2)
                                if date2 < date1:
                                    date2 += timedelta(days=1)

                                if ok_or_no == "no":
                                    # 在时间段里面不通知
                                    if date1 <= now <= date2:
                                        pass
                                    else:
                                        self.show_message_queue.put('客户端出现错误,错误ID: {0}\n{1}'.format(log_id, info))
                                else:
                                    # 在时间段里就通知
                                    if date1 <= now <= date2:
                                        self.show_message_queue.put('客户端出现错误,错误ID: {0}\n{1}'.format(log_id, info))
                                    else:
                                        pass

                    except Exception as err:
                        print("禁用id时效逻辑处理错误")
                        traceback.print_exc()
                        print(err)

                tag = 'Crimson'
            elif log_type == '7':
                # 管理员消息
                tag = 'MediumPurple'
                # 直接发送邮件
                if log_id_int not in self.disabled_id_list:
                    # 禁用了管理员邮件也不会发送
                    self.mail_info_list.append(info)
                else:
                    try:
                        # "ok[23:10-07:00]:ok[23:10-07:00]:no[23:10-07:00]"
                        try:
                            enable_info = self.disabled_id_enable_info_dict[log_id_int]
                        except KeyError:
                            pass
                        else:
                            for info_i in enable_info.split("]:"):
                                # ['ok[23:10-07:00', 'ok[23:10-07:00', 'no[23:10-07:00]']
                                ok_or_no, time_str = info_i.split("[")

                                hour_1 = int(time_str[:2])
                                minute_1 = int(time_str[3:5])
                                hour_2 = int(time_str[6:8])
                                minute_2 = int(time_str[9:11])

                                now = datetime.now()
                                date1 = now.replace(hour=hour_1, minute=minute_1, second=0, microsecond=0)
                                date2 = now.replace(hour=hour_2, minute=minute_2, second=0, microsecond=0)
                                if date2 < date1:
                                    date2 += timedelta(days=1)

                                if ok_or_no == "no":
                                    # 在时间段里面不通知
                                    if date1 <= now <= date2:
                                        pass
                                    else:
                                        self.mail_info_list.append(info)
                                else:
                                    # 在时间段里就通知
                                    if date1 <= now <= date2:
                                        self.mail_info_list.append(info)
                                    else:
                                        pass

                    except Exception as err:
                        print("禁用id时效逻辑处理错误")
                        traceback.print_exc()
                        print(err)

            elif log_type == '5':
                # 管理员消息
                tag = 'OrangeRed'

            if tag:
                self.treeview.insert("", 0, text="line1", values=(str(self.log_num), ip, log_id, info_type, str(insert_time), info), tags=(tag,))
            else:
                self.treeview.insert("", 0, text="line1", values=(str(self.log_num), ip, log_id, info_type, str(insert_time), info))
            self.log_num += 1
        except Exception as err:
            #  self.show_message('插入日志失败: {0}'.format(err))
            self.show_message_queue.put('插入日志失败: {0}'.format(err))
        finally:
            self.log_lock.release()

    def refresh_client_info(self, client_info_dict):
        """ 刷新客户端信息 """
        """
            client_info_dict = {'ip': '192.168.0.174',
            'type': 'heart',
            'client_info':
                {
                    'user': [1, 'Administrator'],
                    'server_time': ['2020-01-14 10:40:06', '2020-01-07 09:06:24'],
                    'network': ['9.26 Kb/s', '1.56 Kb/s'], 'cpu_count': 4,
                    'cpu_rate': '18.4%',
                    'memory': ['47%', '8.34', '15.94'],
                    'disk':
                        {
                        'C:\\': {'total': 107375226880, 'used': 65918775296, 'free': 41456451584, 'percent': 61.4},
                        'D:\\': {'total': 72668409856, 'used': 31608078336, 'free': 41060331520, 'percent': 43.5},
                        'E:\\': {'total': 536871956480, 'used': 69684682752, 'free': 467187273728, 'percent': 13.0},
                        'F:\\': {'total': 1073742868480, 'used': 194474962944, 'free': 879267905536, 'percent': 18.1},
                        'G:\\': {'total': 389779812352, 'used': 145281527808, 'free': 244498284544, 'percent': 37.3}
                        },
                    'process_status' : 'OK MD: 6 DS: 6',
                }
            }
        """
        self.refresh_client_info_lock.acquire()
        try:
            # 提取需要的信息
            ip = client_info_dict['ip']
            # 尝试换为公网ip
            ip = self.ip_dict.get(ip, ip)
            client_info = client_info_dict['client_info']

            # print(self.client_info_label_dict)
            # 客户端信息标签字典
            label_dict = self.client_info_label_dict[ip]

            try:
                # 客户端时间字符串
                client_time = client_info['server_time'][0]
                # 时间格式
                datetime_client_time = datetime.strptime(client_time, '%Y-%m-%d %H:%M:%S')
                # 存储客户端时间
                self.client_time_dict[ip] = datetime_client_time
                # 修改label颜色
                label_dict['server_time']['fg'] = 'black'
                # 错误次数重置为0
                label_dict['server_time_err_times'] = 0
            except Exception:
                client_time = "Error"
                label_dict['server_time']['fg'] = 'red'
                # 错误次数加1
                label_dict['server_time_err_times'] += 1
                if label_dict['server_time_err_times'] <= 2:
                    # 只发送2次错误信息
                    #  self.show_message('获取server_time Exception!')
                    self.show_message_queue.put('获取server_time Exception!')
            try:
                # 网络
                network = "↓: {0} ↑: {1}".format(client_info['network'][0], client_info['network'][1])
                label_dict['network']['fg'] = 'black'
                label_dict['network_err_times'] = 0
            except Exception:
                network = "Error"
                label_dict['network']['fg'] = 'red'
                label_dict['network_err_times'] += 1
                if label_dict['network_err_times'] <= 2:
                    #  self.show_message('获取network Exception!')
                    self.show_message_queue.put('获取network Exception!')
            try:
                # cpu使用率
                cpu_rate = client_info['cpu_rate']
                label_dict['cpu_rate']['fg'] = 'black'
                label_dict['cpu_rate_err_times'] = 0
            except Exception:
                cpu_rate = "Error"
                label_dict['cpu_rate']['fg'] = 'red'
                label_dict['cpu_rate_err_times'] += 1
                if label_dict['cpu_rate_err_times'] <= 2:
                    #  self.show_message('获取cpu_rate Exception!')
                    self.show_message_queue.put('获取cpu_rate Exception!')
            try:
                # 内容使用率
                memory_rate = client_info['memory'][0]
                if int(memory_rate[:-1]) >= 95:
                    # 内存使用率大于等于百分之90
                    label_dict['memory_rate']['fg'] = 'red'
                    label_dict['memory_rate_err_times'] += 1
                    if label_dict['memory_rate_err_times'] <= 2:
                        #  self.show_message('客户端内存使用率过高! {0}'.format(memory_rate))
                        self.show_message_queue.put('客户端内存使用率过高! {0}'.format(memory_rate))
                else:
                    label_dict['memory_rate']['fg'] = 'black'
                    label_dict['memory_rate_err_times'] = 0
            except Exception:
                memory_rate = "Error"
                label_dict['memory_rate']['fg'] = 'red'
                label_dict['memory_rate_err_times'] += 1
                if label_dict['memory_rate_err_times'] <= 2:
                    #  self.show_message('获取memory_rate Exception!')
                    self.show_message_queue.put('获取memory_rate Exception!')
            # C盘使用率int
            try:
                disk_c_rate = client_info['disk']['C:\\']['percent']
                if disk_c_rate >= 80:
                    # C盘使用率大于等于80
                    label_dict['disk_c_rate']['fg'] = 'red'
                    label_dict['disk_c_rate_err_times'] += 1
                    if label_dict['disk_c_rate_err_times'] <= 2:
                        #  self.show_message('客户端C盘使用率过高! {0}'.format(disk_c_rate))
                        self.show_message_queue.put('客户端C盘使用率过高! {0}'.format(disk_c_rate))
                else:
                    label_dict['disk_c_rate']['fg'] = 'black'
                    label_dict['disk_c_rate_err_times'] = 0
                disk_c_rate = "{0}%".format(disk_c_rate)
            except Exception:
                disk_c_rate = 'Error'
                label_dict['disk_c_rate']['fg'] = 'red'
                label_dict['disk_c_rate_err_times'] += 1
                if label_dict['disk_c_rate_err_times'] <= 2:
                    #  self.show_message('获取disk_c_rate Exception!')
                    self.show_message_queue.put('获取disk_c_rate Exception!')
            # 客户端进程状态
            try:
                process_status = client_info['process_status']
                if process_status[0] == 'OK':
                    # 表示客户端进程正确
                    label_dict['process_status']['fg'] = 'black'
                    label_dict['process_status_err_times'] = 0
                else:
                    label_dict['process_status']['fg'] = 'red'
                    label_dict['process_status_err_times'] += 1
                    if label_dict['process_status_err_times'] <= 2:
                        #  self.show_message('客户端进程状态错误!')
                        self.show_message_queue.put('客户端进程状态错误!')
                process_status = process_status[1]
            except Exception:
                process_status = 'Error'
                label_dict['process_status']['fg'] = 'red'
                label_dict['process_status_err_times'] += 1
                if label_dict['process_status_err_times'] <= 2:
                    #  self.show_message('获取process_status Exception!')
                    self.show_message_queue.put('获取process_status Exception!')

            """ 修改label """
            label_dict['server_time']["text"] = client_time
            label_dict['network']["text"] = network
            label_dict['cpu_rate']["text"] = cpu_rate
            label_dict['memory_rate']["text"]= memory_rate
            label_dict['disk_c_rate']["text"] = disk_c_rate
            label_dict['process_status']["text"] = process_status

        except Exception as err:
            #  self.show_message('刷新客户端信息失败: {0}'.format(err))
            self.show_message_queue.put('刷新客户端信息失败: {0}'.format(err))
            traceback.print_exc()
            print(err)
        finally:
            self.refresh_client_info_lock.release()

class Check_Exe():
    """ 检查是否重复运行 """
    def check(self, pro_name="run_server.exe"):
        """ 检查进场列表 """
        pro_i = 0
        for proc in psutil.process_iter():
            if proc.name() == pro_name:
                pro_i += 1

        if pro_i > 2:
            # 这个进程最多只有两个, 一个父进程, 一个子进程, 超过就结束
            self.show_mas()

    def show_mas(self):
        root = tkinter.Tk()
        # 隐藏主窗口
        root.withdraw()
        tkinter.messagebox.showerror("错误", "不能重复运行日志进程!")
        # 退出进程
        sys.exit(1)

if __name__ == '__main__':
    lsg = LogServerGui(['192.168.0.174', '192.168.0.164'])
    lsg.run()
