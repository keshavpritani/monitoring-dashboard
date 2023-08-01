
from django.contrib import admin
from django.urls import path
from django.urls import re_path, include

urlpatterns = [
    re_path(r'^', include('ping.urls')),
    # re_path(r'^', include('instances.urls')),
]
