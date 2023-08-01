"""alert_service URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from django.conf.urls import include
from alert import views as alert_views
from alert import silent_alert as silent_alert
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("alert/", alert_views.get_console),
    path("alert/monitor", alert_views.monitor),
    path("alert/logout/", LogoutView.as_view()),
    path("alert/send-alert/",alert_views.receive_alert),
    path("alert/grafana-alert/",alert_views.grafana_alert),
    path("alert/billing-alert/",alert_views.billing_alert),
    path("alert/update-silent-time/",alert_views.update_silent_time),
    path("alert/update-billing-ignore-capacity/",alert_views.update_billing_ignore_capacity),
    path("alert/toggle_silent_alert/<str:status>/", silent_alert.toggle_silent_alert),
    path("alert/silent/", silent_alert.silent_specific_alert),
    path("alert/release-silent/<str:status>/", silent_alert.release_silent_alert),
    path("alert/remove-service/", alert_views.remove_service),
]
