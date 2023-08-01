from django.urls import re_path
from ping import views
from ping import loop


urlpatterns = [
    re_path(r'^api/serviceping$', views.ping),
]

loop.start_update_service_final()
