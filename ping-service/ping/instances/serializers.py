from rest_framework import serializers
from .models import Instances

class InstancesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instances
        fields = '__all__'
