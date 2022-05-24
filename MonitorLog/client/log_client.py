#!/use/bin/dev python
# -*- coding: utf-8 -*-
import os
import sys
import time
import queue
import psutil
import shutil
import random
import pickle
import socket
import sqlite3
import threading
import traceback
from datetime import datetime
import MonitorLog
MOULD_PATH = MonitorLog.__path__[0]
from MonitorLog.client.MessyServerHardware import MessyServerHardware

""" 连接密码 """
# 普通用户
PASSWORD = b'UHHkSVHsd7MirH'
# 管理员用户
PASSWORD_ADMIN = b'UOCP2P3KheLphV'

""" 连接端口 """
PORT = 12701

# 密码列表
PASSWORD_LIST = [PASSWORD, PASSWORD_ADMIN]

# sock 分割符号
SPLIT_MARK = '♪あ♚'.encode()

def user_get_process_status():
    """ 用户自定义进程状态监控函数 """
    # 默认返回,这个函数应该由用户自定义
    # 查找所有的python进程的数目
    try:
        python_num = 0
        for pid in psutil.pids():
            p = psutil.Process(pid)
            if p.name() == 'python.exe':
                python_num += 1
        return ['OK', 'Python {0}'.format(python_num)]
    except Exception:
        return ['OK', 'test status']

