from django.conf.urls import url
from instances import views
from instances import loop


urlpatterns = [

    url(r'^api/instanceping$', views.instances),


]

loop.update_service_final()
