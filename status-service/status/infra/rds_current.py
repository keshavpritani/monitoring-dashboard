import boto3

from infra.common_baseline import *


def rds_current_insert(tn="current"):
    logger.info(f"Inserting the Current Records for RDS - Type - {tn}")
    rds_client = boto3.client("rds", region_name=region)
    DBInstances = rds_client.describe_db_instances().get("DBInstances")
    active_instance_ids = ()

    try:
        cursor = connections["default"].cursor()
        for db_instance in DBInstances:
            DBInstanceIdentifier = db_instance["DBInstanceIdentifier"]
            Endpoint = db_instance["Endpoint"]
            DBInstanceClass = db_instance["DBInstanceClass"]
            Subnets = db_instance["DBSubnetGroup"]["Subnets"]
            VpcSecurityGroups = db_instance["VpcSecurityGroups"]
            Engine = db_instance["Engine"]
            EngineVersion = db_instance["EngineVersion"]
            StorageEncrypted = db_instance["StorageEncrypted"]
            AvailabilityZone = db_instance["AvailabilityZone"]
            DBParameterGroups = db_instance["DBParameterGroups"]
            MultiAZ = db_instance["MultiAZ"]
            endpoint = Endpoint["Address"] + ":" + str(Endpoint["Port"])

            subnet = []
            for x in Subnets:
                subnet.append(
                    x["SubnetIdentifier"] + " : " + x["SubnetAvailabilityZone"]["Name"]
                )

            vpcSG = []
            for x in VpcSecurityGroups:
                vpcSG.append(x["VpcSecurityGroupId"])

            dbParameters = ""
            for x in DBParameterGroups:
                dbParameters += (
                    x["DBParameterGroupName"] + " (" + x["ParameterApplyStatus"] + "), "
                )

            StorageEncrypted = (
                "Storage Encrypted" if StorageEncrypted else "Storage not Encrypted"
            )
            MultiAZ = "MultiAZ Enabled" if MultiAZ else "MultiAZ not Enabled"

            rds_current_insert = "INSERT INTO aws.rds_{} (instance_id, endpoint, instance_class, subnet, security_group, engine, engine_version, storage_encrypted, availability_zone, db_parameter_groups, multi_az, created_on) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT (instance_id) DO UPDATE SET endpoint = excluded.endpoint, instance_class =  excluded.instance_class, subnet = excluded.subnet, security_group = excluded.security_group, engine = excluded.engine, engine_version = excluded.engine_version, storage_encrypted = excluded.storage_encrypted, availability_zone = excluded.availability_zone, db_parameter_groups = excluded.db_parameter_groups, multi_az = excluded.multi_az, deleted = 'f', created_on = now();".format(
                tn
            )
            cursor.execute(
                rds_current_insert,
                (
                    DBInstanceIdentifier,
                    endpoint,
                    DBInstanceClass,
                    json.dumps(subnet),
                    json.dumps(vpcSG),
                    Engine,
                    EngineVersion,
                    StorageEncrypted,
                    AvailabilityZone,
                    dbParameters,
                    MultiAZ,
                ),
            )

            active_instance_ids += (DBInstanceIdentifier,)
        if len(active_instance_ids) > 0:
            deleted_instance_select = (
                "SELECT instance_id FROM aws.rds_{} WHERE instance_id not in (".format(
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
                    "UPDATE aws.rds_{} set deleted = 't' WHERE instance_id = '{}'".format(tn, x[0])
                )
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to insert the RDS Current Records")
    finally:
        if connection:
            cursor.close()
            connection.commit()


def rds_current_merge(only_diff=False, username=""):
    logger.info(
        f"Fetching Current Diff Records for RDS - Only Diff - {only_diff} - Username - {username}"
    )
    rds_diff = diff("rds", True)
    cursor = connections["default"].cursor()
    only_diff_dict = {}
    for instance_id in rds_diff:
        diff_select = "SELECT {cl} FROM aws.rds_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["rds"]),
            pk=column_list["rds"][0],
            value=instance_id[0],
        )
        cursor.execute(diff_select)
        current_instance = cursor.fetchone()

        diff_select = "SELECT {cl} FROM aws.rds_baseline WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["rds"]),
            pk=column_list["rds"][0],
            value=instance_id[0],
        )
        cursor.execute(diff_select)
        baseline_instance = cursor.fetchone()
        name = ""
        flag = False
        if baseline_instance is None:
            name = current_instance[0]
            desc = "New Instance Created"
            flag = True
        elif current_instance is None:
            name = baseline_instance[0]
            desc = "Instance Deleted"
            flag = True
        else:
            name = current_instance[0]
            desc = ""
            for x in range(len(column_list["rds"])):
                if current_instance[x] != baseline_instance[x]:
                    flag = True
                    if x + 1 in array_indexes["rds"]:
                        curr = json.loads(current_instance[x])
                        base = json.loads(baseline_instance[x])
                        # curr = current_instance[x]
                        # base = baseline_instance[x]
                        deleted = list(set(base) - set(curr))
                        added = list(set(curr) - set(base))

                        if len(deleted) > 0:
                            desc += (
                                column_list["rds"][x]
                                + " = "
                                + "Deleted - "
                                + ";".join(deleted)
                                + "<br>"
                            )
                        if len(added) > 0:
                            desc += (
                                column_list["rds"][x]
                                + " = "
                                + "Added - "
                                + ";".join(added)
                                + "<br>"
                            )
                    else:
                        desc += (
                            column_list["rds"][x]
                            + " = "
                            + (baseline_instance[x] if baseline_instance[x] else "None")
                            + " --> "
                            + (current_instance[x] if current_instance[x] else "None")
                            + "<br>"
                        )
        if not flag:
            logger.info("RDS - Flag falsed")
            continue
        if desc == "":
            desc = "No Changes"
            continue
        only_diff_dict[instance_id[0]] = [name, desc]
        if not only_diff:
            logger.info("Inserting the Diff Records for RDS")
            if current_instance is not None:
                rds_current_insert = "INSERT INTO aws.rds_baseline (instance_id, endpoint, instance_class, subnet, security_group, engine, engine_version, storage_encrypted, availability_zone, db_parameter_groups, multi_az, deleted, created_on) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()) ON CONFLICT (instance_id) DO UPDATE SET endpoint = excluded.endpoint, instance_class =  excluded.instance_class, subnet = excluded.subnet, security_group = excluded.security_group, engine = excluded.engine, engine_version = excluded.engine_version, storage_encrypted = excluded.storage_encrypted, availability_zone = excluded.availability_zone, db_parameter_groups = excluded.db_parameter_groups, multi_az = excluded.multi_az, deleted = excluded.deleted, created_on = now();"
                # current_instance = list(current_instance)
                # for x in array_indexes["rds"]:
                #     current_instance[x -
                #                      1] = json.dumps(current_instance[x - 1])
            else:
                rds_current_insert = (
                    "UPDATE aws.rds_baseline set deleted = 't' WHERE instance_id = '{value}'".format(
                        value=instance_id[0]
                    )
                )
            try:
                cursor.execute(rds_current_insert, current_instance)
                audit_log_insert = "INSERT INTO aws.audit_log (service_name,instance_id, log, username) VALUES (%s, %s, %s, %s)"
                cursor.execute(
                    audit_log_insert, ("rds", instance_id[0], desc, username)
                )
            except (Exception, psycopg2.Error) as error:
                send_exection_alert("Failed to insert the RDS Diff Records")
    if connection:
        # cursor.close()
        connection.commit()

    return only_diff_dict


def rds_current():
    logger.info("Fetching the Current Records for RDS")
    rds_current_dict = {}

    try:
        cursor = connections["default"].cursor()
        rds_current_select = "SELECT {cl}, created_on FROM aws.rds_current WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["rds"])
        )
        cursor.execute(rds_current_select)
        rds_current_records = cursor.fetchall()

        for row in rds_current_records:
            rows = list(row)
            del row
            row = rows
            del rows

            key = row[0]
            for x in array_indexes["rds"]:
                row_type = type(row[x - 1])
                # logger.info(f"RDS - row[{x - 1}] - type is {row_type}")
                if row_type == str:
                    # logger.info(f"RDS - row[{x - 1}] - type is str")
                    row[x - 1] = json.loads(row[x - 1])

            rds_current_dict.setdefault(key, [])
            rds_current_dict[key].append("green")
            for x in range(1, len(row) - 1):
                rds_current_dict[key].append(row[x])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the current records for RDS")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return rds_current_dict
