from django.shortcuts import render
import psycopg2
from django.db import connection
from django.http import JsonResponse
import requests
import json
import threading
from status.time import *
from status.queue_table import *
from status.saxo_tokens import *
from status.flex_validation import *
from status.batch_running import *
from status.essentials import *
from status.aws_instance import *
from status.docker_images import *
from status.db_status import *
from status.certificates import *
from django.template.defaulttags import register
from datetime import datetime, timedelta
from status.infraversion import *
from status.appversion import *
from status.kafka_check import *
from status.dms_check import *

ib_gateway_dict = {}


@register.filter
def get_value(dictionary, key):
    return dictionary.get(key)

@register.filter
def pretty_print_seconds(string):
    if string == "": return ""
    delta = timedelta(seconds=string)
    return str(delta).split('.')[0]


def monitor(request):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1;")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert(f"Error while connecting to PostgreSQL")
        return HttpResponse(1, status=500)
    return HttpResponse(0, status=200)

def ib_gateway_func():
    global ib_gateway_dict
    urls = {
        "IB Orders": get_property("IB_ORDERS_URL"),
        "IB Reader": get_property("IB_READER_URL"),
    }
    logger.info(f"Checking IB Gateway Status - {','.join(urls.values())}")
    ib_gateway_update = {}
    for type, url in urls.items():
        data_str = requests.get(url)
        if data_str.status_code != 200:
            if ENV == "prod": send_exection_alert(f"IB Gateway, Error while checking {type} status - {data_str.status_code}")
            continue
        data_str = data_str.text
        logger.info(f"IB Gateway, {type} status - {data_str}")
        if data_str == "0":
            ib_gateway_dict = {"Success": ["Green", "All the IB Gateway are UP"]}
            continue
        data_str = data_str.split("_")
        ib_gateway = {}

        for i in data_str:
            array = i.split("-")
            if len(array) == 2:
                ib_gateway[array[0]] = array[1]

        for i in ib_gateway:
            key = f"{type}: {i}"
            if key == "IB Reader: 249":
                continue
            ib_gateway_update.setdefault(key, [])
            color = "Green"
            if ib_gateway[i] == "false":
                color = "Red"
                if ENV == "prod" and ( 
                    key not in last_alert_time
                    or last_alert_time[key][0] + timedelta(minutes=30) < datetime.now()
                ):
                    extra_message = "{} gateway has failed for : {}".format(type, i)
                    send_alert(key,"Red","ib",f"\n{extra_message}",only_groups=["trade_ops"])
                    last_alert_time[key] = [datetime.now(),1]
            elif key in last_alert_time: del last_alert_time[key]
            ib_gateway_update[key].append(color)
            ib_gateway_update[key].append(ib_gateway[i])

        ib_gateway_dict = ib_gateway_update

def monitor_url_check(monitors):
    logger.info(f"Checking Monitor status")
    new_monitors = {}
    for key, value in monitors.items():
        url = value["url"]
        health = value["health"]
        # print(url, health)
        if ENV == "local" and "backend-internal" in url: continue
        try:
            if "ib" in key: continue
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                if health >= 3: send_alert(f"{key} - monitor", "Red", "backend", f", Status Code - {response.status_code}")
                else: 
                    new_monitors[key] = {"url": url, "health": health + 1}
                    if ENV == "prod": send_exection_alert(f"{key} monitor has Status Code - {response.status_code}")
            elif key != "webfilter-ws" and response.text != "0": send_alert(f"{key} - monitor", "Red", "backend", f", Response in Monitor - {response.text}")
        except:
            if ENV != "dev": send_exection_alert(f"{key} monitor has timed out")
            new_monitors[key] = {"url": url, "health": health + 1}
    if new_monitors.keys():
        sleep(10)
        monitor_url_check(new_monitors)

def send_alert_array(alerts_list):
    for category, alerts in alerts_list.items():
        single_alert_flag = False
        single_alert_title = category.replace("-", " ").title()
        single_alert_msg = ""
        single_alert_highest_alert = "Green"
        if len(alerts.keys()) > 4: single_alert_flag = True

        for key, alert in alerts.items():
            if not single_alert_flag: send_alert(key , alert["color"], category, alert["msg"])
            else:
                for alert_type in ("Red", "Yellow"):
                    if single_alert_highest_alert == alert_type: break
                    single_alert_highest_alert = alert["color"]
                single_alert_msg += f"\n{key} is {alert['color']}{alert['msg']}"
    
        if single_alert_flag: send_alert(single_alert_title, single_alert_highest_alert, category, single_alert_msg)

