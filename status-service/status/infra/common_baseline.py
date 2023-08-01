import json

import psycopg2
from django.db import connection
from django.db import connections
from status.essentials import *

region = properties["AWS_REGION"]

service_names = ("ec2", "rds", "subnet", "sg", "nacl", "route")

column_list = {}
array_indexes = dict()

column_list["ec2"] = (
    "instance_id",
    "instance_name",
    "instance_type",
    "instance_state",
    "subnet",
    "security_group",
    "instance_iam",
    "deleted"
)
array_indexes["ec2"] = (column_list["ec2"].index("security_group") + 1,)

column_list["rds"] = (
    "instance_id",
    "endpoint",
    "instance_class",
    "subnet",
    "security_group",
    "engine",
    "engine_version",
    "storage_encrypted",
    "availability_zone",
    "db_parameter_groups",
    "multi_az",
    "deleted"
)
array_indexes["rds"] = (
    column_list["rds"].index("subnet") + 1,
    column_list["rds"].index("security_group") + 1,
)

column_list["subnet"] = ("subnet_id", "subnet_name", "cidr_block", "public_ip", "availability_zone", "deleted")
array_indexes["subnet"] = ()

column_list["sg"] = ("sg_id", "sg_name", "inbound_rules", "deleted")
array_indexes["sg"] = (column_list["sg"].index("inbound_rules") + 1,)

column_list["nacl"] = ("nacl_id", "nacl_name", "entries", "deleted")
array_indexes["nacl"] = (column_list["nacl"].index("entries") + 1,)

column_list["route"] = ("route_id", "route_name", "routes", "subnet_ids", "deleted")
array_indexes["route"] = (column_list["route"].index("routes") + 1,column_list["route"].index("subnet_ids") + 1,)


def common_baseline(service_name):
    logger.info(f"Fetching the Baseline Records for {service_name}")
    baseline_dict = {}
    try:
        cursor = connections["default"].cursor()
        baseline_select = "SELECT {cl},created_on FROM aws.{tn}_baseline WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list[service_name]), tn=service_name
        )
        cursor.execute(baseline_select)
        baseline_record = cursor.fetchall()
        for row in baseline_record:
            rows = list(row)
            del row
            row = rows
            del rows

            key = row[0]

            for x in array_indexes[service_name]:
                row[x - 1] = json.loads(row[x - 1])

            baseline_dict.setdefault(key, [])
            baseline_dict[key].append("green")
            for x in range(1, len(row)):
                baseline_dict[key].append(row[x])
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the baseline records")
    finally:
        if connection:
            cursor.close()
            connection.close()

    return baseline_dict


def diff(service_name, only_diff=False):
    if service_name not in service_names:
        return None
    logger.info(
        f"Fetching the Difference in Baseline and Current Records for {service_name}"
    )
    baseline_records = ()
    baseline_dict = common_baseline(service_name)
    try:
        cursor = connections["default"].cursor()
        baseline_select = (
            "SELECT DISTINCT {pk} FROM aws.{sn}_baseline FULL OUTER JOIN aws.{sn}_current USING ({cl}) "
            "WHERE (NOT deleted or (NOT aws.{sn}_baseline.deleted and NOT aws.{sn}_current.deleted)) and (aws.{sn}_baseline.{pk} IS NULL OR aws.{sn}_current.{pk} IS NULL);".format(
                cl=",".join(column_list[service_name]),
                sn=service_name,
                pk=column_list[service_name][0],
            )
        )

        cursor.execute(baseline_select)
        baseline_records = cursor.fetchall()
        new_instances = {}
        for record in baseline_records:
            key = record[0]
            if key not in baseline_dict:
                diff_select = "SELECT {cl},created_on FROM aws.{sn}_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on;".format(
                    cl=",".join(column_list[service_name]),
                    sn=service_name,
                    pk=column_list[service_name][0],
                    value=key,
                )
                cursor.execute(diff_select)
                row = cursor.fetchall()[0]
                rows = list(row)
                del row
                row = rows
                del rows

                new_instances.setdefault(key, [])
                # Blue Color for New Records
                new_instances[key].append("#0100FF")
                for x in array_indexes[service_name]:
                    row_type = type(row[x - 1])
                    # logger.info(f"{service_name} - row[{x - 1}] - type is {row_type}")
                    if row_type == str:
                        # logger.info(f"common - {service_name} - row[{x - 1}] - type is str")
                        row[x - 1] = json.loads(row[x - 1])
                for x in range(1, len(row)):
                    new_instances[key].append(row[x])
            else:
                # Red Color for Difference Records
                baseline_dict.get(key)[0] = "#FF1F00"

        baseline_dict.update(new_instances)
        baseline_dict = dict(sorted(baseline_dict.items(), key=lambda x: x[1][0]))
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the difference records")
    finally:
        if connection:
            cursor.close()
            connection.close()

    if only_diff:
        return baseline_records

    return baseline_dict


def get_log(service_names=service_names, is_not_limit=False):
    service_log = {}
    try:
        cursor = connections["default"].cursor()
        for service_name in service_names:
            extra = "LIMIT 10" if not is_not_limit else ""
            baseline_select = "SELECT to_char(created_on, 'Mon DD YYYY HH24:MI:SS'),instance_id, log , username FROM aws.audit_log WHERE service_name = '{}' ORDER BY created_on desc {};".format(
                service_name, extra
            )
            cursor.execute(baseline_select)
            baseline_record = cursor.fetchall()
            for row in baseline_record:
                key = service_name
                service_log.setdefault(key, [])
                temp = []
                for x in range(len(row)):
                    temp.append(row[x])
                service_log[key].append(temp)
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the log records")
    finally:
        if connection:
            cursor.close()
            connection.close()

    return service_log
