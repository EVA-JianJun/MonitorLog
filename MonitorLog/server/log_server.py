#!/use/bin/dev python
# -*- coding: utf-8 -*-
import os
import json
import time
import queue
import pickle
import sqlite3
import socket
import winsound
import threading
import traceback
from datetime import datetime
# 导入GUI
from LogGui import LogServerGui, Check_Exe
# 从外部导入参数
with open('log_server_config.json', 'r', encoding='utf-8') as fr:
    try:
        config = json.load(fr)
        PASSWORD = config['PASSWORD'].encode()
        PORT = config['PORT']
        # 客户端公网IP
        CLIENT_IP_LIST = config['CLIENT_IP_LIST']
        # 客户端内网IP
        CLIENT_IP_LIST_LOCAL = config['CLIENT_IP_LIST_LOCAL']
        # 客户端名称列表
        CLIENT_NAME_LIST = config['CLIENT_NAME_LIST']

        # smtp服务器列表
        SMTP_SERVER_IP = config['smtp_server_ip']
        # smtp服务器端口列表
        SMTP_SERVER_PORT = config['smtp_server_port']

        # 发件人邮箱账号列表
        MY_SENDER = config['my_sender']
        # 发件人邮箱授权码列表
        MY_PASS = config['my_pass']

        # 收件人邮箱账号列表
        MY_USER_LIST = config['my_user_list']
    except Exception as err:
        traceback.print_exc()
        print(err)
        print("\033[0;36;41m读取配置文件错误!请检查json配置文件!\033[0m")

# 导入邮箱通知类
from MyMail import MyMail

# sock 分割符号
SPLIT_MARK = '♪あ♚'.encode()

