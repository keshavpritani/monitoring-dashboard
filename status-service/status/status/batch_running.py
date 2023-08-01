from django.shortcuts import render
import psycopg2
from django.db import connection
from django.db import connections
from datetime import datetime
from status.essentials import *
from admin_console.views import mark_batchapps_done

alert_batchapps = {"RemoteScanningJob": 30, "APIOrderMonitoringJob": 30}
databases = ['vpn2', 'kpm', 'kyc', 'funds', 'kristaldata', 'reports', 'queue']

alert_counts={}

def db_batch_app_table():
    batchapp_dict = {}
    logger.info("Checking Batch App Table entries")
    for db in databases:
        if ENV in ("dev", "local") and db == "reports":
            continue
        try:
            cursor = connections[db].cursor()

            postgreSQL_select_Query = "select * from batchapps.batch_process_monitor where start_time > now() - (interval '30' day) order by state desc, start_time desc;"
            cursor.execute(postgreSQL_select_Query)
            batchapp_table_records = cursor.fetchall()

            BATCHAPPS_ALERT_THRESHOLD = int(get_property("BATCHAPPS_ALERT_THRESHOLD"))
            for row in batchapp_table_records:
                process_id = row[1]
                key = row[2]
                batchapp_dict.setdefault(key, [])
                batchapp_dict[key].append(row[6])
                batchapp_dict[key].append(process_id)
                batchapp_dict[key].append(db)

                start_date = row[4].strftime('%Y-%m-%d %H:%M:%S')
                batchapp_dict[key].append(start_date)
                if row[5] == None:
                    end_date = ""
                    if key in alert_batchapps.keys():
                        delta = datetime.now() - row[4]
                        alert_key = f'{db} - {key}'
                        if delta.total_seconds() >= (alert_batchapps[key] * 60):
                            delta = str(delta).split('.')[0]
                            color = "Red"
                            extra_msg = f' Running for {delta}'
                            flag = True
                            if alert_key not in alert_counts.keys() and BATCHAPPS_ALERT_THRESHOLD > 0:
                                alert_counts[alert_key] = 1
                            elif alert_key in alert_counts.keys() and alert_counts[alert_key] < BATCHAPPS_ALERT_THRESHOLD:
                                alert_counts[alert_key] += 1
                            else:
                                color="Green"
                                extra_msg = " Marking as Done"
                                mark_batchapps_done(process_id, db)
                                if alert_key in alert_counts.keys(): del alert_counts[alert_key]
                                if ENV != "prod": flag = False
                            if flag: send_alert(alert_key, color, "running_batch_app",extra_msg)
                else:
                    end_date = row[5].strftime('%Y-%m-%d %H:%M:%S')
                batchapp_dict[key].append(end_date)
                cursor.close()
        except (Exception, psycopg2.Error) as error:
            send_exection_alert("Error while Running Batchapps fetching data")
        finally:
            # closing database connection.
            if connections:
                cursor.close()
                connection.close()
        batchapp_dict = dict(sorted(batchapp_dict.items(),
                             key=lambda x: x[1][0], reverse=True))

    return (batchapp_dict)


# db_batch_app_table()
