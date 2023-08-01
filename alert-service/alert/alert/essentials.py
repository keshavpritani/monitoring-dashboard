import json
import logging
import os
import ssl
import sys
import threading
import traceback
from datetime import datetime, timedelta
from pprint import pprint
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
formatter = logging.Formatter("alerts - | %(levelname)s | %(message)s")

stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setLevel(logging.DEBUG)
stdout_handler.setFormatter(formatter)

file_handler = logging.FileHandler("status.log")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stdout_handler)

current_file_name = os.path.basename(__file__)

def return_403():
    status_page_url = get_property("STATUS_PAGE_URL")
    return redirect(f"{status_page_url}/status/403/",status=403)

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
        logger.error(f"{current_file_name} - send_exection_alert - {traceback.format_exc()}")

def local_check(user):
    if ENV == "local" or ENV == "dev": return True
    if user.is_authenticated: return True
    return False

def is_allowed(ip):
    allowed_ips = json.loads(get_property("SILENT_ALERT_ALLOWED_IPS"))
    if ENV not in ("local") and allowed_ips and ip not in allowed_ips:
        logger.error(f"{current_file_name} - is_allowed - IP not allowed - ip - {ip}")
        return False, HttpResponse("Not allowed", status=403)
    return True, f"IP - {ip}"

def get_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for: ip = x_forwarded_for.split(",")[0]
    else_ip = request.META.get("REMOTE_ADDR")
    return ip, else_ip

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

all_silent = False # this is for silent of all the alert
is_silent = False # this is for silent partiular alert
release_silent = False # this if for silent variable at the time of release
silent_at = datetime.now()
silent_by = "SYSTEM"

ENV = properties["ENV"]
logger.info(f"{current_file_name} - started for {ENV}")

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

categories = json.loads(get_property("ALERTS_CATEGORY"))

def update_property(key, value):
    try:
        cursor = connection.cursor()
        cursor.execute(f"UPDATE status.properties SET property_value = '{value}' WHERE property_key = '{key}';")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in Updating property")
    finally:
        if connection:
            cursor.close()
            connection.close()

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

remove_alert_from_dict_last_checked = None

def remove_alert_from_dict():
    global remove_alert_from_dict_last_checked
    remove_alert_from_dict_last_checked = datetime.now()
    time = 6 * 60
    try:
        for key in list(last_alert_time.keys()):
            if (datetime.now() - last_alert_time[key]["last_alert_came"]).total_seconds() >= time: del last_alert_time[key]
    except:
        send_exection_alert("Error in Removing alerts")
    logger.info(f"---------------- remove_alert_from_dict - {last_alert_time} ------------------")
    # sleep(time)
    threading.Timer(time, remove_alert_from_dict).start()
    # remove_alert_from_dict()

threading.Thread(target=remove_alert_from_dict).start()

silent_alert_notification_last_checked = datetime.now()
silent_alert_notification_time = 30 * 60

def silent_alert_notification():
    global all_silent, silent_at, is_silent, silent_by, release_silent, silent_alert_notification_last_checked, silent_alert_notification_time
    silent_alert_notification_last_checked = datetime.now()
    # sleep(30 * 60)
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM status.alert_silent;")
        rows = cursor.fetchall()
        is_silent = len(rows) > 0
        now = datetime.now()
        if now.hour == 0:
            logger.info("Resetting Silent Time Properties")
            update_property("SPECIFIC_SILENT_TIME", 30)
            update_property("RELEASE_SILENT_TIME", 120)

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in silent_alert_notification")
    finally:
        if connection:
            cursor.close()
            connection.close()
    logger.info(f"Checking for Silent alert is {is_silent} - All silent - {all_silent} - Release silent - {release_silent}")
    if all_silent or is_silent or release_silent:
        delta = (datetime.now() - silent_at).total_seconds() // 60
        alert = False
        if delta >= 15: alert = True
        else:
            logger.info(f"Sleeping for Checking Silent Alert for {15 - delta + 1}")
            sleep((15 - delta + 1) * 60)
            delta = (datetime.now() - silent_at).total_seconds() // 60
            alert = all_silent or is_silent or release_silent
        if alert: slack("Alerts are silent for {} minutes (Done by {})".format(delta, silent_by))
    threading.Timer(silent_alert_notification_time, silent_alert_notification).start()
    # silent_alert_notification()

if ENV != "local": threading.Timer(silent_alert_notification_time, silent_alert_notification).start()


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