class Log_Server():
    """ 日志服务端 """
    def __init__(self, client_ip_dict=None, log_file_path=None):
        """ 初始化 """
        # 数据库驱动程序错误变量
        self.sql_err_num = 0

        # 检查进程
        ce = Check_Exe()
        ce.check()
        # client_ip_dict是内网为key,公网为values
        if client_ip_dict:
            self.client_ip_dict = client_ip_dict
            self.client_ip_list = list(client_ip_dict.values())
        else:
            self.client_ip_list = CLIENT_IP_LIST
            self.client_ip_dict = dict(zip(CLIENT_IP_LIST_LOCAL, CLIENT_IP_LIST))

        if log_file_path:
            self.log_file_path = log_file_path
        else:
            self.log_file_path = os.path.join('.', 'server_log.db')

        """ 初始化GUI """
        self.lsg = LogServerGui(self, CLIENT_NAME_LIST, self.client_ip_dict, PASSWORD)
        # 注册GUI函数
        self.insert_log_gui = self.lsg.insert_log
        self.refresh_client_info = self.lsg.refresh_client_info

        """ 系统参数 """
        # mail
        self.MyMailM = MyMail(SMTP_SERVER_IP, SMTP_SERVER_PORT, MY_SENDER, MY_PASS, MY_USER_LIST)
        # sock字典
        self.sock_dict = dict()
        # sock锁字典
        self.sock_lock_dict = dict()
        # 发送数据queue队列dict
        self.send_data_queue_dict = dict()

        # 系统警告音队列
        self.war_sound_queue = queue.Queue()

        # 运行警告音线程函数服务
        self.sys_war_sound_thr()

        """ 运行日志服务端 """
        self.server_connect_fun()

        # 运行GUI
        self.lsg.run()

    """ 系统函数 """
    def sys_war_sound_thr(self):
        """ 发出系统警告音线程 """
        def war_sub():
            while True:
                try:
                    # 每get一个值就发出一次警告音
                    self.war_sound_queue.get()
                    # winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                    # winsound.Beep(800, 300)
                    winsound.PlaySound("data/err.wav", 1)
                except Exception as err:
                    print("发出警告音失败!")
                    traceback.print_exc()
                    print(err)

        war_th = threading.Thread(target=war_sub)
        war_th.setDaemon(True)
        war_th.start()

    """ 用户函数 """
    def insert_log(self, log_data):
        """ 插入一条日志 """
        #  {'ip': '192.168.0.174', 'type': 'log', 'uuid': '22106c70-159a-11ea-a266-005056c00008', 'log_id': '34004', 'insert_time': '2019-12-03 14:57:12', 'info': '一站式的关键是'}
        try:
            # 连接数据
            conn = sqlite3.connect(self.log_file_path)
            # 创建游标
            cursor = conn.cursor()
            try:
                # 插入一条信息
                ip = log_data['ip']
                uuid = log_data['uuid']
                log_id = log_data['log_id']
                insert_time = log_data['insert_time']
                info = log_data['info']

                insert_sql = "INSERT INTO SERVER_LOG_TABLE (ip, uuid, log_id, insert_time, info) VALUES ('{0}', '{1}', '{2}', '{3}', '{4}')".format(ip, uuid, log_id, insert_time, info)
                cursor.execute(insert_sql)
                conn.commit()

                # 在GUI中显示
                self.insert_log_gui(ip, log_id, insert_time, info)
            finally:
                # 关闭连接
                conn.close()
                return 0
        # except pyodbc.InterfaceError as err:
        #     # 原来是odbc, sqlite是没有这个错误的, 这段注释
        #     self.sql_err_num += 1
        #     if self.sql_err_num % 30 == 0 or self.sql_err_num == 1:
        #         # 第一次或者每30次
        #         self.insert_log_gui('localhost', 14404, datetime.now(), '未发现数据源名称并且未指定默认驱动程序!')
        #     print("{0}: \033[0;36;41m未发现数据源名称并且未指定默认驱动程序!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        #     traceback.print_exc()
        #     print(err)
        #     return 1
        except Exception as err:
            self.sql_err_num += 1
            if self.sql_err_num % 30 == 0 or self.sql_err_num == 1:
                # 第一次或者每30次
                self.insert_log_gui('localhost', 14404, datetime.now(), '服务端插入日志数据库失败!')
            print("{0}: \033[0;36;41m服务端插入日志数据库失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            traceback.print_exc()
            print(err)
            return 1

    def send_heart(self):
        """ 发送服务端(监控端)心跳数据 """
        def sub_thr():
            # 从启动后10s后才开始发送
            time.sleep(10)
            while True:
                for send_queue in self.send_data_queue_dict.values():
                    data = {
                        'type' : 'heart',
                        'date' : datetime.now().strftime('%Y-%m-%d %H:%M:%S'),

                    }
                    # 发送一个时间字符串
                    send_queue.put(data)
                # 每30s发送一次
                time.sleep(30)

        send_heart_th = threading.Thread(target=sub_thr)
        send_heart_th.setDaemon(True)
        send_heart_th.start()

    def server_connect_fun(self):
        """ 服务端监听函数 """
        def client_thr():
            """ 客户端线程函数 """
            def tcplink(client_ip, client_port):
                """ 为每个客户端分配一个线程 """
                """ 系统参数 """
                # 获取sock锁
                self.sock_lock_dict[client_ip] = threading.Lock()
                # 发送数据队列
                send_data_queue = queue.Queue()
                self.send_data_queue_dict[client_ip] = send_data_queue
                # 日志处理队列
                log_data_queue = queue.Queue()
                # 客户端系统信息处理队列
                client_info_queue = queue.Queue()

                def get_sock(client_ip, client_port):
                    """ 连接客户端返回sock """
                    while True:
                        """ 循环连接客户端 """
                        self.sock_lock_dict[client_ip].acquire()
                        try:
                            try:
                                # 取出sock
                                sock = self.sock_dict[client_ip]
                                test_data = {
                                    # 消息类型
                                    'type' : 'test',
                                }
                                # 序列化
                                data = pickle.dumps(test_data)
                                # 在消息尾部加上分割符号
                                data += SPLIT_MARK
                                # 发送数据
                                sock.sendall(data)
                            except Exception:
                                # 出错才获取新的
                                # IPv4
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.connect((client_ip, client_port))
                                # 发送密码
                                sock.sendall(PASSWORD)
                                # 保存sock
                                self.sock_dict[client_ip] = sock
                            else:
                                print("{0}: \033[0;36;42m客户端已经连接 IP: {1}\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                        except (ConnectionRefusedError, ConnectionResetError, TimeoutError):
                            print("{0}: \033[0;36;42m连接客户端失败! IP: {1}\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            time.sleep(10)
                        except Exception as err:
                            print("{0}: \033[0;36;41m连接客户端错误! IP: {1}\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            traceback.print_exc()
                            print(err)
                            time.sleep(10)
                            print("{0}: 正在重新连接客户端..".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                        else:
                            print("{0}: \033[0;36;44m客户端连接成功! IP: {1}\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            break
                        finally:
                            self.sock_lock_dict[client_ip].release()

                """ 发送和接受函数 """
                def send_data(client_ip):
                    """ 发送服务端数据线程 """
                    while True:
                        """ 循环读数据库并发送到客户端上 """
                        try:
                            # 从字典取出sock
                            sock = self.sock_dict[client_ip]
                            # 从队列获取数据
                            get_data = send_data_queue.get()
                            # 序列化
                            data = pickle.dumps(get_data)
                            # 在消息尾部加上分割符号
                            data += SPLIT_MARK
                            # 发送数据
                            sock.sendall(data)

                        except (ConnectionResetError,):
                            print("{0}: IP: {1} 客户端端断开连接!正在重连!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            get_sock(client_ip, client_port)
                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m发送数据错误!正在重连!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            traceback.print_exc()
                            print(err)
                            get_sock(client_ip, client_port)
                        else:
                            try:
                                data_type = get_data['type']
                                if data_type == 'recv_uuid':
                                    print("{0}: \033[0;36;44m  \033[0m re_send_uuid: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), get_data['uuid']))
                                elif data_type == 'heart':
                                    # 发送心跳就忽略
                                    pass
                                else:
                                    print("\033[0;36;44m{0}: 发送未识别类型数据!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                                    print(get_data)
                            except Exception as err:
                                print("\033[0;36;41m打印日志错误!\033[0m")
                                traceback.print_exc()
                                print(err)

                def recv_data(client_ip):
                    """ 接受客户端数据 """
                    # 数据缓存
                    all_sock_data = b''
                    while True:
                        """ 循环接收数据 """
                        try:
                            # 从字典取出sock
                            sock = self.sock_dict[client_ip]
                            # 把接受的数据添加到缓存后
                            all_sock_data += sock.recv(512)

                            while True:
                                # 循环处理分割数据
                                # 然后slpit一次数据
                                sock_data_list = all_sock_data.split(SPLIT_MARK, 1)
                                if len(sock_data_list) == 1:
                                    # 数据还未接受完
                                    all_sock_data = sock_data_list[0]
                                    break
                                else:
                                    # 有两个数据
                                    # 第一个数据是切割好的bytes数据
                                    re_data = sock_data_list[0]
                                    # 第二个数据是还未接受完的数据或者刚好为空
                                    all_sock_data = sock_data_list[1]

                                    # 处理接受好的re_data数据
                                    data = pickle.loads(re_data)

                                    # 根据这个数据的类型,把之交给特定的线程处理
                                    # 获取数据类型
                                    data_type = data['type']
                                    if data_type == 'log':
                                        log_data_queue.put(data)
                                        print("{0}: \033[0;30;43m  \033[0m recv_log: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data['uuid']))
                                    elif data_type == 'heart':
                                        client_info_queue.put(data)
                                        print("{0}: \033[0;30;43m  \033[0m recv_heart: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data['ip']))
                                    else:
                                        print("{0}: \033[0;36;42m收到未注册类型数据!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                                        print(data)

                        except (ConnectionResetError,):
                            print("{0}: IP: {1} \033[0;36;42m客户端断开连接!正在重新连接\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            # 获取sock
                            get_sock(client_ip, client_port)
                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m接受数据错误!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            traceback.print_exc()
                            print(err)
                            # 尝试重新连接
                            # 获取sock
                            get_sock(client_ip, client_port)

                """ 用户功能函数 """
                def log_do():
                    """ 处理日志函数 """
                    while True:
                        try:
                            log_data = log_data_queue.get()
                            # TODO 处理日志
                            # 插入数据库
                            if self.insert_log(log_data) == 0:
                                # 等于0表示插入数据库成功才进行回报

                                # 获取uuid
                                uuid = log_data['uuid']

                                # 构造返回字典
                                data = {
                                    'type': 'recv_uuid',
                                    'uuid': uuid,
                                }

                                # 发送数据
                                send_data_queue.put(data)

                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m日志处理错误!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            traceback.print_exc()
                            print(err)

                def client_info_do():
                    """ 客户端信息处理函数 """
                    while True:
                        try:
                            client_info_dict = client_info_queue.get()
                            # TODO 客户端信息处理
                            # 在GUI中显示
                            self.refresh_client_info(client_info_dict)
                            print(client_info_dict)
                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m日志处理错误!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), client_ip))
                            traceback.print_exc()
                            print(err)

                """ 运行客户端处理逻辑 """
                # 获取sock(更新字典)
                get_sock(client_ip, client_port)

                th1 = threading.Thread(target=send_data, args=(client_ip,))
                th1.setDaemon(True)
                th1.start()

                th2 = threading.Thread(target=recv_data, args=(client_ip,))
                th2.setDaemon(True)
                th2.start()

                th3 = threading.Thread(target=log_do)
                th3.setDaemon(True)
                th3.start()

                th4 = threading.Thread(target=client_info_do)
                th4.setDaemon(True)
                th4.start()

            print("{0}: 服务端启动..".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            for client_ip in self.client_ip_list:
                # 创建新线程来处理TCP连接:
                client_th = threading.Thread(target=tcplink, args=(client_ip, PORT))
                client_th.setDaemon(True)
                client_th.start()

        # 先启动心跳服务
        self.send_heart()

        server_th = threading.Thread(target=client_thr)
        server_th.setDaemon(True)
        server_th.start()
