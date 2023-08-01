from django.shortcuts import render
import psycopg2
from django.db import connection
from django.db import connections
from datetime import datetime
from datetime import timedelta
from status.essentials import *


# queue_dict={}
def db_queue_table():
    logger.info("Checking Queue Table entries")
    queue_dict = {}
    today_date = datetime.today()
    today_date_str = datetime.strftime(today_date, '%Y-%m-%d')

    try:
        cursor = connections['queue'].cursor()

        postgreSQL_select_Query = "select task_type,count(1) from investo2o.queue_table group by task_type order by task_type;"
        postgreSQL_select_Query_today_data = "select task_type,count(1) from investo2o.queue_table where upload_time >= '{0}' group by task_type order by task_type;".format(
            today_date_str)

        cursor.execute(postgreSQL_select_Query)
        queue_table_records = cursor.fetchall()

        cursor.execute(postgreSQL_select_Query_today_data)
        queue_table_records_today_data = cursor.fetchall()

        for row in queue_table_records:
            key = row[0]
            queue_dict.setdefault(key, [])
            queue_dict[key].append(row[1])

        for row in queue_table_records_today_data:
            key = row[0]
            queue_dict.setdefault(key, [])
            queue_dict[key].append(row[1])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error while fetching data from Queue Table")

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()

    return queue_dict


# db_queue_table()
