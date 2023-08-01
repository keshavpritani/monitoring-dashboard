import time
import boto3
from status.essentials import *

region = properties['AWS_REGION']

ec2_client = boto3.client("ec2", region_name=region)
ec2_alerts = {}
category_instances = {}
health_check = 3

def ec2_instance_status():
    global category_instances, ec2_alerts, ec2_thead
    logger.info(f"Checking EC2 Instance Status - {ec2_alerts}")
    instances = {}
    response = ec2_client.describe_instances()
    for reservation in response["Reservations"]:
        for instance in reservation["Instances"]:
            key = instance["InstanceId"]
            name = ""
            flag = False
            if "Tags" not in instance:
                name = key
            else:
                for tag in instance["Tags"]:
                    if tag["Key"] == "Name":
                        name = tag["Value"]
                    if tag["Key"] == "Monitoring" and "node" in tag["Value"]:
                        flag = True
            color = "Green"
            state = instance['State']['Name']
            if state != "running":
                color = "Red"
                if flag: ec2_alerts[name] = { "text": f", current state - {state}" , "count": 3 }
                elif name in ec2_alerts: del ec2_alerts[name]
            elif name in ec2_alerts and "reaching" not in ec2_alerts[name]["text"]: del ec2_alerts[name]
            instances[key] = [name, color, state, flag]

    response = ec2_client.describe_instance_status().get('InstanceStatuses')
    for instance in response:
        key = instance['InstanceId']
        if key in instances:
            flag = False
            imparied = ""
            for check_type in ('InstanceStatus', 'SystemStatus'):
                status = instance.get(check_type).get('Status')
                if status != 'ok' and status != 'initializing':
                    for x in instance[check_type]['Details']:
                        if x['Status'] != 'passed':
                            flag = True
                            imparied = f"{status}, Error while reaching this " + \
                                instance['InstanceId'] + " instance"
                            if 'ImpairedSince' in x:
                                imparied += " since " + \
                                    str(x['ImpairedSince'])
                            break
            color = "Green"
            name = instances[key][0]
            if flag:
                color = "Red"
                send_exection_alert(f"Instance Reachablity alert - {name} - {imparied}")
                if instances[key][3]:
                    ec2_alerts.setdefault(name, { "text": "", "count": 0 })
                    ec2_alerts[name]["text"] = f", current state - {imparied}"
                    ec2_alerts[name]["count"] += 1
            elif name in ec2_alerts and "reaching" in ec2_alerts[name]["text"]: del ec2_alerts[name]
            instances[key][1] = color
            instances[key][2] = imparied
    # send slack alert
    temp_ec2_alerts = ec2_alerts.copy()
    for key, value in ec2_alerts.items():
        if value["count"] >= health_check:
            send_alert(f"{key} instance", "Red", "aws", value["text"])
            del temp_ec2_alerts[key]
    ec2_alerts = temp_ec2_alerts
    if len(ec2_alerts) > 0 and not ec2_thead.is_alive(): 
        ec2_thead = threading.Thread(target=ec2_thead_func)
        ec2_thead.start()
    temp_category_instances = {}
    category_list = ["backend", "batchapps", "consumers",
                     "frontend", "redis", "solr", "kafka", "other"]
    for category in category_list: temp_category_instances[category] = []
    for value in instances.values():
        for category in category_list:
            if category in value[0].lower() or (category == "consumers" and "report" in value[0].lower()):
                temp_category_instances[category].append(value)
                break
        else:
            temp_category_instances["other"].append(value)
    category_instances = temp_category_instances
    return category_instances

def ec2_thead_func():
    for i in range(health_check - 1):
        logger.info(f"Checking EC2 Heath Status - {i}")
        time.sleep(60)
        ec2_instance_status()
ec2_thead = threading.Thread(target=ec2_thead_func)