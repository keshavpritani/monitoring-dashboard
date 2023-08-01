from django.db import models

# Create your models here.
class Instances(models.Model):
    container_id = models.CharField(max_length=20,primary_key=True)
    service_name = models.CharField(max_length=50)
    time = models.DateTimeField(auto_now=True)
from django.db import models

# Create your models here.