def db_select_calling(request):
    from status.aws_instance import category_instances, ec2_thead
    # from status.docker_images import docker_images_time, last_refresh_ecr
    from status.dms_check import dms_alerts, dms_thead
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    if ENV not in ("local", "dev") and user_name == "Unknown" and ip != get_property("VPC_NAT_IP"):
        return redirect("/status/")

    logger.info(
        f"views.py - db_select - start - User : {user_name} - ip - {ip} - {else_ip}"
    )
    threading.Timer(10, db_session_check).start()
    dict = {
        "backend": [],
        "ui": [],
        "batchapps": [],
        "services": [],
        "consumers": [],
        "rate_limit": [],
    }
    last_updated_time = {}
    queue_dict = {}
    saxo_dict = {}
    flex_validation = {}
    batch_app = {}
    aws_instances = {}
    # docker_status = {}
    certificates = {}
    silent_list = []
    version = []
    version1= []
    # connectors_list = []
    # topics = []
    redis_rate_limit = {}
    # temp_docker_images_time = []
    application_down = {}
    alert_service_url = "/alert"
    logger.info("Checking services_final status")
    try:
        cursor = connection.cursor()
        # cursor.execute("select pg_sleep(30);")
        if ENV in ("local", "dev") or request.user.groups.filter(name="DevOps").exists():
            postgreSQL_select_Query = (
                "select service_name from status.alert_silent order by service_name;"
            )
            cursor.execute(postgreSQL_select_Query)
            silent_records = cursor.fetchall()
            for row in silent_records:
                silent_list.append(row[0])

        postgreSQL_select_Query = "select service_name, total_nodes, up_nodes, monitor_url, category, create_time, modified_time from service_final order by service_name;"
        cursor.execute(postgreSQL_select_Query)
        mobile_records = cursor.fetchall()

        # 0 service_name
        # 1 total_nodes
        # 2 up_nodes
        # 3 monitor_url
        # 4 category
        # 5 create_time
        # 6 modified_time
        monitors = {}
        alerts_list = {}
        for row in mobile_records:
            modified_time = row[6]
            monitor_url = row[3]
            category = row[4]
            up_nodes = row[2]
            total_nodes = row[1]
            service_name = row[0]
            dict.setdefault(category, [])
            alerts_list.setdefault(category, {})
            data = []
            flag=True
            if up_nodes >= total_nodes:
                data.append("Green")
                data.append(service_name)
                if service_name in application_down: del application_down[service_name]
            elif total_nodes - 1 == up_nodes and up_nodes != 0:
                data.append("Yellow")
                data.append(service_name)
                alerts_list[category][service_name]= { "color": "Yellow", "msg" : ""}
            else:
                flag=False
                data.append("Red")
                data.append(service_name)
                delta = str(datetime.now() - modified_time).split(".")[0]
                msg = f", for {delta}"
                # if category == "rate_limit":
                #     alerts_list[category].setdefault("Redis Rate Limiting",{ "color": "Red", "category": category, "msg" : ""})
                #     alerts_list[category]["Redis Rate Limiting"]['msg'] +=  f"\n{service_name} for {delta}"
                # else: 
                alerts_list[category][service_name]= { "color": "Red", "msg" : msg}
                application_down[service_name] = True
            dict[category].append(data)
            if monitor_url and flag:
                monitors[service_name] = {"url": monitor_url, "health": 0}

        threading.Timer(10, monitor_url_check, args=(monitors,)).start()
        threading.Timer(15, send_alert_array, args=(alerts_list,)).start()
        
        redis_rate_limit = dict["rate_limit"]
        del dict["rate_limit"]
        if "kyc-internal-ws" not in application_down: saxo_dict = saxo_tokens_func()
        if "validation-ws" not in application_down: flex_validation = refresh_func()
        if ENV != "local":
            if ENV != "dev" and "ib-orders-ws" not in application_down and "ib-reader-ws" not in application_down: threading.Thread(target=ib_gateway_func).start()
            threading.Timer(20, kafka_connectors_check).start()
            batch_app = db_batch_app_table()
            queue_dict = db_queue_table()
            last_updated_time = db_time()
            if ec2_thead.is_alive():
                send_exection_alert("ec2_thead is alive")
                aws_instances = category_instances
            else: aws_instances = ec2_instance_status()
            now = datetime.now()
            if ENV != "dev" and now.minute % 15 == 0 and not dms_thead.is_alive(): threading.Timer(30, dms_tasks_status).start()
            version = versioncomp()
            version1= appversioncomp()
            if ENV == "prod": certificates = db_certificates_status()
        # for values in docker_images_time:
        #     delta = timedelta(seconds=values[1])
        #     delta = str(delta).split('.')[0]
        #     temp_docker_images_time.append([values[0], delta])
        alert_service_url = get_property("ALERT_SERVICE_URL")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error while Loading Status Page")
    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()
    logger.info(f"Rendering db_select.html")
    update_last_called_time()
    return render(
        request,
        "status/status.html",
        {
            "ENV": ENV,
            "services": dict,
            "tokens": {
                "Saxo Tokens": saxo_dict,
                "IB Gateway (Might be 1-2 Mins late)": ib_gateway_dict,
                "Flex Validation": flex_validation,
                "DMS Tasks": dms_alerts,
            },
            "batch_app": batch_app,
            "rate_limit": redis_rate_limit,
            "queue": queue_dict,
            "aws_instances": aws_instances,
            "solr": cores_rows,
            # "docker": temp_docker_images_time,
            # "last_refresh_ecr": last_refresh_ecr,
            "certificates": certificates,
            "silent_list": ",".join(silent_list),
            "last": last_updated_time,
            "last_refresh": last_refresh,
            "user_name": user_name,
            'version' : version,
            'version1' : version1,
            'alert_service_url': alert_service_url
        },
    )