def toggle_silent_alert_calling(username="SYSTEM", status="False", minutes=30):
    global all_silent, silent_at, is_silent, silent_by, release_silent, last_alert_time
    try:
        cursor = connection.cursor()
        cursor.execute("delete from status.alert_silent;")
        connection.commit()
        last_alert_time.clear()
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in deleting alert silent")
    finally:
        if connection:
            cursor.close()
            connection.close()
    old_silent = is_silent
    is_silent = all_silent = status.lower() in ["true", "1", "t", "y", "yes", "disable", "stop", "silent"]
    if old_silent != is_silent: 
        silent_at = datetime.now()
        silent_by = username
    else: return HttpResponse("No change in silent alert status, Silent alert is {}".format(all_silent),status=304)
    logger.info("Silent alert is {} by {}".format(all_silent, username))
    if is_silent: threading.Timer(minutes * 60, toggle_silent_alert_calling,args=(username,"False",minutes)).start()
    else: release_silent = is_silent
    extra_msg = f"Changed by {username}"
    if is_silent: extra_msg = f"{extra_msg} for {minutes} minutes"
    insert_audit_log("silent_alert-all", all_silent, extra_msg)
    return HttpResponse("Silent alert is {}".format(all_silent))

toggle_silent_alert_calling()

def unsilent_specific_alert(service_name, user_name):
    global is_silent, silent_at, silent_by, release_silent
    if not is_silent: return
    logger.info("Unsilent alert for {} by {}".format(service_name, user_name))
    try:
        cursor = connection.cursor()
        cursor.execute(
            f"DELETE FROM status.alert_silent where service_name = '{service_name}';"
        )
        insert_audit_log(
             f"silent_alert-{service_name}", "False", f"Changed by {user_name}"
        )
        connection.commit()
        cursor.execute("SELECT * FROM status.alert_silent;")
        rows = cursor.fetchall()
        old_silent = is_silent
        is_silent = len(rows) > 0
        if old_silent != is_silent: 
            silent_at = datetime.now()
            silent_by = user_name
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in inserting alert silent")


def is_alert_silet(key, category):
    global is_silent, all_silent
    if is_silent:
        logger.info("Silent alert is on")
        try:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT * FROM status.alert_silent where service_name = '{key}' or service_name = 'category-{category}';"
            )
            rows = cursor.fetchall()
            if len(rows) > 0:
                return True
        except (Exception, psycopg2.Error) as error:
            send_exection_alert("Error in checking alert silent")
        finally:
            if connection:
                cursor.close()
                connection.close()
    return all_silent

def send_alert(key, status, category, extra_message="", groups = [], only_groups = []):
    global release_silent, categories
    temp = extra_message.replace('\n', ' ')
    groups = ['devops'] + groups if only_groups == [] else only_groups
    groups = set(groups)
    logger.info(f"Alerting - Groups - {groups} - {key} - {status}{temp}")
    IGNORE_STARTING_ALERTS_CATEGORIES = json.loads(get_property("IGNORE_STARTING_ALERTS_CATEGORIES"))
    if ENV == "local": return
    try:
        msg = f"{key} is {status}{extra_message}"
        if ENV != "dev" and only_groups == []:
            if not release_silent or category not in IGNORE_STARTING_ALERTS_CATEGORIES: slack(msg, name="SECONDARY")
            else: logger.info("Release silent alert is on")
        if status.lower() != "green" and is_alert_silet(key, category): return
        time = 60
        if status.lower() == "red": time = 20
        last_alert_time.setdefault(key, {
            "last_alert_sent": datetime.now(), 
            "is_active": False
        })

        flag = False

        if category not in IGNORE_STARTING_ALERTS_CATEGORIES and not last_alert_time[key]["is_active"]: flag = last_alert_time[key]["is_active"] = True
        last_alert_time[key]["last_alert_came"] = datetime.now()

        if (not last_alert_time[key]["is_active"] and last_alert_time[key]["last_alert_sent"] + timedelta(minutes=10) <= datetime.now()) \
        or \
        last_alert_time[key]["last_alert_sent"] + timedelta(minutes=time) <= datetime.now(): 
            flag = last_alert_time[key]["is_active"] = True
            last_alert_time[key]["last_alert_sent"] = last_alert_time[key]["last_alert_came"]

        if ENV == "prod" or flag or status.lower() == "green":
            for group_name in groups: 
                slack(msg, group_name)
                if status.lower() == "red" and ENV == "prod":
                    whatsapp(key, group_name)
                    if group_name == "devops":
                        if category == "automation": group_name = "qa"
                        alertmanager(key, status, extra_message, group_name)
            if only_groups == []: insert_audit_log(key, status, extra_message)
        if category not in categories:
            categories = json.loads(get_property("ALERTS_CATEGORY"))
            if category not in categories:
                categories.append(category)
                categories = list(set(categories))
                update_property("ALERTS_CATEGORY", json.dumps(categories))
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in sending alert")

def slack(msg, group_name="devops", name="PRIMARY"):
    receviers = get_alert_receiver(group_name)
    if name not in receviers: raise Exception(f"Slack̉ Details not found for {group_name} - {name} in DB")
    if receviers[name] == "IGNORE": return
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
    if name not in receviers: raise Exception(f"Slack̉ Details not found for {group_name} - {name} in DB")
    if receviers[name] == "IGNORE": return
    DASHBOARD_CHANNEL = receviers[name]
    logger.info(f"Sending slack alert V2 - {group_name} - {DASHBOARD_CHANNEL} - {msg[:20]}")
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    client = WebClient(token=get_property("SLACK_BOT_TOKEN"), ssl=ssl_context)
    response = client.chat_postMessage(channel=DASHBOARD_CHANNEL, text=msg)
    print(response)


