import psycopg2
from django.db import connection
from status.essentials import *


def db_urls():
    db_urls = {}

    try:
        cursor = connection.cursor()

        postgreSQL_select_Query = "select name,url,env from links.urls order by name;"
        cursor.execute(postgreSQL_select_Query)
        batchapp_table_records = cursor.fetchall()

        for row in batchapp_table_records:
            key = row[1]
            db_urls.setdefault(key, [])
            db_urls[key].append(row[0])
            db_urls[key].append(row[2])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the URLs from DB")

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()

    return (db_urls)
