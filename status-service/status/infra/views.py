import threading
from datetime import datetime
from status.essentials import *

from django.shortcuts import render, redirect

from infra.ec2_current import *
from infra.nacl_current import *
from infra.rds_current import *
from infra.security_group_current import *
from infra.subnet_current import *
from infra.route_current import *
from django.template.defaulttags import register

import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.text import MIMEText

import smtplib

@register.filter
def replace(string):
    return string.replace("_", " ")


def get_ec2_details(queue):
    ec2_current_dict = ec2_current()
    ec2_baseline_dict = diff("ec2")
    ec2_only_diff = ec2_current_merge(True)

    queue.append((ec2_current_dict, ec2_baseline_dict, ec2_only_diff))


def get_rds_details(queue):
    rds_current_dict = rds_current()
    rds_baseline_dict = diff("rds")
    rds_only_diff = rds_current_merge(True)

    queue.append((rds_current_dict, rds_baseline_dict, rds_only_diff))


def get_subnet_details(queue):
    subnet_current_dict = subnet_current()
    subnet_baseline_dict = diff("subnet")
    subnet_only_diff = subnet_current_merge(True)

    queue.append((subnet_current_dict, subnet_baseline_dict, subnet_only_diff))


def get_sg_details(queue):
    sg_current_dict = sg_current()
    sg_baseline_dict = diff("sg")
    sg_only_diff = sg_current_merge(True)

    queue.append((sg_current_dict, sg_baseline_dict, sg_only_diff))


def get_nacl_details(queue):
    nacl_current_dict = nacl_current()
    nacl_baseline_dict = diff("nacl")
    nacl_only_diff = nacl_current_merge(True)

    queue.append((nacl_current_dict, nacl_baseline_dict, nacl_only_diff))


def get_route_details(queue):
    route_current_dict = route_current()
    route_baseline_dict = diff("route")
    route_only_diff = route_current_merge(True)

    queue.append((route_current_dict, route_baseline_dict, route_only_diff))


