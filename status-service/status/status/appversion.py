import json
from django.db import connection

def appversioncomp():
    l={}
    appversion=[]
    cursor = connection.cursor()
    cursor.execute(" select * from application_versions ORDER BY hostname ASC,components ASC")
    row = cursor.fetchone()
    while row is not None:
        jsn1=row[0]
        jsn2=row[1]
        jsn3=json.loads(jsn2)
        jsn4=str(jsn3)[1:-1]
        l={"hostname":jsn1,"component":jsn4}
        appversion.append(l)
        row = cursor.fetchone()
    cursor.close()
    return appversion
