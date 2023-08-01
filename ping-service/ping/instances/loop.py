import threading
from instances.viewUpdate import *
import time

def update_service_final():
  threading.Timer(900, update_service_final).start()
  db_delete_instances()
  time.sleep(2)
  db_delete_status()
  time.sleep(2)
  db_update_status()
  print ("Hello, World! Instances")
