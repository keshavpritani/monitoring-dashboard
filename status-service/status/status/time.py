import psycopg2
from django.db import connection
from datetime import datetime, timedelta
import pytz
from status.essentials import *

def db_time():
    try:

        # Last Update Time
        time = connection.cursor()
        time_select_Query = "select MAX(time) from ping_ping;"
        time.execute(time_select_Query)
        time_ping = time.fetchall()

        time_ping_utc_obj = time_ping[0][0]
        time_ping_utc = time_ping[0][0].strftime('%m/%d/%Y %H:%M:%S')

        # time_ping_ist_obj = time_ping[0][0] + timedelta(minutes=330)
        # time_ping_ist = time_ping_ist_obj.strftime('%m/%d/%Y %H:%M:%S')

# Current Time
        UTC_now = pytz.utc
        datetime_utc_obj = datetime.now(UTC_now)
#       datetime_utc = datetime_utc_obj.strftime('%m/%d/%Y %H:%M:%S')

#       IST_now = pytz.timezone('Asia/Kolkata')
#       datetime_ist_obj = datetime.now(IST_now)


# Time Difference

        duration = datetime_utc_obj - time_ping_utc_obj
        str_delta = str(duration.total_seconds())
        str_delta = str_delta.split('.')[0]
        last_updated_time = "Last updated {} sec ago, {}".format(
            str_delta, time_ping_utc)
        return last_updated_time

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the time from DB")

    finally:
        # closing database connection.
        if connection:
            time.close()
            cursor.close()
            connection.close()
