import psycopg2
from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser
from rest_framework import status
from instances.models import Instances
from instances.serializers import InstancesSerializer
from rest_framework.decorators import api_view
from instances.viewUpdate import *
import time

# Create your views here.

@api_view(['GET', 'POST'])
def instances(request):
    try:
        if request.method == 'GET':
            instancesPing = Instances.objects.all()
            container_id = request.query_params.get('container_id', None)
            if container_id is not None:
                instancesPing = instancesPing.filter(container_id__icontains=container_id)

            instances_serializer = InstancesSerializer(instancesPing, many=True)
            return JsonResponse(instances_serializer.data, safe=False)

        elif request.method == 'POST':
            ping_data = JSONParser().parse(request)
            instances_serializer = InstancesSerializer(data=ping_data)
            container_id=ping_data['container_id']
            if instances_serializer.is_valid():
                instances_serializer.save()
                return JsonResponse(instances_serializer.data, status=status.HTTP_201_CREATED)
            else:
                instances_serializer = InstancesSerializer(Instances.objects.get(pk=container_id), data=ping_data)
                if instances_serializer.is_valid():
                    instances_serializer.save()
                    return JsonResponse(instances_serializer.data)
                return JsonResponse(instances_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            return JsonResponse(instances_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    finally:
        pass
#        db_delete_ping()
#        db_delete_status()
#        db_update_status()
#        db_select()


from django.shortcuts import render

# Create your views here.
