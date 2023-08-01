from django.shortcuts import redirect, render
import psycopg2
from django.db import connection
from django.db import connections
from django.http import HttpResponse
from status.essentials import *
from django.views.decorators.csrf import csrf_exempt
import requests

databases = ['vpn2', 'kpm', 'kyc', 'funds', 'kristaldata', 'reports', 'queue']

@user_passes_test(local_check, login_url="/accounts/google/login/")
def get_console(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(
                f"admin_views.py - get_console - User - {user_name} - User does not have DevOps group"
            )
            return redirect("/status/403/", status=403)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(
        f"admin_views.py - get_console - User - {user_name} - ip - {ip} - {else_ip}"
    )

    context = {
        "ENV": ENV,
        "user_name": user_name
    }
    try:
        cursor = connection.cursor()

        postgreSQL_select_Query = (
            "select service_name from status.alert_silent order by service_name;"
        )
        cursor.execute(postgreSQL_select_Query)
        silent_records = cursor.fetchall()
        context["alerts"] = silent_records

        postgreSQL_select_Query = "select service_name, count(service_name) from ping_ping where service_name not in (select service_name from ping_ping intersect select service_name from service_final) GROUP BY service_name;"
        cursor.execute(postgreSQL_select_Query)
        silent_records = cursor.fetchall()
        context["new_services"] = silent_records

        batchapp_dict = {}
        for db in databases:
            # if ENV in ("dev", "local") and db == "reports":
            #     continue
            cursor = connections[db].cursor()

            postgreSQL_select_Query = "select * from batchapps.batch_process_monitor where start_time > now() - (interval '30' day) and state = 'RUNNING' order by state desc, start_time desc;"
            cursor.execute(postgreSQL_select_Query)
            batchapp_table_records = cursor.fetchall()

            for row in batchapp_table_records:
                key = row[2]
                batchapp_dict.setdefault(key, [])
                batchapp_dict[key].append(row[1])
                batchapp_dict[key].append(db)
                delta = datetime.now() - row[4]
                batchapp_dict[key].append(str(delta).split(".")[0])
        context["batchapp_dict"] = batchapp_dict
        context["alert_service_url"] = get_property("ALERT_SERVICE_URL")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to load admin console")
    return render(request, "admin/admin.html", context)


@user_passes_test(local_check, login_url="/accounts/google/login/")
def new_service(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(
                f"admin_views.py - new_service - User - {user_name} - User does not have DevOps group"
            )
            return redirect("/status/403/", status=403)

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(
        f"admin_views.py - new_service - User - {user_name} - ip - {ip} - {else_ip}"
    )

    try:
        if request.method != "POST":
            return HttpResponse("Method Not Allowed", status=405)
        service_name = request.POST.get("service_name")
        count = request.POST.get("count")
        category = request.POST.get("category")
        if category == "batchapps": count = 1
        monitor_url = request.POST.get("monitor_url")
        cursor = connection.cursor()
        cursor.execute(
            f"INSERT INTO service_final VALUES ('{service_name}',{count},0,'{monitor_url}','{category}',now(),now());"
        )
        connection.commit()
        insert_audit_log(f"{service_name}", "Green", f"New service added by {user_name}")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to add new service")
        return HttpResponse(error)
    return redirect("/status/admin/")

@csrf_exempt
@user_passes_test(local_check, login_url="/accounts/google/login/")
def batchapp_done(request, process_id, db):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(
                f"admin_views.py - batchapp_done - User - {user_name} - User does not have DevOps group"
            )
            return redirect("/status/403/", status=403)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(
        f"admin_views.py - batchapp_done - User - {user_name} - ip - {ip} - {else_ip}"
    )

    return mark_batchapps_done(process_id, db, user_name)

def mark_batchapps_done(process_id, db, user_name = "SYSTEM"):
    Jenkins_url = get_property("JENKINS_URL")
    jenkins_user = get_property("JENKINS_USER_ID")
    jenkins_pwd = get_property("JENKINS_USER_PASSWORD")
    jenkins_job_name = get_property("JENKINS_JOB_NAME")
    jenkins_params = {'token': get_property("JENKINS_TOKEN"), 
                    'process_id': process_id,
                    'DB': db,
                    'cause': f"Started by {user_name}"}
    try:
        data = requests.post("{0}/job/{1}/buildWithParameters".format(Jenkins_url,jenkins_job_name),auth=(jenkins_user, jenkins_pwd),params=jenkins_params, timeout=10)
        if str(data.status_code) != "201": raise Exception(f"Jenkins job is not triggered - Status Code - {data.status_code}")
        else: insert_audit_log(f"{db} - {process_id}", "Green", f"Batchapp marked as DONE by {user_name}")
    except Exception as e:
        send_exection_alert("Failed to mark batchapp as DONE")
        return HttpResponse(e)
    return HttpResponse("OK")
