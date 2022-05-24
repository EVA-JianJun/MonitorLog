#!/usr/bin/env python
# -*- coding: utf-8 -*-
import MonitorLog

if __name__ == '__main__':

    Mlog = MonitorLog.Log()

    Mlog.logid(404)

    Mlog.logid(10002)

    Mlog.log("TEST INFO!", 20001)
