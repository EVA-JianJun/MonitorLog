#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import time
import random
import psutil
import socket
import threading
import traceback
import portalocker
from datetime import datetime, timedelta
from subprocess import Popen

lock_path = os.path.join(sys.exec_prefix, 'MonitorLog_TMP', 'Tmp_FileLock_File')
if not os.path.isdir(lock_path):
    # 文件锁目录不存在
    os.makedirs(lock_path)

def run_with_lock_file(file_code, func, func_args=(), timeout=300):
    """ 使用文件锁运行一个函数 """
    try:
        with portalocker.Lock(os.path.join(sys.exec_prefix, 'MonitorLog_TMP', 'Tmp_FileLock_File', file_code), 'w', timeout=timeout) as fh:
            try:
                # do what you need to do
                return func(*func_args)
            except Exception as err:
                print("运行文件锁用户函数失败!")
                traceback.print_exc()
                print(err)
            finally:
                # flush and sync to filesystem
                fh.flush()
                os.fsync(fh.fileno())
    except Exception as err:
        print("运行文件锁函数失败!")
        traceback.print_exc()
        print(err)

START_LOCK = threading.Lock()

# 守护线程检查时间间隔
CHECK_FREQUENCE = 60
# 日志进程超时重启限制, 25个小时必须重启一次
SERVER_TIMEOUT = 90000
# 守护线程随机时间上限秒
RANDOM_MAX_NNN = 300
# 下面三个是每天的重启时间
RESTART_HOUR = 3
RESTART_MINUTE = 30
RESTART_SECOND = 0

