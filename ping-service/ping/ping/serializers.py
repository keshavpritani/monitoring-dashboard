from rest_framework import serializers
from .models import Ping

class PingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ping
        fields = '__all__'
