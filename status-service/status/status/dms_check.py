import time
import boto3
from status.essentials import *

region = properties['AWS_REGION']

client = boto3.client("dms", region_name=region)
dms_alerts = {}
health_check = 3

def dms_tasks_status():
    global dms_alerts, dms_thead
    try:
        logger.info(f"Checking DMS Tasks Status - {dms_alerts}")
        response = client.describe_replication_tasks()['ReplicationTasks']

        for i in response:
            name = i['ReplicationTaskIdentifier']
            status = i['Status']
            # stop_reason = i['StopReason'] if "StopReason" in i else ""
            last_failure_message = i['LastFailureMessage'] if "LastFailureMessage" in i else ""
            no_of_errors = i['ReplicationTaskStats']['TablesErrored']
            list_tags_for_resource = client.list_tags_for_resource(ResourceArn=i['ReplicationTaskArn'])
            monitoring = False
            for tags in list_tags_for_resource['TagList']:
                if tags['Key'] == 'Monitoring' and tags['Value'] == 'yes':
                    monitoring = True
            if not monitoring:
                if name in dms_alerts: del dms_alerts[name]
                continue
            flag = False
            if no_of_errors > 0:
                flag = True
                if name not in dms_alerts: dms_alerts[name] = { "text": "" , "count": 0 }
                dms_alerts[name]["text"] = f", current status - {status} with {no_of_errors} error(s)"
                dms_alerts[name]["count"] += 1
            if status != "running":
                flag = True
                msg = f", current status - {status}"
                # if stop_reason: msg = f"{msg}, Stop Reason - {stop_reason}"
                if last_failure_message: msg = f"{msg}, Last Failure Message - {last_failure_message}"
                dms_alerts[name] = { "text": msg , "count": 3 }
                if status == "failed": dms_alerts[name]["failed"] = True
                
            if not flag and name in dms_alerts: del dms_alerts[name]
        
        # send slack alert
        temp_dms_alerts = dms_alerts.copy()
        for key, value in dms_alerts.items():
            logger.info(f"Got Alert for {key} - {value}")
            if value["count"] >= health_check:
                txt = value["text"]
                if "failed" in value and value["failed"] and ENV != "prod": 
                    result, message = call_jenkins_job(get_property("START_DMS_JENKINS_JOB_NAME"), {"DB": key.split("-")[0], "STATUS": "start"})
                    if result: txt = f"{txt}\nTriggered its Start Task Jenkins Job Successfully"
                    else: txt = f"{txt}\nFailed to trigger its Start Task Jenkins Job - {message}"
                send_alert(f"{key} DMS Task", "Red", "dms", txt)
                del temp_dms_alerts[key]
        dms_alerts = temp_dms_alerts.copy()
        if len(dms_alerts) > 0 and not dms_thead.is_alive(): 
            dms_thead = threading.Thread(target=dms_thead_func)
            dms_thead.start()
    except: send_exection_alert("Error in dms_tasks_status")

def dms_thead_func():
    for i in range(health_check - 1):
        logger.info(f"Checking DMS Task Heath Status - {i}")
        time.sleep(60)
        dms_tasks_status()
dms_thead = threading.Thread(target=dms_thead_func)