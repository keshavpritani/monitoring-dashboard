from cmath import log
import boto3

from infra.common_baseline import *


def nacl_current_insert(tn="current"):
    logger.info(f"Inserting the Current Records for NACL - Type - {tn}")
    ec2_client = boto3.client("ec2", region_name=region)
    nacls = ec2_client.describe_network_acls().get("NetworkAcls")
    active_instance_ids = ()

    try:
        cursor = connections["default"].cursor()

        for nacl in nacls:

            Entries = nacl["Entries"]
            NetworkAclId = nacl["NetworkAclId"]
            naclName = ""
            if "Tags" in nacl.keys():
                if len(nacl["Tags"]) > 0:
                    naclName = list(filter(lambda x: x["Key"] == "Name", nacl["Tags"]))[
                        0
                    ].get("Value")

            nacl_current_insert = "INSERT INTO aws.nacl_{} (nacl_id, nacl_name, entries, created_on) VALUES (%s,%s,%s,now()) ON CONFLICT (nacl_id) DO UPDATE SET entries = excluded.entries, nacl_name = excluded.nacl_name, deleted = 'f', created_on = now();".format(
                tn
            )
            record_to_insert = (NetworkAclId, naclName, json.dumps(Entries))
            cursor.execute(nacl_current_insert, record_to_insert)

            active_instance_ids += (NetworkAclId,)
        if len(active_instance_ids) > 0:
            deleted_instance_select = (
                "SELECT nacl_id FROM aws.nacl_{} WHERE nacl_id not in (".format(tn)
            )
            for x in active_instance_ids:
                deleted_instance_select += "'{}',".format(x)
            deleted_instance_select = deleted_instance_select[0:-1]
            deleted_instance_select += ");"
            cursor.execute(deleted_instance_select)
            deleted_instance = cursor.fetchall()
            for x in deleted_instance:
                cursor.execute(
                    "UPDATE aws.nacl_{} set deleted = 't' WHERE nacl_id = '{}'".format(tn, x[0])
                )
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to insert the NACL Current Records")
    finally:
        if connection:
            cursor.close()
            connection.commit()


def nacl_current_merge(only_diff=False, username=""):
    logger.info(
        f"Fetching Current Diff Records for NACL - Only Diff - {only_diff} - Username - {username}"
    )
    nacl_diff = diff("nacl", True)
    cursor = connections["default"].cursor()
    only_diff_dict = {}
    for instance_id in nacl_diff:
        diff_select = "SELECT {cl} FROM aws.nacl_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on;".format(
            cl=",".join(column_list["nacl"]),
            pk=column_list["nacl"][0],
            value=instance_id[0],
        )
        cursor.execute(diff_select)
        current_instance = cursor.fetchone()

        diff_select = "SELECT {cl} FROM aws.nacl_baseline WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on;".format(
            cl=",".join(column_list["nacl"]),
            pk=column_list["nacl"][0],
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
            for x in range(len(column_list["nacl"])):
                if current_instance[x] != baseline_instance[x]:
                    if x + 1 in array_indexes["nacl"]:
                        flag = True
                        curr = json.loads(current_instance[x])
                        base = json.loads(baseline_instance[x])
                        # curr = current_instance[x]
                        # base = baseline_instance[x]

                        deleted = list(map(str, [y for y in base if y not in curr]))
                        added = list(map(str, [y for y in curr if y not in base]))

                        if len(deleted) > 0:
                            desc += (
                                column_list["nacl"][x]
                                + " = "
                                + "Deleted "
                                + " - "
                                + ";".join(deleted)
                                + "<br>"
                            )
                        if len(added) > 0:
                            desc += (
                                column_list["nacl"][x]
                                + " = "
                                + "Added "
                                + " - "
                                + ";".join(added)
                                + "<br>"
                            )
                    else:
                        desc += (
                            column_list["nacl"][x]
                            + " = "
                            + (baseline_instance[x] if baseline_instance[x] else "None")
                            + " --> "
                            + (current_instance[x] if current_instance[x] else "None")
                            + "<br>"
                        )
        if not flag:
            logger.info("NACL - Flag falsed")
            continue
        if desc == "":
            desc = "No Changes"
            continue
        only_diff_dict[instance_id[0]] = [name, desc]
        if not only_diff:
            logger.info("Inserting the Diff Records for NACL")
            if current_instance is not None:
                nacl_current_insert = "INSERT INTO aws.nacl_baseline (nacl_id, nacl_name, entries, deleted, created_on) VALUES (%s,%s,%s,%s,now()) ON CONFLICT (nacl_id) DO UPDATE SET entries = excluded.entries, nacl_name = excluded.nacl_name, deleted = excluded.deleted, created_on = now();"
                # current_instance = list(current_instance)
                # for x in array_indexes["nacl"]:
                #     current_instance[x -
                #                      1] = json.dumps(current_instance[x - 1])
            else:
                nacl_current_insert = (
                    "UPDATE aws.nacl_baseline set deleted = 't' WHERE nacl_id = '{value}'".format(
                        value=instance_id[0]
                    )
                )
            try:
                cursor.execute(nacl_current_insert, current_instance)
                audit_log_insert = "INSERT INTO aws.audit_log (service_name,instance_id, log,username) VALUES (%s, %s, %s,%s)"
                cursor.execute(
                    audit_log_insert, ("nacl", instance_id[0], desc, username)
                )
            except (Exception, psycopg2.Error) as error:
                send_exection_alert("Failed to insert the NACL Diff Records")
    if connection:
        # cursor.close()
        connection.commit()

    return only_diff_dict


def nacl_current():
    logger.info("Fetching the Current Records for NACL")
    nacl_current_dict = {}

    try:
        cursor = connections["default"].cursor()
        nacl_current_select = "SELECT {cl}, created_on FROM aws.nacl_current WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["nacl"])
        )
        cursor.execute(nacl_current_select)
        nacl_current_record = cursor.fetchall()

        for row in nacl_current_record:
            rows = list(row)
            del row
            row = rows
            del rows

            key = row[0]
            for x in array_indexes["nacl"]:
                row_type = type(row[x - 1])
                # logger.info(f"NACL - row[{x - 1}] - type is {row_type}")
                if row_type == str:
                    # logger.info(f"NACL - row[{x - 1}] - type is str")
                    row[x - 1] = json.loads(row[x - 1])

            nacl_current_dict.setdefault(key, [])
            nacl_current_dict[key].append("green")
            for x in range(1, len(row) - 1):
                nacl_current_dict[key].append(row[x])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the Current Records for NACL")

    finally:
        # closing database connection.
        if connection:
            cursor.close()
            connection.close()

    return nacl_current_dict
