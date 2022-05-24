#!/usr/bin/env python
# -*- coding: utf-8 -*-
import smtplib
import traceback
from email.mime.text import MIMEText
from email.utils import formataddr
from datetime import datetime

#  my_sender='910377594@qq.com'    # 发件人邮箱账号
#  my_pass = ''          # 发件人邮箱授权码
#  my_user_list=['910377594@qq.com']     # 收件人邮箱账号，我这边发送给自己

class MyMail():

    def __init__(self, smtp_server_ip, smtp_server_port, my_sender, my_pass, my_user_list):
        """ 初始化 """
        if smtp_server_ip:
            # 邮箱服务器列表不为空
            self.my_sender = my_sender
        else:
            # 否则禁用邮箱功能
            self.sendmail = lambda x : x

        """ 记录服务器参数 """
        self.smtp_server_ip = smtp_server_ip
        self.smtp_server_port = smtp_server_port
        self.my_sender = my_sender
        self.my_pass = my_pass

        # 服务器信息长度
        server_len_n = len(self.smtp_server_ip)

        def generate_server_info(server_len_n):
            while True:
                for i in range(server_len_n):
                    yield self.smtp_server_ip[i], self.smtp_server_port[i], self.my_sender[i], self.my_pass[i]

        # smtp服务器信息获取生成器
        self.get_server_info = generate_server_info(server_len_n)

        # 收信用户列表
        self.my_user_list = my_user_list

    def sendmail(self, info='MonitorLogMail 邮箱测试'):
        """ 发送邮件 """
        if info.find("</p>") >= 0:
            # 以p标签判断该信息是否为html
            print("send html mail:\n{0}".format(info))
            return self.sendmail_html(info)
        else:
            print("send mail:\n{0}".format(info))
            # 普通邮件
            try:
                # 使用生成器获取smtp服务器信息
                smtp_server_ip, smtp_server_port, my_sender, my_pass = next(self.get_server_info)

                server = smtplib.SMTP_SSL(smtp_server_ip, smtp_server_port)  # 发件人邮箱中的SMTP服务器，端口是25
                try:
                    server.login(my_sender, my_pass)  # 括号中对应的是发件人邮箱账号、邮箱密码

                    for my_user in self.my_user_list:
                        msg=MIMEText(info, 'plain', 'utf-8')
                        # 括号里的对应发件人邮箱昵称、发件人邮箱账号
                        msg['From']=formataddr(["MonitorLogMail", my_sender])
                        # 括号里的对应收件人邮箱昵称、收件人邮箱账号
                        msg['To']=formataddr(["User", my_user])
                        # 邮件的主题，也可以说是标题
                        msg['Subject']="MonitorLog 日志通知"

                        server.sendmail(my_sender, [my_user], msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
                finally:
                    server.quit()  # 关闭连接
            except Exception as err:
                traceback.print_exc()
                with open('mail_log.log', 'a') as fa:
                    print(datetime.now(), err, file=fa)
                print(err)
                return False
            else:
                return True

    def sendmail_html(self, info='MonitorLogMail 邮箱测试'):
        """ 发送html邮件 """
        try:
            # 使用生成器获取smtp服务器信息
            smtp_server_ip, smtp_server_port, my_sender, my_pass = next(self.get_server_info)

            server = smtplib.SMTP_SSL(smtp_server_ip, smtp_server_port)  # 发件人邮箱中的SMTP服务器，端口是25
            try:
                server.login(my_sender, my_pass)  # 括号中对应的是发件人邮箱账号、邮箱密码

                for my_user in self.my_user_list:
                    msg=MIMEText(info, 'html', 'utf-8')
                    # 括号里的对应发件人邮箱昵称、发件人邮箱账号
                    msg['From']=formataddr(["MonitorLogMail", my_sender])
                    # 括号里的对应收件人邮箱昵称、收件人邮箱账号
                    msg['To']=formataddr(["User", my_user])
                    # 邮件的主题，也可以说是标题
                    msg['Subject']="MonitorLog 日志通知"

                    server.sendmail(my_sender, [my_user], msg.as_string())  # 括号中对应的是发件人邮箱账号、收件人邮箱账号、发送邮件
            finally:
                server.quit()  # 关闭连接
        except Exception as err:
            traceback.print_exc()
            with open('mail_log.log', 'a') as fa:
                print(datetime.now(), err, file=fa)
            print(err)
            return False
        else:
            return True