@user_passes_test(local_check, login_url="/accounts/google/login/")
def show_data(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(
        f"infra_views.py - show_data - User - {user_name} - ip - {ip} - {else_ip}"
    )

    ec2_queue = []
    ec2_thread = threading.Thread(target=get_ec2_details, args=(ec2_queue,))
    ec2_thread.start()

    rds_queue = []
    rds_thread = threading.Thread(target=get_rds_details, args=(rds_queue,))
    rds_thread.start()

    subnet_queue = []
    subnet_thread = threading.Thread(target=get_subnet_details, args=(subnet_queue,))
    subnet_thread.start()

    sg_queue = []
    sg_thread = threading.Thread(target=get_sg_details, args=(sg_queue,))
    sg_thread.start()

    nacl_queue = []
    nacl_thread = threading.Thread(target=get_nacl_details, args=(nacl_queue,))
    nacl_thread.start()

    route_queue = []
    route_thread = threading.Thread(target=get_route_details, args=(route_queue,))
    route_thread.start()

    logs = get_log()

    ec2_thread.join()
    ec2_current_dict, ec2_baseline_dict, ec2_only_diff = ec2_queue[0]

    rds_thread.join()
    rds_current_dict, rds_baseline_dict, rds_only_diff = rds_queue[0]

    subnet_thread.join()
    subnet_current_dict, subnet_baseline_dict, subnet_only_diff = subnet_queue[0]

    sg_thread.join()
    sg_current_dict, sg_baseline_dict, sg_only_diff = sg_queue[0]

    nacl_thread.join()
    nacl_current_dict, nacl_baseline_dict, nacl_only_diff = nacl_queue[0]

    route_thread.join()
    route_current_dict, route_baseline_dict, route_only_diff = route_queue[0]
    context = {
        "ENV": ENV,
        "services": {
            "EC2": {
                "column_list": column_list["ec2"],
                "baseline": ec2_baseline_dict,
                "current": ec2_current_dict,
                "diff": ec2_only_diff,
                "arrays": array_indexes["ec2"],
            },
            "RDS": {
                "column_list": column_list["rds"],
                "baseline": rds_baseline_dict,
                "current": rds_current_dict,
                "diff": rds_only_diff,
                "arrays": array_indexes["rds"],
            },
            "Subnet": {
                "column_list": column_list["subnet"],
                "baseline": subnet_baseline_dict,
                "current": subnet_current_dict,
                "diff": subnet_only_diff,
                "arrays": array_indexes["subnet"],
            },
            "Security Group": {
                "column_list": column_list["sg"],
                "baseline": sg_baseline_dict,
                "current": sg_current_dict,
                "diff": sg_only_diff,
                "arrays": array_indexes["sg"],
            },
            "NACL": {
                "column_list": column_list["nacl"],
                "baseline": nacl_baseline_dict,
                "current": nacl_current_dict,
                "diff": nacl_only_diff,
                "arrays": array_indexes["nacl"],
            },
            "Route Tables": {
                "column_list": column_list["route"],
                "baseline": route_baseline_dict,
                "current": route_current_dict,
                "diff": route_only_diff,
                "arrays": array_indexes["route"],
            },
        },
        "log": logs,
        "user_name": user_name,
    }
    context["alert_service_url"] = get_property("ALERT_SERVICE_URL")
    logger.info(f"Rendering infra.html")
    return render(request, "infra/infra.html", context)

# @user_passes_test(local_check, login_url="/accounts/google/login/")
def refresh_data(request, tn):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(f"infra_views.py - refresh_data - User - {user_name} - ip - {ip} - {else_ip}")

    logger.info(f"Refreshing Data at {datetime.now()}")
    table_name = "current"
    count = 1 if tn == table_name else 2
    for i in range(count):
        logger.info("Inserting the {} Records for EC2".format(table_name))
        ec2_thread = threading.Thread(target=ec2_current_insert, args=(table_name,))
        ec2_thread.start()

        logger.info("Inserting the {} Records for RDS".format(table_name))
        rds_thread = threading.Thread(target=rds_current_insert, args=(table_name,))
        rds_thread.start()

        logger.info("Inserting the {} Records for Subnet".format(table_name))
        subnet_thread = threading.Thread(
            target=subnet_current_insert, args=(table_name,)
        )
        subnet_thread.start()

        logger.info("Inserting the {} Records for Security Group".format(table_name))
        sg_thread = threading.Thread(target=sg_current_insert, args=(table_name,))
        sg_thread.start()

        logger.info("Inserting the {} Records for NACL".format(table_name))
        nacl_thread = threading.Thread(target=nacl_current_insert, args=(table_name,))
        nacl_thread.start()

        logger.info("Inserting the {} Records for Route Tables".format(table_name))
        route_thread = threading.Thread(target=route_current_insert, args=(table_name,))
        route_thread.start()

        ec2_thread.join()
        rds_thread.join()
        subnet_thread.join()
        sg_thread.join()
        nacl_thread.join()
        route_thread.join()

        table_name = tn

    return redirect("/infra/")


services = {
    "EC2": ec2_current_merge,
    "RDS": rds_current_merge,
    "Subnet": subnet_current_merge,
    "Security Group": sg_current_merge,
    "NACL": nacl_current_merge,
    "Route Tables": route_current_merge,
}


@user_passes_test(local_check, login_url="/accounts/google/login/")
def merge_data(request, service_name):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
        if not request.user.groups.filter(name="DevOps").exists():
            logger.error(
                f"infra_views.py - merge_data - User - {user_name} - User does not have DevOps group"
            )
            return redirect("/status/403/", status=403)
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(
        f"infra_views.py - merge_data - User - {user_name} - ip - {ip} - {else_ip}"
    )

    logger.info(
        "Merging the Current Records to Baseline Records of {}".format(service_name)
    )
    if service_name == "all":
        for service in services:
            services[service](username=user_name)
    else:
        services[service_name](username=user_name)
    logger.info("Merging Completed of {}".format(service_name))

    return redirect("/infra/")


@user_passes_test(local_check, login_url="/accounts/google/login/")
def logs(request, service_name):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
    columns = ["Time", "instance_id", "log", "username"]
    rows = get_log(service_names=[service_name], is_not_limit=True)
    if service_name in rows:
        rows = rows[service_name]
    return render(
        request,
        "logs.html",
        {
            "ENV": ENV,
            "title": service_name,
            "columns": columns,
            "rows": rows,
            "user_name": user_name,
            "status_service_url": get_property("STATUS_BOARD_URL"),
            "alert_service_url": get_property("ALERT_SERVICE_URL")
        },
    )

services_functions = {
    "merge" : {
        "ec2": ec2_current_merge,
        "rds": rds_current_merge,
        "subnet": subnet_current_merge,
        "sg": sg_current_merge,
        "nacl": nacl_current_merge,
        "route": route_current_merge,
    }
}

def send_mail(request):
    refresh_data(request, "current")
    diff = {}
    for service_name in service_names:
        print(service_name)
        matrix = []
        temp_diff = services_functions["merge"][service_name](True)
        for single_diff in temp_diff: temp_diff[single_diff][1] = str(temp_diff[single_diff][1]).replace("<br>", "\n").strip()
        for key, value in temp_diff.items(): matrix.append([key] + value)
        if matrix: 
            transpose = [[matrix[j][i] for j in range(len(matrix))] for i in range(len(matrix[0]))]
            diff[service_name] = pd.DataFrame(transpose).T
    # pprint(diff)
    if not diff:
        logger.info("No Diff Found")
        return HttpResponse("No Diff Found")
    
    from datetime import date
    today = date.today()
    d1 = today.strftime("%d-%m-%Y")

    # filename = get_property("INFRA_DIFF_MAIL_FILENAME")
    # temp = filename.split(".")
    # filename = temp[0] + "_" + d1 + "." + temp[1]

    filename = f"aws_{ENV}_infra_diff_{d1}.xlsx"
    print(filename)
    with pd.ExcelWriter(filename) as writer:
        for service_name in service_names:
            if service_name in diff: diff[service_name].to_excel(writer, sheet_name = service_name, header = ["ID", "Name", "Description"], index = False, freeze_panes = [0,1])
    
    msg = MIMEMultipart()
    msg['Subject'] = f"AWS {str(ENV).title()} Infra Diff - {d1}"
    msg['From'] = get_property("INFRA_DIFF_MAIL_FROM")
    msg['To'] = get_property("INFRA_DIFF_MAIL_TO")
    body = MIMEText("Found Diff in - " + ", ".join(diff) + f"\nMore Info at {get_property('INFRA_BOARD_URL')}/")
    msg.attach(body)
    file = MIMEApplication(open(filename, 'rb').read())
    file.add_header('Content-Disposition', 'attachment', filename = filename)
    msg.attach(file)

    try:
        logger.info("Sending Mail")
        with smtplib.SMTP_SSL(get_property("INFRA_DIFF_SMTP_HOST"), port = int(get_property("INFRA_DIFF_SMTP_PORT"))) as smtpObj:
            smtpObj.ehlo()
            smtpObj.login(get_property("INFRA_DIFF_SMTP_USERNAME"), get_property("INFRA_DIFF_SMTP_PASSWORD"))
            smtpObj.sendmail(msg['From'], msg['To'], msg.as_string())
            smtpObj.quit()
            logger.info(f"Mail Sent to {msg['To']}")
    except Exception as e:
        print(e)
        return HttpResponse("Error in sending mail", status = 500)

    # from django.core.mail import EmailMessage
    # subject = f"AWS {str(ENV).title()} Infra Diff - {d1}"
    # message = "Found Diff in - " + ",".join(diff)
    # mail = EmailMessage(subject, message, get_property("INFRA_DIFF_MAIL_FROM"), [get_property("INFRA_DIFF_MAIL_TO")])
    # f = open(filename,'r')
    # mail.attach(f.name, f.read())
    # mail.send()
    
    import os
    if os.path.exists(filename): os.remove(filename)

    return HttpResponse("Successfully")

