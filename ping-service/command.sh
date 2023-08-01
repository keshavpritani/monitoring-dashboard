#!/bin/bash
nohup rsyslogd </dev/null >/dev/null 2>&1 &
python /app/ping/manage.py runserver 0.0.0.0:80
