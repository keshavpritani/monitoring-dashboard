from alert.essentials import *
current_file_name = os.path.basename(__file__)

@csrf_exempt
def toggle_silent_alert(request, status):
    user_name = "Unknown"
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - toggle_silent_alert")
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(
                f"{current_file_name} - toggle_silent_alert - User - {user_name} - User does not have DevOps group"
            )
            return return_403()
    else:
        return_status, data = is_allowed(ip)
        if not return_status: return data
        else: user_name = data
    logger.info(f"{current_file_name} - toggle_silent_alert - User - {user_name} - ip - {ip} - {else_ip}")

    minutes = 10
    if "minutes" in request.POST: minutes = int(request.POST.get("minutes"))
    if request.method == "PUT": 
        data = json.loads(request.body)
        user_name = data["username"] if "username" in data else user_name
        minutes = int(data["minutes"]) if "minutes" in data else minutes

    response = toggle_silent_alert_calling(user_name, status, minutes)
    if request.method == "POST": return redirect("/alert/")
    return response

@csrf_exempt
def silent_specific_alert(request):
    user_name = "Unknown"
    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - silent_specific_alert - User - {user_name} - ip - {ip} - {else_ip}")
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(
                f"{current_file_name} - silent_specific_alert - User - {user_name} - User does not have DevOps group"
            )
            return return_403()
    else:
        return_status, data = is_allowed(ip)
        if not return_status: return data
        else: user_name = data

    if request.method != "POST": return HttpResponse("Only Post Method is Allowed", status=405)

    import alert.essentials as ess
    try:
        data = json.loads(request.body)
        if "status" not in data: return HttpResponse("Status is not provided", status=404)
        if "service_name" not in data and "service_names" not in data: return HttpResponse("Service Name(s) is not provided", status=404)
        status = data["status"]
        service_name = str(data["service_name"]).split(",") if "service_name" in data else []
        service_names = []
        if "service_names" in data:
            param_type = type(data["service_names"])
            if param_type == str: service_names = str(data["service_names"]).split(",")
            elif param_type == list: service_names = data["service_names"]
        service_names = service_name + service_names
        time = int(get_property("SPECIFIC_SILENT_TIME"))
        if "time" in data and str(data["time"]).isnumeric(): time = int(data["time"]) 
    except:
        send_exection_alert("Error in Toggling alert silent")
        return HttpResponse("Something went wrong", status=500)
    try:
        cursor = connection.cursor()
        for service_name in service_names:
            service_name = service_name.strip()
            if status:
                cursor.execute(
                    f"INSERT INTO status.alert_silent(service_name) values ('{service_name}') on conflict (service_name) DO UPDATE SET silented_on = now();"
                )
                threading.Timer(time * 60, unsilent_specific_alert,args=(service_name,user_name)).start()
            else:
                cursor.execute(
                    f"DELETE FROM status.alert_silent where service_name = '{service_name}';"
                )
            insert_audit_log(
                f"silent_alert-{service_name}", status, f"Changed by {user_name} for {time} minutes"
            )
        connection.commit()
        cursor.execute("SELECT * FROM status.alert_silent;")
        rows = cursor.fetchall()
        old_silent = ess.is_silent
        ess.is_silent = len(rows) > 0
        if old_silent != ess.is_silent: 
            ess.silent_at = datetime.now()
            ess.silent_by = user_name
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in Toggling alert silent")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return HttpResponse("Success", status=200)

@csrf_exempt
def release_silent_alert(request, status):
    import alert.essentials as ess
    status = status.lower() in ["true", "1", "t", "y", "yes", "disable", "stop", "silent"]
    if not ess.is_silent and not status: return HttpResponse("No change in silent alert status, Silent alert is {}".format(ess.is_silent))

    ip, else_ip = get_ip(request)
    logger.info(f"{current_file_name} - release_silent_alert - Status - {status} - ip - {ip} - {else_ip}")

    return_status, user_name = is_allowed(ip)
    if not return_status: return user_name

    if ess.release_silent and status:
        return HttpResponse("Alerts Already Silent, Please Un-Silent it first", status=409)

    time = int(get_property("RELEASE_SILENT_TIME"))
    services = json.loads(get_property("RELEASE_SILENT_CATEGORIES"))
    type = "release"
    try:
        cursor = connection.cursor()
        if request.body:
            data = json.loads(request.body)
            if "type" in data and data["type"] != "": type = data["type"]
            # if type != "release" and ("services" not in data or len(data["services"]) == 0): return HttpResponse("Services are not provided", status=409)
            if "services" in data and len(data["services"]) != 0: services = data["services"]
            if "time" in data and str(data["time"]).isnumeric(): time = int(data["time"])
        for service_name in services:
            if status: cursor.execute(f"INSERT INTO status.alert_silent(service_name) values ('category-{service_name}') on conflict (service_name) DO UPDATE SET silented_on = now();")
            else: cursor.execute(f"DELETE FROM status.alert_silent where service_name = 'category-{service_name}';")
        
        extra_description = "Silented Categories - " + ", ".join(services)
        insert_audit_log(f"silent_alert-{type}", status, f"Changed by {user_name} for {time} minutes, {extra_description}")
        connection.commit()
        cursor.execute("SELECT * FROM status.alert_silent;")
        rows = cursor.fetchall()
        old_silent = ess.is_silent
        ess.is_silent = len(rows) > 0
        if type in ("release", "dd"): ess.release_silent = status
        if status: threading.Timer(time * 60, release_silent_alert,args=(request,"false")).start()
        if old_silent != ess.is_silent: 
            ess.silent_at = datetime.now()
            ess.silent_by = user_name
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error in Toggling alert silent")
        return HttpResponse("Something went wrong", status=500)
    finally:
        if connection:
            cursor.close()
            connection.close()
    return HttpResponse("Success", status=200)
