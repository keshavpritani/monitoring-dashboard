from django.shortcuts import render
from alert.essentials import *

current_file_name = os.path.basename(__file__)

def check_threads():
    from alert.essentials import remove_alert_from_dict_last_checked, silent_alert_notification_last_checked
    try:
        now = datetime.now()
        if remove_alert_from_dict_last_checked < now - timedelta(minutes=15):
            send_exection_alert("!!!!!!!!!!!!!!!!!!!!!!! Restarting remove_alert_from_dict thread !!!!!!!!!!!!!!!!!!!!!!!")
            threading.Thread(target=remove_alert_from_dict).start()
        if ENV != "local" and silent_alert_notification_last_checked < now - timedelta(minutes=75):
            send_exection_alert("!!!!!!!!!!!!!!!!!!!!!!! Restarting silent_alert_notification thread !!!!!!!!!!!!!!!!!!!!!!!")
            threading.Thread(target=silent_alert_notification).start()
    except:
        send_exection_alert("Error in check_threads")

def monitor(request):
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1;")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert(f"Error while connecting to PostgreSQL")
        return HttpResponse(1, status=500)
    return HttpResponse(0, status=200)

@csrf_exempt
def receive_alert(request):
    check_threads()
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - receive_alert - ip - {ip} - {else_ip}")

    return_status, data = is_allowed(ip)
    if not return_status: return data

    if request.method != "POST": return HttpResponse("Method Not Allowed", status=405)

    try:
        if not request.body: return HttpResponse("Request Body is Required", status=404)
        data = json.loads(request.body)
        mandatory_fields = ["key", "status", "category"]
        for i in mandatory_fields:
            if i not in data: return HttpResponse(f"{i} is not provided", status=412)
        key = data["key"]
        status = str(data["status"]).title()
        allowed_values = ("red", "yellow", "green")
        if status.lower() not in allowed_values: return HttpResponse(f"{status} not allowed in Status", status=412)
        category = data["category"]
        extra_message = data['extra_message'] if "extra_message" in data else ""
        for dict_key,dict_value in data.items():
            if dict_key in mandatory_fields or dict_key in ("groups", "only_groups", "extra_message"): continue
            extra_message = f"{extra_message}\n{dict_key} - {dict_value}"
        groups = data["groups"] if "groups" in data and data["groups"] else []
        only_groups = data["only_groups"] if "only_groups" in data and data["only_groups"] else []
        if type(groups) != list: return HttpResponse("Groups should be in type array of strings only",status=412)
        send_alert(key,status,category,extra_message, groups, only_groups)
    except:
        send_exection_alert("Error in Receiving Alert")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return HttpResponse("Success", status=200)

@csrf_exempt
def grafana_alert(request):
    check_threads()
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - grafana_alert - ip - {ip} - {else_ip}")

    return_status, data = is_allowed(ip)
    if not return_status: return data

    if request.method != "POST": return HttpResponse("Method Not Allowed", status=405)

    try:
        if not request.body: return HttpResponse("Request Body is Required", status=404)
        data = json.loads(request.body)
        logger.info(f"data - {data}")
    except:
        send_exection_alert("Error in Receiving Grafana Alert")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return HttpResponse("Success", status=200)

