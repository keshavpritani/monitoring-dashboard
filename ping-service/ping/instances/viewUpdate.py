import psycopg2
from django.db import connection

def db_delete_instances():
     try:
       cursor = connection.cursor()

       postgreSQL_delete_Query = "delete from instances_instances where time < NOW() - interval '900 SECOND';"

       cursor.execute(postgreSQL_delete_Query)
       connection.commit()
       deleted_rows = cursor.rowcount
       print("deleted rows",deleted_rows)

     except (Exception, psycopg2.Error) as error :
         print (error)

     finally:
        #closing database connection.
        if connection:
            cursor.close()
            connection.close()

def db_delete_status():
     try:
       cursor = connection.cursor()

       postgreSQL_delete_Query = "update service_final_instances set up_nodes=0 where modified_time < NOW() - interval '910 SECOND';"

       cursor.execute(postgreSQL_delete_Query)
       connection.commit()
       updated_rows = cursor.rowcount
       print("Updated rows",updated_rows)

     except (Exception, psycopg2.Error) as error :
         print (error)

     finally:
        #closing database connection.
        if connection:
            cursor.close()
            connection.close()

def db_update_status():
     try:
       cursor = connection.cursor()

       postgreSQL_select_Query = "with abc as ( select count(1) as sum, service_name  from instances_instances group by service_name) update service_final_instances as t set modified_time=current_timestamp,up_nodes =a.sum FROM abc a where t.service_name=a.service_name;"
       cursor.execute(postgreSQL_select_Query)
       connection.commit()
       updated_rows = cursor.rowcount
       print(updated_rows)

     except (Exception, psycopg2.Error) as error :
         print (error)

     finally:
        #closing database connection.
        if connection:
            cursor.close()
            connection.close()

def db_select():
    dict={}
    try:
       cursor = connection.cursor()

       postgreSQL_select_Query = "select * from service_final_instances;"

       cursor.execute(postgreSQL_select_Query)
       mobile_records = cursor.fetchall()

       print("Print each row and it's columns values")
       for row in mobile_records:
           if row[2] >= row[1]:
               dict[row[0]] = 'Green'
           elif row[1] -1 == row[2] and row[2]!=0:
               dict[row[0]] = 'Yellow'
           else:
               dict[row[0]] = 'Red'
       print(dict)

    except (Exception, psycopg2.Error) as error :
        print (error)

    finally:
        #closing database connection.
        if connection:
            cursor.close()
            connection.close()
