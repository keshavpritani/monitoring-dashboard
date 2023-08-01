#!/bin/bash
# APPNAME=$1
nohup rsyslogd </dev/null >/dev/null 2>&1 &
python /app/${APPNAME}/manage.py runserver 0.0.0.0:8000
