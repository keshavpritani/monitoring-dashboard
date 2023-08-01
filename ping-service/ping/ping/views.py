import psycopg2
from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser
from rest_framework import status
from ping.models import Ping
from ping.serializers import PingSerializer
from rest_framework.decorators import api_view
from ping.viewUpdate import *
import time
# import logging
# import sys
import traceback

# logger = logging.getLogger()
# logger.setLevel(logging.INFO)
# formatter = logging.Formatter("| %(asctime)s - %(levelname)s | %(message)s")

# stdout_handler = logging.StreamHandler(sys.stdout)
# stdout_handler.setLevel(logging.DEBUG)
# stdout_handler.setFormatter(formatter)
# file_handler = logging.FileHandler("ping.log")
# file_handler.setLevel(logging.DEBUG)
# file_handler.setFormatter(formatter)

# logger.addHandler(file_handler)
# logger.addHandler(stdout_handler)

headers = {
    "Content-type": "application/json",
}


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


def send_exection_alert(message=""):
    try:
        # logger.error(f"Exception came - {message} - {traceback.format_exc()}")
        data = {"text": f"Exception came - {message}"}
        data = json.dumps(data)
        devops_receviers = get_alert_receiver("devops")
        requests.post(
            devops_receviers["EXCEPTION"],
            data=data,
            headers=headers,
        )
    except (Exception, psycopg2.Error) as error:
        print(f"essentials.py - send_exection_alert - {traceback.format_exc()}")


# Create your views here.

@api_view(['GET', 'POST'])
def ping(request):
    try:
        if request.method == 'GET':
            servicePing = Ping.objects.all()
            container_id = request.query_params.get('container_id', None)
            if container_id is not None:
                servicePing = servicePing.filter(container_id__icontains=container_id)

            ping_serializer = PingSerializer(servicePing, many=True)
            return JsonResponse(ping_serializer.data, safe=False)

        elif request.method == 'POST':
            # logger.info(request.body)
            ping_data = JSONParser().parse(request)
            ping_serializer = PingSerializer(data=ping_data)
            container_id=ping_data['container_id']
            if ping_serializer.is_valid():
                ping_serializer.save()
                # logger.info(f"success for - {ping_data}")
                return JsonResponse(ping_serializer.data, status=status.HTTP_201_CREATED)
            else:
                # logger.info(f"success1 for - {ping_data}")
                ping_serializer = PingSerializer(Ping.objects.get(pk=container_id), data=ping_data)
                if ping_serializer.is_valid():
                    ping_serializer.save()
                    return JsonResponse(ping_serializer.data)
                # logger.error(f"fail for - {ping_data}")
                return JsonResponse(ping_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except:
        print("Error in Receiving Ping")
    finally:
        pass
#        db_delete_ping()
#        time.sleep(2)
#        db_delete_status()
#        time.sleep(2)
#        db_update_status()
#        time.sleep(2)
#        db_select()
#        time.sleep(2)
    # logger.error(f"request failed")
    return JsonResponse({"error": "error"}, status=status.HTTP_400_BAD_REQUEST)


