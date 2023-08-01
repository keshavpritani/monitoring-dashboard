import boto3
from django.http import HttpResponse

from infra.common_baseline import *

ec2_client = boto3.client("ec2", region_name=region)


def ec2_current_insert(tn="current"):
    logger.info(f"Inserting the Current Records for EC2 - Type - {tn}")
    reservations = ec2_client.describe_instances().get("Reservations")
    active_instance_ids = ()
    try:
        cursor = connections["default"].cursor()
        for reservation in reservations:
            for instance in reservation["Instances"]:
                if "InstanceLifecycle" in instance and instance["InstanceLifecycle"] == "spot": continue
                instance_id = instance["InstanceId"]
                instance_type = instance["InstanceType"] if "InstanceType" in instance else ""
                instance_subnet = instance["SubnetId"] if "SubnetId" in instance else ""
                SecurityGroups = instance["SecurityGroups"] if "SecurityGroups" in instance else []
                instance_state = instance["State"]["Name"] if "State" in instance else ""
                instance_iam = "/".join(str(instance["IamInstanceProfile"]["Arn"]).split("/")[1:]) if "IamInstanceProfile" in instance else ""
                instance_sg = []
                for x in SecurityGroups:
                    instance_sg.append(x.get("GroupId"))
                instance_name = ""
                if "Tags" in instance.keys():
                    instance_name = list(
                        filter(lambda x: x["Key"] == "Name", instance["Tags"])
                    )[0].get("Value")
                ec2_current_insert = "INSERT INTO aws.ec2_{} (instance_id, instance_name, instance_type, instance_state, subnet, security_group, instance_iam, created_on) VALUES (%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT (instance_id) DO UPDATE SET instance_name = excluded.instance_name".format(tn)
                if instance_type != "": ec2_current_insert += ", instance_type = excluded.instance_type"
                if instance_state != "": ec2_current_insert += ", instance_state = excluded.instance_state"
                if instance_subnet != "": ec2_current_insert += ", subnet = excluded.subnet"
                if len(instance_sg) != 0: ec2_current_insert += ", security_group = excluded.security_group"
                if instance_iam != "": ec2_current_insert += ", instance_iam = excluded.instance_iam"
                ec2_current_insert += ", deleted = 'f', created_on = now();"
                cursor.execute(
                    ec2_current_insert,
                    (
                        instance_id,
                        instance_name,
                        instance_type,
                        instance_state,
                        instance_subnet,
                        json.dumps(instance_sg),
                        instance_iam,
                    ),
                )

                active_instance_ids += (instance_id,)
        if len(active_instance_ids) > 0:
            deleted_instance_select = (
                "SELECT instance_id FROM aws.ec2_{} WHERE instance_id not in (".format(
                    tn
                )
            )
            for x in active_instance_ids:
                deleted_instance_select += "'{}',".format(x)
            deleted_instance_select = deleted_instance_select[0:-1]
            deleted_instance_select += ");"
            cursor.execute(deleted_instance_select)
            deleted_instance = cursor.fetchall()
            for x in deleted_instance:
                cursor.execute(
                    "UPDATE aws.ec2_{} set deleted = 't' WHERE instance_id = '{}'".format(tn, x[0])
                )
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to insert the EC2 Current Records")
    finally:
        if connection:
            cursor.close()
            connection.commit()