class Log_Client():
    """ 日志客户端 """
    # 负责把日志信息发送到服务端
    def __init__(self, ip=None, port=None, log_file_path=None):
        """ 用户参数 """
        self.log_file_path = "runtime_log.db"
        if log_file_path:
            self.log_file_path = log_file_path
        else:
            if not os.path.isfile("runtime_log.db"):
                runtime_log_default_file = os.path.join(MOULD_PATH, "data", "runtime_log.db")
                shutil.copyfile(runtime_log_default_file, "runtime_log.db")

        if ip:
            self._ip = ip
        else:
            # 获取本机内网ip
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                self._ip = s.getsockname()[0]
                s.close()
            except Exception:
                self._ip = "ERR IP"

        #  print("本机IP: {0}".format(self._ip))
        if port:
            self._port = port
        else:
            self._port = PORT

        """ 系统参数 """
        self.sql_lock = threading.Lock()

        # IP 黑名单
        self.ip_blacklist = set()
        # IP 错误次数字典
        self.ip_err_times_dict = dict()

        # 系统信息获取实例
        self.msh = MessyServerHardware(user_get_process_status)

        # 服务端变量字典
        self.server_variable_dict = dict()

        # 服务端类型,普通用户或者管理员
        self.server_type_dict = dict()

        # 心跳打印次数显示数
        self._print_heart_num = 0

        """ 运行日志客户端 """
        self.client_Listen_fun()

        # 让进程卡住,让线程能一直运行
        self.sleep_queue = queue.Queue()
        self.sleep_queue.get()

    def read_log(self):
        """ 读取日志 """
        self.sql_lock.acquire()
        try:
            # 连接数据
            conn = sqlite3.connect(self.log_file_path)
            # 创建游标
            cursor = conn.cursor()
            try:
                # 读取日志(只读send_flag为None的, sql中要写成null)
                select_sql = "SELECT * FROM LOG_TABLE WHERE send_flag is null"
                cursor.execute(select_sql)
                result = cursor.fetchall()
                return result
            finally:
                # 关闭连接
                conn.close()
        except Exception as err:
            print("{0}: \033[0;36;41m读取日志数据库失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
            traceback.print_exc()
            print(err, flush=True)
            return tuple()
        finally:
            self.sql_lock.release()

    def set_uuid_log(self, uuid):
        """ 设置日志uuid Flag 为Ture标志 """
        self.sql_lock.acquire()
        try:
            # 连接数据
            conn = sqlite3.connect(self.log_file_path)
            # 创建游标
            cursor = conn.cursor()
            try:
                update_sql = "UPDATE LOG_TABLE SET send_flag = 'True' WHERE uuid = '{0}'".format(uuid)
                cursor.execute(update_sql)
                conn.commit()
            finally:
                # 关闭连接
                conn.close()
        except Exception as err:
            print("{0}: uuid: {1}\033[0;36;41m更新日志数据库uuid失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), uuid), flush=True)
            traceback.print_exc()
            print(err, flush=True)
        finally:
            self.sql_lock.release()

    def client_Listen_fun(self):
        """ 客户端监听函数 """
        def client_thr():
            """ 使用线程运行 """
            def tcplink(sock, server_ip, server_port):
                """ 服务端线程函数 """

                """ 发送和接受函数 """
                # 下面两个函数负责发送客户端数据和接受服务端返回的数据,如果连接断开自动退出
                def send_data(sock):
                    """ 发送客户端数据线程 """
                    while True:
                        """ 循环读数据库并发送到客户端上 """
                        try:
                            # 从队列获取数据
                            send_data_queue = self.server_variable_dict[sock]['send_data_queue']
                            get_data = send_data_queue.get()
                            # 序列化
                            data = pickle.dumps(get_data)
                            # 在消息尾部加上分割符号
                            data += SPLIT_MARK
                            # 发送数据
                            sock.sendall(data)
                        except (ConnectionResetError,):
                            print("{0}: IP: {1} \033[0;36;41m服务端端断开连接!退出!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                            # 删除sock,好让发送消息的时候不再发送已经断开的sock
                            """
                            try:
                                del self.server_variable_dict[sock]
                            except KeyError:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except KeyError:
                                pass
                            """
                            # 关闭连接
                            try:
                                sock.shutdown(socket.SHUT_RDWR)
                            except Exception:
                                pass
                            try:
                                sock.close()
                            except Exception:
                                pass
                            # 删除变量
                            try:
                                del self.server_variable_dict[sock]
                            except Exception:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except Exception:
                                pass
                            return
                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m发送数据错误!退出!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                            traceback.print_exc()
                            print(err, flush=True)
                            # 出错就退出
                            # 关闭连接
                            # 删除sock,好让发送消息的时候不再发送已经断开的sock
                            """
                            try:
                                del self.server_variable_dict[sock]
                            except KeyError:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except KeyError:
                                pass
                            """
                            # 关闭连接
                            try:
                                sock.shutdown(socket.SHUT_RDWR)
                            except Exception:
                                pass
                            try:
                                sock.close()
                            except Exception:
                                pass
                            # 删除变量
                            try:
                                del self.server_variable_dict[sock]
                            except Exception:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except Exception:
                                pass
                            with open("log_err.log", 'a') as fa:
                                fa.write("{0}: 日志发送错误: err: {1} info: {2}\n".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), err, get_data))
                            return
                        else:
                            try:
                                """ 打印发送的信息到屏幕上 """
                                data_type = get_data['type']
                                if data_type == 'log':
                                    print("{0}: \033[0;36;44m  \033[0m send_uuid: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), get_data['uuid']), flush=True)
                                elif data_type == 'heart':
                                    self._print_heart_num += 1
                                    # 每七分钟打印一次
                                    if self._print_heart_num % 28 == 0:
                                        print("{0}: \033[0;36;44m  \033[0m send_heart: ...".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
                                else:
                                    print("\033[0;36;44m{0}: 发送未识别类型数据!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
                                    print(get_data, flush=True)
                            except Exception as err:
                                print("\033[0;36;41m打印日志错误!\033[0m", flush=True)
                                traceback.print_exc()
                                print(err, flush=True)

                def recv_data(sock):
                    """ 接收服务端数据 """
                    #  """ 接收服务端已经收到的uuid并更新数据库 """
                    # 数据缓存
                    all_sock_data = b''
                    while True:
                        """ 循环接收数据 """
                        try:
                            # 把接受的数据添加到缓存后
                            all_sock_data += sock.recv(512)

                            while True:
                                # 循环处理分割数据
                                # 然后slpit一次数据
                                try:
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
                                        data_type = data['type']
                                        if data_type == 'recv_uuid':
                                            # 收到这个表示服务端已经收到了日志
                                            log_recv_uuid = data
                                            # 处理uuid
                                            uuid = log_recv_uuid['uuid']
                                            log_recv_flag_set = self.server_variable_dict[sock]['log_recv_flag_set']
                                            # 把这个uuid添加进已经收到的uuid集合中
                                            log_recv_flag_set.add(uuid)
                                            print("{0}: \033[0;30;43m  \033[0m recv_uuid: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), data['uuid']), flush=True)
                                        elif data_type == 'heart':
                                            # 心跳信息忽略
                                            #  print("heart: {0}".format(data))
                                            pass
                                        else:
                                            # 这里是服务端发送了未知数据类型过来
                                            print("{0}: \033[0;36;42m收到未注册类型数据!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
                                            print(data, flush=True)
                                except Exception as err:
                                    print("{0}: IP: {1} \033[0;36;41m接受服务端数据分割错误!忽略错误,继续接受!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                                    traceback.print_exc()
                                    print(err, flush=True)

                        except (ConnectionResetError,):
                            print("{0}: IP: {1} \033[0;36;41m服务端端断开连接(recv)!退出!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                            # 删除sock,好让发送消息的时候不再发送已经断开的sock
                            """
                            try:
                                del self.server_variable_dict[sock]
                            except KeyError:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except KeyError:
                                pass
                            """
                            # 关闭连接
                            try:
                                sock.shutdown(socket.SHUT_RDWR)
                            except Exception:
                                pass
                            try:
                                sock.close()
                            except Exception:
                                pass
                            # 删除变量
                            try:
                                del self.server_variable_dict[sock]
                            except Exception:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except Exception:
                                pass
                            return
                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m接受数据错误!退出!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                            traceback.print_exc()
                            print(err, flush=True)
                            # 删除sock,好让发送消息的时候不再发送已经断开的sock
                            """
                            try:
                                del self.server_variable_dict[sock]
                            except KeyError:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except KeyError:
                                pass
                            """
                            # 关闭连接
                            try:
                                sock.shutdown(socket.SHUT_RDWR)
                            except Exception:
                                pass
                            try:
                                sock.close()
                            except Exception:
                                pass
                            # 删除变量
                            try:
                                del self.server_variable_dict[sock]
                            except Exception:
                                pass
                            try:
                                del self.server_type_dict[sock]
                            except Exception:
                                pass
                            return

                print('{0}: \033[0;36;44m服务端已经连接 {1}:{2}\033[0m'.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip, server_port), flush=True)
                # 接收密码,16位
                # 设置超时
                sock.settimeout(7)
                try:
                    password = sock.recv(16)
                except socket.timout:
                    # 7秒内不发送密码
                    print("{0}: 客户端连接后不发送密码! ip: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                    # 关闭连接
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    try:
                        sock.close()
                    except Exception:
                        pass
                    # 错误次数加一
                    try:
                        self.ip_err_times_dict[server_ip] += 1
                    except KeyError:
                        self.ip_err_times_dict[server_ip] = 1

                    # 退出线程
                    return
                else:
                    # 恢复超时
                    sock.settimeout(None)

                if password not in PASSWORD_LIST:
                    print("{0}: 密码错误 ip: {1}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                    # 如果密码不相等
                    try:
                        self.ip_err_times_dict[server_ip] += 1
                    except KeyError:
                        self.ip_err_times_dict[server_ip] = 1

                    # 关闭连接
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except Exception:
                        pass
                    try:
                        sock.close()
                    except Exception:
                        pass
                    # 删除变量
                    try:
                        del self.server_variable_dict[sock]
                    except Exception:
                        pass
                    try:
                        del self.server_type_dict[sock]
                    except Exception:
                        pass

                    # 判断是否已经三次失败,失败就拉黑
                    if self.ip_err_times_dict[server_ip] >= 3:
                        print("{0}: 拉黑ip: \033[0;36;42m{1}\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                        self.ip_blacklist.add(server_ip)

                    # 退出服务线程
                    return
                else:
                    print("{0}: \033[0;36;44m密码正确 ip: {1}\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                    # 密码正确正常进入逻辑
                    """ 线程系统参数 """
                    # 创建字典
                    self.server_variable_dict[sock] = dict()
                    # 发送数据队列
                    self.server_variable_dict[sock]['send_data_queue'] = queue.Queue()
                    # log发送完毕标志,uuid集合
                    self.server_variable_dict[sock]['log_recv_flag_set'] = set()

                    if password == PASSWORD_ADMIN:
                        # 管理员
                        #  print("admin")
                        self.server_type_dict[sock] = 0
                    else:
                        # 普通用户
                        #  print("Nomor")
                        self.server_type_dict[sock] = 1

                    # 启动子服务线程
                    thr1 = threading.Thread(target=send_data, args=(sock,))
                    thr1.setDaemon(True)
                    thr1.start()

                    thr2 = threading.Thread(target=recv_data, args=(sock,))
                    thr2.setDaemon(True)
                    thr2.start()

            """ 创建sock,等待连接 """
            try:
                self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_sock.bind((self._ip, self._port))
                self.client_sock.listen(5)
            except Exception:
                # 这里一般是多开检测到错误,我们就结束掉进程
                self.sleep_queue.put(1)
                sys.exit(2)

            """ 全局系统用户功能函数 """
            def send_log():
                """ 读取日志并发送 """
                while True:
                    time.sleep(10)
                    log_tuple = self.read_log()
                    # 如果没有读取到新日志,那么不会发生任何信息
                    # 每次至多发送5次
                    for log in log_tuple[:5]:
                        try:
                            uuid = log[1]
                            log_id = log[2]
                            log_dict = {
                                # 客户端ip
                                'ip': self._ip,
                                # 消息类型
                                'type' : 'log',
                                'uuid': uuid,
                                'log_id': log_id,
                                'insert_time': log[3],
                                'info': log[4],
                            }

                            if str(log_id)[-4:-3] == '7':
                                # 说明这个log为管理员消息
                                for sock_key in self.server_variable_dict:
                                    try:
                                        if self.server_type_dict[sock_key]:
                                            # 这个值为1的话说明是普通用户,普通用户是不用发送这个管理员log的,我们修改他的发送状态
                                            log_recv_flag_set = self.server_variable_dict[sock_key]['log_recv_flag_set']
                                            # 把这个uuid添加进已经收到的uuid集合中,说明这条消息假装已经发送过了
                                            # 然后下面再判断就不会发生给普通用户这个消息了
                                            log_recv_flag_set.add(uuid)
                                    except KeyError:
                                        # 关闭连接
                                        try:
                                            sock.shutdown(socket.SHUT_RDWR)
                                        except Exception:
                                            pass
                                        try:
                                            sock.close()
                                        except Exception:
                                            pass
                                        # 删除变量
                                        try:
                                            del self.server_variable_dict[sock]
                                        except Exception:
                                            pass
                                        try:
                                            del self.server_type_dict[sock]
                                        except Exception:
                                            pass

                            for sock_key in self.server_variable_dict:
                                # 先提取uuid set
                                log_recv_flag_set = self.server_variable_dict[sock_key]['log_recv_flag_set']
                                if uuid in log_recv_flag_set:
                                    # 如果要发送的这个uuid在已经发送过的set中就不用发送了
                                    pass
                                else:
                                    # 所有连接的服务端都发送数据
                                    send_data_queue = self.server_variable_dict[sock_key]['send_data_queue']
                                    # 循环所有连接,put进去
                                    send_data_queue.put(log_dict)
                        except Exception as err:
                            print("{0}: IP: {1} \033[0;36;41m发送日志错误!退出!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                            traceback.print_exc()
                            print(err, flush=True)

            def send_heart():
                """ 发送客户端信息 """
                time.sleep(random.random() * 5)
                while True:
                    try:
                        time.sleep(15)
                        data_dict = {
                            # 客户端ip
                            'ip': self._ip,
                            # 消息类型
                            'type' : 'heart',
                            # 获取系统信息
                            'client_info': self.msh.get_all(),
                        }

                        for sock_key in self.server_variable_dict:
                            # 循环所有连接,put进去
                            #  print(sock_key)
                            send_data_queue = self.server_variable_dict[sock_key]['send_data_queue']
                            send_data_queue.put(data_dict)
                    except Exception as err:
                        print("{0}: IP: {1} \033[0;36;41m发送日志错误!退出!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                        traceback.print_exc()
                        print(err, flush=True)

            def set_log_flag():
                """ 根据服务端回报修改数据库发送标志为True """
                while True:
                    try:
                        # 发送线程10s运行一次,检查线程5秒运行一次
                        time.sleep(5)

                        # 查找所有的sock都有的uuid
                        same_uuid_set = set()
                        for sock_key in self.server_variable_dict:
                            # 提取uuid集合
                            log_recv_flag_set = self.server_variable_dict[sock_key]['log_recv_flag_set']
                            # 先提取
                            same_uuid_set = same_uuid_set | log_recv_flag_set

                        for sock_key in self.server_variable_dict:
                            # 提取uuid集合
                            log_recv_flag_set = self.server_variable_dict[sock_key]['log_recv_flag_set']
                            # 然后查找共同都有的元素
                            same_uuid_set = same_uuid_set & log_recv_flag_set

                        for uuid in same_uuid_set:
                            # 共同的uuid,然后设置数据库转态为True
                            # 设置uuid标志
                            self.set_uuid_log(uuid)

                        for uuid in same_uuid_set:
                            for sock_key in self.server_variable_dict:
                                # 提取uuid集合
                                log_recv_flag_set = self.server_variable_dict[sock_key]['log_recv_flag_set']
                                # 然后从收到的uuid集合中把已经全部收到的uuid给删除
                                log_recv_flag_set.remove(uuid)

                        #  print("debug", self.server_variable_dict)
                    except Exception as err:
                        print("{0}: IP: {1} \033[0;36;41m日志recv uuid处理错误!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), server_ip), flush=True)
                        traceback.print_exc()
                        print(err, flush=True)

            # 运行线程
            thr3 = threading.Thread(target=send_log)
            thr3.setDaemon(True)
            thr3.start()

            thr4 = threading.Thread(target=send_heart)
            thr4.setDaemon(True)
            thr4.start()

            thr5 = threading.Thread(target=set_log_flag)
            thr5.setDaemon(True)
            thr5.start()

            print("{0}: 等待服务端连接..".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), flush=True)
            while True:
                try:
                    # 接受一个新连接:
                    sock, addr = self.client_sock.accept()

                    server_ip = addr[0]
                    server_port = addr[1]

                    if server_ip in self.ip_blacklist:
                        # 如果在黑名单里
                        sock.shutdown(socket.SHUT_RDWR)
                        sock.close()
                        continue

                    # 创建新线程来处理TCP连接:
                    server_thr = threading.Thread(target=tcplink, args=(sock, server_ip, server_port))
                    server_thr.setDaemon(True)
                    server_thr.start()
                except Exception as err:
                    print("\033[0;36;41m日志客户端线程启动失败!\033[0m", flush=True)
                    traceback.print_exc()
                    print(err, flush=True)

        client_th = threading.Thread(target=client_thr)
        client_th.setDaemon(True)
        client_th.start()
