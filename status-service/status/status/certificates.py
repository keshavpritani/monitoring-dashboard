import psycopg2
from django.db import connection
from status.essentials import *
import datetime


def db_certificates_status():
    certificates = {}
    logger.info("Checking DB Certificates Status")
    try:
        cursor = connection.cursor()
        postgreSQL_select_Query = "select unique_id, name, expiry_date, last_updated_on, last_updated_by from status.certificates order by expiry_date;"
        cursor.execute(postgreSQL_select_Query)
        certificates_status = cursor.fetchall()
        for certificate in certificates_status:
            id = certificate[0]
            Name = certificate[1]
            ExpiryDate = certificate[2]
            certificates.setdefault(id, {})
            certificates[id]['Name'] = Name
            certificates[id]['ExpiryDate'] = ExpiryDate
            certificates[id]['LastUpdateOn'] = certificate[3]
            certificates[id]['LastUpdateBy'] = certificate[4]
            if ExpiryDate is None:
                continue
            now = datetime.datetime.now()
            today = datetime.date.today()
            days_left = (ExpiryDate - today).days
            if now.hour == 4 and now.minute == 0:
                msg = "Certificate {} is about to expire".format(Name)
                extra_message = ", {} days left".format(days_left)
                logger.info(msg)
                color = ""
                if days_left <= 0:
                    continue
                if days_left <= 15:
                    color = "Red"
                elif days_left <= 30:
                    color = "Yellow"
                if color != "":
                    send_alert(msg, color, "certificate", extra_message)
    except (Exception, psycopg2.Error) as error:
        send_exection_alert(f"Failed to fetch certificates from DB")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return certificates