class client_server():

    def cheak_starus(self):
        """ 检查进程状态 """
        try:
            # 检查命令行
            run_flag = True
            for pid in psutil.pids():
                try:
                    p = psutil.Process(pid)
                    if 'client_server_flag' in p.cmdline():
                        # 说明进程中已经有日志客户端进程了
                        # 可能是新进程,也可能是进程自身
                        # 那么就不用启动了
                        run_flag = False
                except Exception:
                    # 可能是不能访问的进程
                    pass
            return run_flag
        except Exception as err:
            print("{0}: \033[0;36;41m检查日志进程状态错误!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            traceback.print_exc()
            print(err)
            # 检查出错默认为进程存在,不要重复启动
            return True

    def start(self):
        """ 启动日志客户端 """
        # 启动前加锁
        START_LOCK.acquire()
        try:
            # 获取本机内网ip
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
                s.close()
            except Exception:
                ip = "ERR IP"

            print("{0}: \033[0;36;44m日志进程启动! IP: {1} PORT: 12701\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), ip))
            if self.cheak_starus():
                # python 目录
                py_path = sys.exec_prefix
                # 日志客户端文件目录
                log_path = os.path.join(py_path, 'Lib', 'site-packages', 'MonitorLog', 'MonitorLog_log_client.log')
                # 日志客户端脚本运行cmd
                client_cmd = 'python ' + '"' + os.path.join(py_path, 'Lib', 'site-packages', 'MonitorLog', 'client', 'run_client.py') + '"' + ' client_server_flag'

                """ 运行日志客户端 """
                with open(log_path, 'a') as log_file:
                    # 输出到文件中
                    Popen(client_cmd, bufsize=0, stdout=log_file, stderr=log_file)
                    #  client_pro = Popen(client_cmd, bufsize=0)
            else:
                print("{0}: \033[0;36;41m启动日志进程的时候发现日志进程存在!不进程启动!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        except Exception as err:
            print("{0}: \033[0;36;41m日志进程启动失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            traceback.print_exc()
            print(err)
        finally:
            START_LOCK.release()

    def stop(self):
        """ 结束日志客户端 """
        try:
            print("{0}: \033[0;36;44m日志进程停止!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            for pid in psutil.pids():
                try:
                    p = psutil.Process(pid)
                    if 'client_server_flag' in p.cmdline():
                        # 找到日志进程,并结束
                        p.terminate()
                except Exception:
                    # 可能是不能访问的进程
                    pass
        except Exception as err:
            print("{0}: \033[0;36;41m日志进程停止失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            traceback.print_exc()
            print(err)

    def restart(self, replace=True):
        """ 重启日志进程 """
        # 这个函数运行过一次会重复的运行
        # 停止
        self.stop()
        # 启动, 每次启动全电脑只能同时运行一个进程
        run_with_lock_file('log_client_run', self.start)
        if replace:
            # 启动新的计时器运行本函数，可以重复的重启
            now = datetime.now()
            # 在凌晨3点30的时候重启
            now_0330 = now.replace(hour=RESTART_HOUR, minute=RESTART_MINUTE, second=RESTART_SECOND, microsecond=0)
            if now < now_0330:
                # 如果当前时间在0330之前,那么计算到这个0340的秒数
                sleep_t = now_0330.timestamp() - now.timestamp()
            else:
                # 时间在0330之后了,那么0330加一天,变到now之后,然后计算到这个未来的0330之间秒数
                now_0330 += timedelta(days=1)
                sleep_t = now_0330.timestamp() - now.timestamp()

            # 下一次3:30重启日志进程
            timer = threading.Timer(sleep_t, self.restart)
            timer.setDaemon(True)
            timer.start()

    def daemon(self):
        """ 日志进程守护线程 """
        def sub():
            # 随机暂停, 防止所有进程运行到同一个时刻检测
            time.sleep(random.randint(0, RANDOM_MAX_NNN))
            # 记录守护线程运行, 一个python进程只运行一个守护线程
            daemon_flag = True
            try:
                if sys.log_server_daemon_pid == os.getpid():
                    # 已经存在,就不运行了
                    print("守护进程存在! 不会启动了!")
                    daemon_flag = False
            except AttributeError:
                # 不存在赋值可以运行
                print("守护进程不存在! 第一次启动!")
                sys.log_server_daemon_pid = os.getpid()
            if daemon_flag:
                run_n = 0
                while True:
                    run_n += 1
                    if self.cheak_starus():
                        print("{0}: \033[0;36;41m日志进程不存在,正在重启!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                        try:
                            # 说明没有日志进程就启动(不重复运行每天重启逻辑)
                            self.restart(replace=False)
                        except Exception as err:
                            print("{0}: \033[0;36;41m日志进程重启失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                            traceback.print_exc()
                            print(err)
                            # 10s 后再次尝试
                            time.sleep(15)
                            continue
                    else:
                        if run_n % 10 == 0:
                            # 每10分钟打印一次
                            # print("日志进程已经存在,Daemon不启动进程!")
                            # 重置
                            run_n = 0

                            # 检查日志进程的运行时间
                            for pid in psutil.pids():
                                try:
                                    p = psutil.Process(pid)
                                    if 'client_server_flag' in p.cmdline():
                                        # 找到日志进程了
                                        break
                                except Exception:
                                    # 可能是不能访问的进程
                                    pass

                            if time.time() - p.create_time() > SERVER_TIMEOUT:
                                # 日志运行时间过长, 正在重启
                                print("{0}: \033[0;36;41m日志运行时间过长({1}s), 正在重启..!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), time.time() - p.create_time()))
                                try:
                                    # 说明没有日志进程就启动(不重复运行每天重启逻辑)
                                    self.restart(replace=False)
                                except Exception as err:
                                    print("{0}: \033[0;36;41m日志进程重启失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                                    traceback.print_exc()
                                    print(err)
                                    # 10s 后再次尝试
                                    time.sleep(15)
                                    continue
                            # else:
                            #     print("日志进程运行未超时!")

                    # 正常每分钟检查一次
                    time.sleep(CHECK_FREQUENCE)

        th = threading.Thread(target=sub)
        th.setDaemon(True)
        th.start()

    def auto_run_client(self):
        """ 重启 """
        if self.cheak_starus():
            # 先检查状态, 没有日志进去才启动
            self.restart()

        # 启动守护线程
        self.daemon()

cs = client_server()
# 自动运行
cs.auto_run_client()
