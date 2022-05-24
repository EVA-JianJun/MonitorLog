#!/use/bin/dev python
# -*- coding: utf-8 -*-
import os
import uuid
import shutil
import sqlite3
import threading
import traceback
import MonitorLog
MOULD_PATH = MonitorLog.__path__[0]
from datetime import datetime

class Log():
    """ 记录日志 """
    def __init__(self, log_file_path=None):
        """ 初始化 """
        if not os.path.isfile("LOG_ID_INFO.py"):
            log_id_info_dict_default_file = os.path.join(MOULD_PATH, "log_tools", "LOG_ID_INFO.py")
            shutil.copyfile(log_id_info_dict_default_file, "LOG_ID_INFO.py")
        from LOG_ID_INFO import LOG_ID_INFO_DICT

        self.log_id_info_dict = LOG_ID_INFO_DICT

        self.log_file_path = "runtime_log.db"
        if log_file_path:
            self.log_file_path = log_file_path
        else:
            if not os.path.isfile("runtime_log.db"):
                runtime_log_default_file = os.path.join(MOULD_PATH, "data", "runtime_log.db")
                shutil.copyfile(runtime_log_default_file, "runtime_log.db")

        self.lock = threading.RLock()

    def _format_data(self, data):
        """ 格式化data,让其能插入数据库 """
        return str(data).replace("'", "''").replace('"', "''")

    def log(self, info, log_id=44404):
        """ 记录一个日志 """
        self.lock.acquire()
        try:
            # 插入时间
            insert_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # uuid
            uuid_id = uuid.uuid1()

            # 连接数据
            conn = sqlite3.connect(self.log_file_path)
            # 创建游标
            cursor = conn.cursor()
            try:
                # 插入日志
                insert_sql = "INSERT INTO LOG_TABLE (uuid, log_id, insert_time, info) VALUES ('{0}', '{1}', '{2}', '{3}')".format(uuid_id, log_id, insert_time, info)
                cursor.execute(insert_sql)
                conn.commit()
            finally:
                # 关闭连接
                conn.close()
        except Exception as err:
            # 如果数据库出问题这里会无线递归, 所以注释了
            # self.logid(14025)
            print("{0}: \033[0;36;41m日志写入数据库失败!\033[0m".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            traceback.print_exc()
            print(err)
            # 错误就写入文件
            with open('MonitorLog_err.log', 'a') as fa:
                fa.write("{0}: info: {1} log_id: {2}\n".format(insert_time, info, log_id))
        finally:
            self.lock.release()

    def logid(self, log_id):
        """ 根据log_id直接记录特定info """
        self.lock.acquire()
        try:
            info = self.log_id_info_dict[log_id]
        except KeyError:
            self.log("错误的日志ID: {0}".format(log_id), 14404)
        else:
            # 正常记录日志
            self.log(info, log_id)
        finally:
            self.lock.release()