def ec2_current_merge(only_diff=False, username=""):
    logger.info(
        f"Fetching Current Diff Records for EC2 - Only Diff - {only_diff} - Username - {username}"
    )
    ec2_diff = diff("ec2", True)
    cursor = connections["default"].cursor()
    only_diff_dict = {}
    for instance_id in ec2_diff:
        diff_select = "SELECT {cl} FROM aws.ec2_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["ec2"]),
            pk=column_list["ec2"][0],
            value=instance_id[0],
        )

        cursor.execute(diff_select)
        current_instance = cursor.fetchone()

        diff_select = "SELECT {cl} FROM aws.ec2_baseline WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["ec2"]),
            pk=column_list["ec2"][0],
            value=instance_id[0],
        )
        cursor.execute(diff_select)
        baseline_instance = cursor.fetchone()
        name = ""
        flag = False
        if baseline_instance is None:
            name = current_instance[1]
            desc = "New Instance Created"
            flag = True
        elif current_instance is None:
            name = baseline_instance[1]
            desc = "Instance Deleted"
            flag = True
        else:
            name = current_instance[1]
            desc = ""
            for x in range(len(column_list["ec2"])):
                if current_instance[x] != baseline_instance[x]:
                    flag = True
                    if x + 1 in array_indexes["ec2"]:
                        curr = json.loads(current_instance[x])
                        base = json.loads(baseline_instance[x])
                        # curr = current_instance[x]
                        # base = baseline_instance[x]
                        deleted = list(set(base) - set(curr))
                        added = list(set(curr) - set(base))

                        if len(deleted) > 0:
                            desc += (
                                column_list["ec2"][x]
                                + " = "
                                + "Deleted - "
                                + ";".join(deleted)
                                + "<br>"
                            )
                        if len(added) > 0:
                            desc += (
                                column_list["ec2"][x]
                                + " = "
                                + "Added - "
                                + ";".join(added)
                                + "<br>"
                            )
                    else:
                        desc += (
                            column_list["ec2"][x]
                            + " = "
                            + (baseline_instance[x] if baseline_instance[x] else "None")
                            + " --> "
                            + (current_instance[x] if current_instance[x] else "None")
                            + "<br>"
                        )
        if not flag:
            logger.info("EC2 - Flag falsed")
            continue
        if desc == "":
            desc = "No Changes"
            continue
        only_diff_dict[instance_id[0]] = [name, desc]

        if not only_diff:
            logger.info("Inserting the Diff Records for EC2")
            if current_instance is not None:
                ec2_current_insert = "INSERT INTO aws.ec2_baseline (instance_id, instance_name, instance_type, instance_state, subnet, security_group, instance_iam, deleted, created_on) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT (instance_id) DO UPDATE SET instance_name = excluded.instance_name, instance_type = excluded.instance_type, instance_state = excluded.instance_state, subnet = excluded.subnet, security_group = excluded.security_group, instance_iam = excluded.instance_iam, deleted = excluded.deleted, created_on = now();"
                # current_instance = list(current_instance)
                # for x in array_indexes["ec2"]:
                #     current_instance[x -
                #                      1] = json.dumps(current_instance[x - 1])
            else:
                ec2_current_insert = (
                    "UPDATE aws.ec2_baseline set deleted = 't' WHERE instance_id = '{value}'".format(
                        value=instance_id[0]
                    )
                )

            try:
                cursor.execute(ec2_current_insert, current_instance)
                audit_log_insert = "INSERT INTO aws.audit_log (service_name, instance_id, log, username) VALUES (%s, %s, %s, %s)"
                cursor.execute(
                    audit_log_insert, ("ec2", instance_id[0], desc, username)
                )
            except (Exception, psycopg2.Error) as error:
                send_exection_alert("Failed to insert the EC2 Diff Records")
    if connection:
        # cursor.close()
        connection.commit()

    return only_diff_dict


def ec2_current():
    logger.info("Fetching the Current Records for EC2")

    ec2_current_dict = {}

    try:
        cursor = connections["default"].cursor()
        ec2_current_select = "SELECT {cl}, created_on FROM aws.ec2_current WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["ec2"])
        )
        cursor.execute(ec2_current_select)
        ec2_current_records = cursor.fetchall()

        for row in ec2_current_records:
            rows = list(row)
            del row
            row = rows
            del rows

            for x in array_indexes["ec2"]:
                row_type = type(row[x - 1])
                # logger.info(f"EC2 - row[{x - 1}] - type is {row_type}")
                if row_type == str:
                    # logger.info(f"EC2 - row[{x - 1}] - type is str")
                    row[x - 1] = json.loads(row[x - 1])

            key = row[0]
            ec2_current_dict.setdefault(key, [])
            ec2_current_dict[key].append("green")
            for x in range(1, len(row) - 1):
                ec2_current_dict[key].append(row[x])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the EC2 Current Records")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return ec2_current_dict