@user_passes_test(local_check, login_url="/accounts/google/login/")
def update_silent_time(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(f"{current_file_name} - get_console - User - {user_name} - User does not have DevOps group")
            return return_403()
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - update_silent_time - User - {user_name} - ip - {ip} - {else_ip}")

    if request.method != "POST": return HttpResponse("Method Not Allowed", status=405)

    try:
        update_property("SPECIFIC_SILENT_TIME", request.POST.get("specific"))
        update_property("RELEASE_SILENT_TIME", request.POST.get("release"))
        insert_audit_log("update-silent-time", "Green", f"Silent Time Properties changed by {user_name}")
    except:
        send_exection_alert("Error in Updating silent time")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return redirect("/alert/")

@user_passes_test(local_check, login_url="/accounts/google/login/")
def update_billing_ignore_capacity(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(f"{current_file_name} - get_console - User - {user_name} - User does not have DevOps group")
            return return_403()
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - update_silent_time - User - {user_name} - ip - {ip} - {else_ip}")

    if request.method != "POST": return HttpResponse("Method Not Allowed", status=405)

    try:
        current = get_property("BILLING_IGNORE_CAPACITY")
        new = json.loads(request.POST.get("current_billing_ignore"))
        update_property("BILLING_IGNORE_CAPACITY", json.dumps(new))
        insert_audit_log("update-billing-ignore-capacity", "Green", f"Billing Ignore Capacity Properties changed by {user_name}, From - {current} - To - {new}")
    except:
        send_exection_alert("Error in Updating silent time")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return redirect("/alert/")

@user_passes_test(local_check, login_url="/accounts/google/login/")
def get_console(request):
    check_threads()
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(f"{current_file_name} - get_console - User - {user_name} - User does not have DevOps group")
            return return_403()
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - get_console - User - {user_name} - ip - {ip} - {else_ip}")

    from alert.essentials import is_silent, silent_at, last_alert_time, release_silent, all_silent, silent_by
    extra_status = f"All Silent - {all_silent} - Release Silent - {release_silent}"
    context = {
        "ENV": ENV,
        "is_silent": is_silent,
        "silent_at": silent_at,
        "silent_by": f"(Done by {silent_by})",
        "extra_status": extra_status,
        "last_alert_time": last_alert_time,
        "user_name": user_name,
        "specific_alert_time" : get_property("SPECIFIC_SILENT_TIME"),
        "release_alert_time": get_property("RELEASE_SILENT_TIME"),
        "status_service_url": get_property("STATUS_BOARD_URL"),
        "alerts_category": json.loads(get_property("ALERTS_CATEGORY")),
        "billing_last_alert": billing_last_alert,
        "billing_ignore_capacity": get_property("BILLING_IGNORE_CAPACITY"),
    }
    try:
        cursor = connection.cursor()
        cursor.execute("select service_name from status.alert_silent order by service_name;")
        silent_records = cursor.fetchall()
        silent_list = []
        for row in silent_records:
            silent_list.append(row[0])
        context["alerts"] = silent_list
        context["silent_list"] = ",".join(silent_list)

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to load alert console")
    return render(request, "alert/alert.html", context)

@csrf_exempt
@user_passes_test(local_check, login_url="/accounts/google/login/")
def remove_service(request):
    if ENV == "prod": return HttpResponse("Not Allowed in this ENV", status=406)
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(f"{current_file_name} - remove_service - User - {user_name} - User does not have DevOps group")
            return return_403()

    ip, else_ip = get_ip(request)

    logger.info(f"{current_file_name} - remove_service - User - {user_name} - ip - {ip} - {else_ip}")

    global last_alert_time
    try:
        if request.method != "POST": return HttpResponse("Method Not Allowed", status=405)
        data = json.loads(request.body)
        if "service_name" not in data: return HttpResponse("No service name provided", status=400)
        service_name = data["service_name"]
        cursor = connection.cursor()
        cursor.execute(f"DELETE FROM service_final WHERE service_name = '{service_name}';")
        connection.commit()
        if service_name in last_alert_time: del last_alert_time[service_name]
        insert_audit_log(f"{service_name}", "Red", f"Service removed by {user_name}")
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to remove service")
        return HttpResponse(error)
    return HttpResponse("OK")

billing_last_alert = {}

@csrf_exempt
def billing_alert(request):
    check_threads()
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - billing_alert - ip - {ip} - {else_ip}")

    return_status, data = is_allowed(ip)
    if not return_status: return data

    if request.method != "POST": return HttpResponse("Method Not Allowed", status=405)

    global billing_last_alert
    try:
        if not request.body: return HttpResponse("Request Body is Required", status=404)
        alerts = {}
        data = json.loads(request.body)
        alerts["EC2"] = data["EC2"] if "EC2" in data and data["EC2"] else {}
        alerts["RDS"] = data["RDS"] if "RDS" in data and data["RDS"] else {}
        if not alerts["EC2"] and not alerts["RDS"]: return HttpResponse(f"One of the Parameter is required - EC2 / RDS", status=400)
        BILLING_IGNORE_CAPACITY = {}
        try: BILLING_IGNORE_CAPACITY = json.loads(get_property("BILLING_IGNORE_CAPACITY"))
        except: send_exection_alert(f"Error in converting BILLING_IGNORE_CAPACITY to json in {current_file_name} - billing_alert ")
        extra_message = ""
        for dict_key, dict_value in data.items():
            temp = ""
            for key, value in dict_value.items():
                if dict_key not in BILLING_IGNORE_CAPACITY or key not in BILLING_IGNORE_CAPACITY[dict_key] or (BILLING_IGNORE_CAPACITY[dict_key][key] > 0 and BILLING_IGNORE_CAPACITY[dict_key][key] <= value) or (BILLING_IGNORE_CAPACITY[dict_key][key] < 0 and BILLING_IGNORE_CAPACITY[dict_key][key] >= value): temp = f"{temp}\n    {key}: {value} GB"
            if temp: extra_message += f"\n```{dict_key}: {temp}```"
        if extra_message: send_alert(f"{str(ENV).title()} - AWS Reserve Instance", "Yellow", "billing", f", Current State (Negative is Extra): {extra_message}", [], ["devops_1"])
        else: logger.info(f"Alert were not sent - Got - {alerts} - BILLING_IGNORE_CAPACITY - {BILLING_IGNORE_CAPACITY}")
        billing_last_alert = alerts.copy()
    except:
        send_exection_alert("Error in Receiving Billing Alert")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return HttpResponse("Success", status=200)
