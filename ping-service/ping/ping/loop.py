import threading
from ping.viewUpdate import *
import time


def update_service_final():
    threading.Timer(30, update_service_final).start()
    db_delete_ping()
    time.sleep(2)
    db_delete_status()
    time.sleep(2)
    db_update_status()
    print("Hello, World!")


def update_docker_image():
    docker_images()
    threading.Timer(60, update_docker_image).start()

def start_update_service_final():
    threading.Thread(target=update_service_final).start()
    # threading.Thread(target=update_docker_image).start()