import requests
import psycopg2
from django.db import connection
from django.db import connections
from status.essentials import *
from django.http import JsonResponse

def kafka_connectors_check(retry=3):
    logger.info(f"Checking Kafka connectors - retry - {retry}")
    connectors_list={}
    try:
        url = get_property('KAFKA_CONNECTORS_URL')
        response = requests.get(url, timeout=10).json()
        flag = False
        for connector in response:
            connector_response = requests.get(f"{url}/{connector}/status", timeout=10).json()
            connectors_list[connector] = connector_response['connector']['state']
            if connector_response['connector']['state'] != 'RUNNING': flag = True
            else:
                for task in connector_response['tasks']:
                    if task['state'] != 'RUNNING':
                        connectors_list[connector] = task['state']
                        flag = True
                        break
        if flag:
            extra_message = ", These are `not in RUNNING state`:"
            for key, value in connectors_list.items():
                if value != "RUNNING": extra_message += "\n" + key
            if retry <= 0: send_alert("Kafka Connector", "Red", "kafka", extra_message)
            else:
                send_exection_alert(f"Kafka connectors fail - {retry}")
                sleep(30)
                kafka_connectors_check(retry - 1)
    except Exception:
        send_exection_alert("Error while checking Kafka connectors")
    return connectors_list

def kafka_topic_list():
    logger.info("Fetching Kafka topics List")
    topics = []
    try:
        cursor = connections['queue'].cursor()
        postgreSQL_select_Query = "select task_type from investo2o.queue_table_split ORDER BY task_type"
        cursor.execute(postgreSQL_select_Query)
        topics = cursor.fetchall()
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error while fetching data from Queue Table")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return topics


# https://github.com/yahoo/CMAK/blob/master/conf/routes - for CMAK
def kafka_topic_check(request):
    topic_name = request.GET['topic']
    logger.info(f"Checking Kafka topics status for {topic_name}")
    CMAK_URL = get_property('CMAK_URL')
    response = requests.get(f"{CMAK_URL}/api/status/{ENV}/{topic_name}/{topic_name}/KF/topicSummary").json()
    total_lag = response['totalLag']
    consumers = response['owners']
    current_offset = response['partitionLatestOffsets']
    log_end_offset = response['partitionOffsets']
    return JsonResponse({ 
        "total_lag": total_lag,
        "consumers": consumers,
        "log_end_offset": log_end_offset,
        "current_offset": current_offset
    })