@user_passes_test(local_check, login_url="/accounts/google/login/")
def db_select(request):
    return db_select_calling(request)


cores_rows = {}

last_refresh = ""

SOLR_ENDPOINT = get_property("SOLR_ENDPOINT")

def get_core_rows(core_name):
    global cores_rows
    response = requests.get(f"{SOLR_ENDPOINT}/{core_name}/query?debug=query&q=*:*", timeout=10)
    if response.status_code == 200:
        cores_rows[core_name] = response.json()["response"]["numFound"]
    else:
        cores_rows[core_name] = "Not Found"


def refresh_data(request):
    global last_refresh
    logger.info("Refreshing Solr rows data")
    for core in cores_rows:
        get_core_rows(core)

    response = requests.get(f"{SOLR_ENDPOINT}/admin/collections?action=LIST", timeout=10)
    cores_list = response.json()["collections"]
    current_cores_list = cores_rows.keys()

    new_cores = list(set(cores_list) - set(current_cores_list))
    deleted_cores = list(set(current_cores_list) - set(cores_list))

    for core in new_cores:
        get_core_rows(core)

    temp = cores_rows

    for core in deleted_cores:
        del cores_rows[core]

    last_refresh = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    status = ""
    if len(new_cores) > 0 or len(deleted_cores) > 0:
        status = " There are some changes in solr cores. Refresh this page."

    return JsonResponse({"core": temp, "status": last_refresh + status})


@user_passes_test(local_check, login_url="/accounts/google/login/")
def alert_logs(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
    columns = ["service_name", "status", "message"]
    postgreSQL_select_Query = "select to_char(create_time, 'Mon DD YYYY HH24:MI:SS'),{} from status.audit_logs ORDER BY create_time desc".format(
        ",".join(columns)
    )
    rows = []
    try:
        cursor = connection.cursor()
        cursor.execute(postgreSQL_select_Query)
        rows = cursor.fetchall()
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error while Loading Alert Logs")
    finally:
        if connection:
            cursor.close()
            connection.close()
    columns.insert(0, "Time")
    return render(
        request,
        "logs.html",
        {
            "ENV": ENV,
            "title": "Alert",
            "columns": columns,
            "rows": rows,
            "user_name": user_name,
            "status_service_url": get_property("STATUS_BOARD_URL"),
            "alert_service_url": get_property("ALERT_SERVICE_URL")
        },
    )


def error_403(request):
    return render(
        request,
        "error_403.html",
        {
            "ENV": ENV,
            "user_name": request.user.get_full_name(),
        },
        status=403,
    )
