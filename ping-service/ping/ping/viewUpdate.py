import psycopg2
from django.db import connection
import json
import requests
from datetime import datetime


def db_delete_ping():
    try:
        cursor = connection.cursor()

        postgreSQL_delete_Query = "delete from ping_ping where time < NOW() - interval '35 SECOND';"

        cursor.execute(postgreSQL_delete_Query)
        connection.commit()
#       deleted_rows = cursor.rowcount
#       print("deleted rows",deleted_rows)

    except (Exception, psycopg2.Error) as error:
        print(error)

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()


def db_delete_status():
    try:
        cursor = connection.cursor()

        postgreSQL_delete_Query = "update service_final set up_nodes=0 where modified_time < NOW() - interval '35 SECOND';"

        cursor.execute(postgreSQL_delete_Query)
        connection.commit()
#       updated_rows = cursor.rowcount
#       print("Updated rows",updated_rows)

    except (Exception, psycopg2.Error) as error:
        print(error)

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()


def db_update_status():
    try:
        cursor = connection.cursor()

        postgreSQL_select_Query = "with abc as ( select count(1) as sum, service_name  from ping_ping group by service_name) update service_final as t set modified_time=current_timestamp,up_nodes =a.sum FROM abc a where t.service_name=a.service_name;"
        cursor.execute(postgreSQL_select_Query)
        connection.commit()
#       updated_rows = cursor.rowcount
#       print(updated_rows)

    except (Exception, psycopg2.Error) as error:
        print(error)

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()


def db_select():
    dict = {}
    try:
        cursor = connection.cursor()

        postgreSQL_select_Query = "select * from service_final;"

        cursor.execute(postgreSQL_select_Query)
        mobile_records = cursor.fetchall()

        print("Print each row and it's columns values")
        for row in mobile_records:
            if row[2] >= row[1]:
                dict[row[0]] = 'Green'
            elif row[1] - 1 == row[2] and row[2] != 0:
                dict[row[0]] = 'Yellow'
            else:
                dict[row[0]] = 'Red'
#       print(dict)

    except (Exception, psycopg2.Error) as error:
        print(error)

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()


def docker_images():
    try:
        cursor = connection.cursor()
        cursor.execute(
            "select property_value from status.properties where property_key = 'DOCKER_REGISTRY_URL';")
        docker_url = cursor.fetchone()[0]

        cursor.execute(
            "select property_value from status.properties where property_key = 'DOCKER_REGISTRY_USERNAME';")
        username = cursor.fetchone()[0]

        cursor.execute(
            "select property_value from status.properties where property_key = 'DOCKER_REGISTRY_PASSWORD';")
        password = cursor.fetchone()[0]

        url = f"{docker_url}/v2"
        auth = (username, password)

        cursor.execute(
            "select property_value from status.properties where property_key like 'DOCKER_IMAGE_TAG%';")
        tags_temp = cursor.fetchall()

        tags = []
        for i in tags_temp:
            tags.append(i[0])

        data_str = requests.get(f"{url}/_catalog?n=500", auth=auth).text
        data_str = json.loads(data_str)
        for i in data_str['repositories']:
            print(i)
            if 'services' not in i and 'batchapps' not in i and 'frontend' not in i:
                continue
            for tag in tags:
                data = requests.get(
                    f"{url}/{i}/manifests/{tag}", auth=auth).text
                data = json.loads(data)
                if 'history' in data:
                    date = json.loads(data['history'][0]['v1Compatibility'])[
                        'created']
                    date = date.split('.')
                    date = datetime.strptime(date[0], '%Y-%m-%dT%H:%M:%S')
                    postgreSQL_select_Query = "INSERT INTO docker_images_status (image_name, tag, last_updated) VALUES (%s, %s, %s) ON CONFLICT (image_name, tag) DO UPDATE SET last_updated=%s;"
                    cursor.execute(postgreSQL_select_Query,
                                   (i, tag, date, date))
        connection.commit()
    except (Exception, psycopg2.Error) as error:
        print(error)
    finally:
        if connection:
            cursor.close()
            connection.close()