def whatsapp(app, group_name):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }
    app = app.replace(" ", "_")
    params_payload = {"msg": "Hello, {} service is down.".format(app)}
    receviers = get_alert_receiver(group_name, "whatsapp")
    if len(receviers.keys()) > 0: logger.info(f"Sending Whatapps alert - {group_name}")
    for number in receviers.values():
        requests.get(
            f"https://media.smsgupshup.com/GatewayAPI/rest?method=SendMessage&format=json&userid=2000188941&password=yFD2eUJcb&send_to={number}&v=1.1&auth_scheme=plain&msg_type=TEXT",
            headers=headers,
            params=params_payload,
        )

def alertmanager(key, status, extra_message="", group_name="devops"):
    severity = "PHONE"
    if group_name != "devops": severity = f"{severity}-{group_name}"
    alertmanager_url = "http://prometheus.kristal-internal.com:9093/api/v1/alerts"
    data = {
        "status": "firing",
        "labels": {
            "alertname": "alert-service",
            "severity": severity,
            "instance": key,
        },
        "annotations": {"summary": "{} is {}{}".format(key, status, extra_message)},
        "generatorURL": get_property("STATUS_BOARD_URL"),
    }
    requests.post(alertmanager_url, json=[data])


alert_data = {}

@csrf_exempt
def jira(request):
    if request.method == "POST":
        if request.META["HTTP_AUTHORIZATION"] != properties["JIRA_AUTH"]:
            return HttpResponse(status=401)
        data = json.loads(request.body)
        required_fields = ("title", "state", "evalMatches", "message", "ruleName")
        valid_state = ("alerting", "resolved")
        for field in required_fields:
            if field not in data.keys():
                return HttpResponse(
                    status=428, content="Missing parameters\nRequired: {}".format(field)
                )
        title = data["title"]
        state = data["state"]
        if state not in valid_state:
            return HttpResponse(
                status=404,
                content="Invalid state\nValid states: {}".format(valid_state),
            )
        rule_name = data["ruleName"]
        message = data["message"] + f", state - {state}\n\n"
        evalMatches = data["evalMatches"]
        if state != "resolved":
            if len(evalMatches) == 0:
                return HttpResponse(status=404, content="No evalMatches")
        required_fields_in_evalMatches = ("metric", "value")
        for evalMatch in evalMatches:
            for field in required_fields_in_evalMatches:
                if field not in evalMatch.keys():
                    return HttpResponse(
                        status=428,
                        content="Missing parameters\nRequired: {}".format(field),
                    )
            metric = evalMatch["metric"]
            value = evalMatch["value"]
            message += "{} is {}\n".format(metric, value)
        url = properties["JIRA_URL"]

        auth = HTTPBasicAuth(properties["JIRA_USERNAME"], properties["JIRA_APIKEY"])

        headers = {"Accept": "application/json", "Content-Type": "application/json"}

        update = False

        if rule_name in alert_data:
            update = True
            api = f"{url}/rest/api/3/issue/{alert_data[rule_name][1]}"
            response = requests.request("GET", api, headers=headers, auth=auth).json()
            print(response["fields"]["status"]["name"])
            if (
                alert_data[rule_name][0] > (datetime.now() + timedelta(days=1))
                or "Done" in response["fields"]["status"]["name"]
            ):
                del alert_data[rule_name]
                update = False
        if rule_name not in alert_data and state == "alerting":
            alert_data[rule_name] = [datetime.now(), ""]

        api = f"{url}/rest/api/3/issue"
        method = "POST"

        payload = json.dumps(
            {
                "fields": {
                    "project": {"id": properties["JIRA_PROJECT_KEY"]},
                    "issuetype": {"id": properties["JIRA_ISSUE_TYPE"]},
                    "summary": title,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"text": message, "type": "text"}],
                            }
                        ],
                    },
                    "assignee": {"id": properties["JIRA_ASSIGNEE"]},
                }
            }
        )

        if update:
            if alert_data[rule_name][1] == "":
                return HttpResponse(status=500, content="Issue ID not found")
            api = f"{url}/rest/api/3/issue/{alert_data[rule_name][1]}"
            method = "PUT"
            if state == "resolved":
                del alert_data[rule_name]

        response = requests.request(
            method, api, data=payload, headers=headers, auth=auth
        )
        if response.status_code == 201:
            if state == "alerting":
                alert_data[rule_name][1] = response.json()["key"]
            print(
                json.dumps(
                    json.loads(response.text),
                    sort_keys=True,
                    indent=4,
                    separators=(",", ": "),
                )
            )
            return HttpResponse(
                response.text,
                status=response.status_code,
                content_type="application/json",
            )
        else:
            return HttpResponse(status=response.status_code, content=response.text)
