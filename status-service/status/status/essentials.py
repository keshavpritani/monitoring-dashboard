import json
import logging
from pprint import pprint
import sys
import ssl
import threading
import traceback
from datetime import datetime, timedelta
from time import sleep

import psycopg2
import requests
from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from requests.auth import HTTPBasicAuth
from slack_sdk import WebClient


logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("| %(levelname)s | %(message)s")

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

file_handler = logging.FileHandler("status.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

last_called_time = datetime.now()

def update_last_called_time():
    global last_called_time
    last_called_time = datetime.now()

def send_exection_alert(message=""):
    try:
        logger.error(f"Exception came - {message} - {traceback.format_exc()}")
        # exp_message = sys.exc_info()[1].__str__()
        # if "canceling statement due to statement timeout" in exp_message and ENV != "prod":
        #     file_name = sys.exc_info()[2].tb_frame.f_code.co_filename
        #     line_no = sys.exc_info()[2].tb_lineno
        #     send_alert("DB_TIMEOUT", "red", "db", f", File - {file_name}:{line_no} - Message - {exp_message}")
        if ENV == "local": return
        slack(f"Exception came - {message}", name="EXCEPTION")
    except (Exception, psycopg2.Error) as error:
        logger.error(f"essentials.py - send_exection_alert - {traceback.format_exc()}")

def local_check(user):
    if user.is_authenticated: return True
    if ENV == "local" or ENV == "dev": return True
    return False

properties = {}
last_alert_time = {}

try:
    cursor = connection.cursor()
    cursor.execute(
        "select property_key, property_value from status.properties where property_key in ('AWS_REGION','ENV') or property_key ilike '%jira%';"
    )
    rows = cursor.fetchall()
    for row in rows:
        properties[row[0]] = row[1]
except (Exception, psycopg2.Error) as error:
    send_exection_alert("Error in getting properties")
finally:
    if connection:
        cursor.close()
        connection.close()

ENV = properties["ENV"]
logger.info(f"views.py - started for {ENV}")

def get_property(key):
    value = ""
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"select property_value from status.properties where property_key ilike '%{key}%';"
        )
        value = cursor.fetchone()
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in getting property")
    finally:
        if connection:
            cursor.close()
            connection.close()
    return value[0]

def get_alert_receiver(group, type="slack"):
    data = {}
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"select name,value from status.alert_receivers where group_name = '{group}' and type = '{type}';"
        )
        value = cursor.fetchall()
        for row in value:
            data[row[0]] = row[1]

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in getting alert receivers")
    finally:
        if connection:
            cursor.close()
            connection.close()
    return data

def slack(msg, group_name="devops", name="PRIMARY"):
    receviers = get_alert_receiver(group_name)
    if name not in receviers and group_name != "devops": return
    DASHBOARD_WEBHOOK = receviers[name]
    if DASHBOARD_WEBHOOK[0] == '#': return slack_v2(msg, group_name, name)
    logger.info(f"Sending slack alert - {group_name} - {name} - {msg[:20]}")
    headers = {
        "Content-type": "application/json",
    }
    data = {"text": msg}
    data = json.dumps(data)
    requests.post(
        DASHBOARD_WEBHOOK,
        data=data,
        headers=headers,
    )

def slack_v2(msg, group_name="devops", name="PRIMARY"):
    receviers = get_alert_receiver(group_name)
    if name not in receviers and group_name != "devops": return
    DASHBOARD_CHANNEL = receviers[name]
    logger.info(f"Sending slack alert V2 - {group_name} - {DASHBOARD_CHANNEL} - {msg[:20]}")
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    client = WebClient(token=get_property("SLACK_BOT_TOKEN"), ssl=ssl_context)
    response = client.chat_postMessage(channel=DASHBOARD_CHANNEL, text=msg)
    print(response)


def checking_status_page_called():
    sleep(30 * 60)
    now = datetime.now()
    silent_hours = get_property("SILENT_HOURS").split(",")
    logger.info(f"Checking for Status Page last called time")
    if str(now.hour) not in silent_hours and last_called_time < now - timedelta(minutes=10):
        logger.info("Sending alert for status page not being called")
        devops_receviers = get_alert_receiver("devops")
        WEBHOOK = devops_receviers["PRIMARY"]
        delta = now - last_called_time
        slack(f"Status Dashboard is not being called for {delta.total_seconds() // 60} minutes")
    threading.Thread(target=checking_status_page_called).start()

if ENV != "local": threading.Thread(target=checking_status_page_called).start()

def insert_audit_log(key, status, extra_message=""):
    try:
        cursor = connection.cursor()
        extra_message = extra_message[:200]
        cursor.execute("INSERT INTO status.audit_logs(service_name,status,message) values (%s,%s,%s);",
            (
                key,
                status,
                extra_message,
            )
        )
        connection.commit()
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in inserting audit logs")

def toggle_silent_alert_calling(username="SYSTEM", status="False", minutes=5):
    if ENV == "local": return
    try:
        alert_service_url = get_property("ALERT_SERVICE_URL")
        response = requests.put(f"{alert_service_url}/toggle_silent_alert/{status}/", json={
            "username": username,
            "minutes": minutes
        })
        if response.status_code != 200: send_exection_alert(f"Error while toggle_silent_alert_calling - Return Code - {response.status_code}")
    except: send_exection_alert("Error while toggle_silent_alert_calling")

def send_alert(key, status, category, extra_message="", groups=[], only_groups=[]):
    if ENV == "local": 
        logger.info(f"Got Alert for - {key} - {status} - {category} - {extra_message} - {groups} - {only_groups}")
        return
    alert_service_url = get_property("ALERT_SERVICE_URL")
    response = requests.post(f"{alert_service_url}/send-alert/", json={
        "key": key,
        "status": status,
        "category": category,
        "extra_message": extra_message,
        "groups": groups,
        "only_groups": only_groups
    })
    if response.status_code != 200: send_exection_alert(f"Error while Sending Alert - Return Code - {response.status_code}")


def call_jenkins_job(jenkins_job_name, parameters = {}, user_name = "SYSTEM"):
    Jenkins_url = get_property("JENKINS_URL")
    jenkins_user = get_property("JENKINS_USER_ID")
    jenkins_pwd = get_property("JENKINS_USER_PASSWORD")
    jenkins_params = {'token': get_property("JENKINS_TOKEN"),
                    'cause': f"Started by {user_name}"}
    jenkins_params.update(parameters)
    data = requests.post(f"{Jenkins_url}/job/{jenkins_job_name}/buildWithParameters",auth=(jenkins_user, jenkins_pwd),params=jenkins_params, timeout=30)
    if str(data.status_code) != "201": return False, f"Jenkins job is not triggered - {jenkins_job_name} - Status Code - {data.status_code}"
    return True, "Success"
