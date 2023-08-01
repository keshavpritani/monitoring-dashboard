from django.shortcuts import render

from status.links import *
from status.essentials import logger


def db_select(request):
    user_name = "Unknown"
    if request.user.is_authenticated:
        user_name = request.user.get_full_name()
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    ip = ""
    else_ip = ""
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]

    else_ip = request.META.get("REMOTE_ADDR")

    logger.info(f"link_views.py - db_select - User : {user_name} - ip - {ip} - {else_ip}")

    urls = db_urls()
    return render(request, 'status/links.html', {'urls': urls})
