import boto3

from infra.common_baseline import *


def subnet_current_insert(tn="current"):
    logger.info(f"Inserting the Current Records for Subnet - Type - {tn}")
    ec2_client = boto3.client("ec2", region_name=region)
    subnets = ec2_client.describe_subnets().get("Subnets")
    active_instance_ids = ()

    try:
        cursor = connections["default"].cursor()
        for subnet in subnets:
            SubnetId = subnet["SubnetId"]
            AvailabilityZone = subnet["AvailabilityZone"]
            CidrBlock = subnet["CidrBlock"]
            MapPublicIpOnLaunch = subnet["MapPublicIpOnLaunch"]
            SubnetName = ""
            if "Tags" in subnet.keys():
                SubnetName = list(filter(lambda x: x["Key"] == "Name", subnet["Tags"]))[
                    0
                ].get("Value")

            subnet_current_insert = "INSERT INTO aws.subnet_{} (subnet_id, availability_zone, cidr_block, subnet_name, public_ip, created_on) VALUES (%s,%s,%s,%s,%s,now()) ON CONFLICT (subnet_id) DO UPDATE SET availability_zone = excluded.availability_zone, cidr_block = excluded.cidr_block, subnet_name = excluded.subnet_name, public_ip = excluded.public_ip, deleted = 'f', created_on = now();".format(
                tn
            )
            record_to_insert = (SubnetId, AvailabilityZone, CidrBlock, SubnetName, MapPublicIpOnLaunch)
            cursor.execute(subnet_current_insert, record_to_insert)

            active_instance_ids += (SubnetId,)
        if len(active_instance_ids) > 0:
            deleted_instance_select = (
                "SELECT subnet_id FROM aws.subnet_{} WHERE subnet_id not in (".format(
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
                    "UPDATE aws.subnet_{} set deleted = 't' WHERE subnet_id = '{}'".format(tn, x[0])
                )
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to insert the Subnet Current Records")
    finally:
        if connection:
            cursor.close()
            connection.commit()


def subnet_current_merge(only_diff=False, username=""):
    logger.info(
        f"Fetching Current Diff Records for Subnet - Only Diff - {only_diff} - Username - {username}"
    )
    subnet_diff = diff("subnet", True)
    cursor = connections["default"].cursor()
    only_diff_dict = {}
    for instance_id in subnet_diff:
        diff_select = "SELECT {cl} FROM aws.subnet_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on;".format(
            cl=",".join(column_list["subnet"]),
            pk=column_list["subnet"][0],
            value=instance_id[0],
        )
        cursor.execute(diff_select)
        current_instance = cursor.fetchone()

        diff_select = "SELECT {cl} FROM aws.subnet_baseline WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on;".format(
            cl=",".join(column_list["subnet"]),
            pk=column_list["subnet"][0],
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
            for x in range(len(column_list["subnet"])):
                if current_instance[x] != baseline_instance[x]:
                    flag = True
                    desc += (
                        column_list["subnet"][x]
                        + " = "
                        + (baseline_instance[x] if baseline_instance[x] else "None")
                        + " --> "
                        + (current_instance[x] if current_instance[x] else "None")
                        + "<br>"
                    )
        if not flag:
            logger.info("Subnet - Flag falsed")
            continue
        if desc == "":
            desc = "No Changes"
            continue
        only_diff_dict[instance_id[0]] = [name, desc]
        if not only_diff:
            logger.info("Inserting the Diff Records for Subnet")
            if current_instance is not None:
                subnet_current_insert = "INSERT INTO aws.subnet_baseline (subnet_id,subnet_name, cidr_block, public_ip, availability_zone, deleted, created_on) VALUES (%s,%s,%s,%s,%s,%s,now()) ON CONFLICT (subnet_id) DO UPDATE SET availability_zone = excluded.availability_zone, cidr_block = excluded.cidr_block, subnet_name = excluded.subnet_name, public_ip = excluded.public_ip, deleted = excluded.deleted, created_on = now();"
            else:
                subnet_current_insert = "UPDATE aws.subnet_baseline set deleted = 't' WHERE subnet_id = '{value}'".format(
                    value=instance_id[0]
                )
            try:
                cursor.execute(subnet_current_insert, current_instance)
                audit_log_insert = "INSERT INTO aws.audit_log (service_name,instance_id, log, username) VALUES (%s, %s, %s, %s)"
                cursor.execute(
                    audit_log_insert, ("subnet", instance_id[0], desc, username)
                )
            except (Exception, psycopg2.Error) as error:
                send_exection_alert("Failed to insert the Subnet Diff Records")
    if connection:
        # cursor.close()
        connection.commit()

    return only_diff_dict


def subnet_current():
    logger.info("Fetching the Current Records for Subnet")
    subnet_current_dict = {}

    try:
        cursor = connections["default"].cursor()
        subnet_current_select = "SELECT {cl}, created_on FROM aws.subnet_current WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["subnet"])
        )
        cursor.execute(subnet_current_select)
        subnet_current_record = cursor.fetchall()

        for row in subnet_current_record:
            key = row[0]
            subnet_current_dict.setdefault(key, [])
            subnet_current_dict[key].append("green")
            for x in range(1, len(row) - 1):
                subnet_current_dict[key].append(row[x])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the Subnet Current Records")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return subnet_current_dict
