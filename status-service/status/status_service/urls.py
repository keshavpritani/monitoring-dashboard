"""status_service URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from status.essentials import send_exection_alert

try:
    from django.contrib import admin
    from django.urls import path
    import status.views
    import status.link_views
    import infra.views
    import admin_console.views
    from django.conf.urls import include
    from django.contrib.auth.views import LogoutView
    import threading

    urlpatterns = [
        path("admin/", admin.site.urls),
        path("accounts/", include("allauth.urls")),
        path("urls/", status.link_views.db_select),

        path("status/", status.views.db_select),

        path("status/monitor", status.views.monitor),
        path("status/calling/", status.views.db_select_calling),
        path("status/refresh/solr/", status.views.refresh_data),
        # path("status/refresh/ecr/", status.views.ecr_docker_images_status),
        path("status/validate-docker-image/", status.views.validate_deployed_images),
        path("status/alert-logs/", status.views.alert_logs),
        path("status/403/", status.views.error_403),
        
        path("status/logout/", LogoutView.as_view()),
        
        path("infra/", infra.views.show_data),
        path("infra/send-mail", infra.views.send_mail),
        path("infra/refresh/<str:tn>", infra.views.refresh_data),
        path("infra/merge/<str:service_name>", infra.views.merge_data),
        path("infra/logs/<str:service_name>", infra.views.logs),
        
        path("status/admin/", admin_console.views.get_console),
        path("status/admin/new_service/", admin_console.views.new_service),
        path("status/admin/batchapp_done/<int:process_id>/<str:db>/",admin_console.views.batchapp_done),
    ]

    time = 0
    if status.views.ENV == "prod": time = 5
    threading.Thread(target = status.views.toggle_silent_alert_calling,args=("SYSTEM", "True", time)).start()
    # Calling Status Dashboard
    # def status_board_calling():
    #     time = int(status.views.get_property("CALLING_TIME"))
    #     sleep(time * 60)
    #     if time > 1:
    #         requests.get("http://localhost:8000/status/calling/")
    #     status_board_calling()
    # if status.views.ENV != "prod": threading.Thread(target=status_board_calling).start()
except Exception as e:
    send_exection_alert("Error while loading main urls.py")
