import boto3

from infra.common_baseline import *


def sg_current_insert(tn="current"):
    logger.info(f"Inserting the Current Records for SG - Type - {tn}")
    ec2_client = boto3.client("ec2", region_name=region)
    security_groups = ec2_client.describe_security_groups().get("SecurityGroups")
    active_instance_ids = ()

    try:
        cursor = connections["default"].cursor()
        for security_group in security_groups:
            IpPermissions = security_group["IpPermissions"]
            GroupId = security_group["GroupId"]
            GroupName = ""
            if "Tags" in security_group.keys():
                GroupName = list(
                    filter(lambda x: x["Key"] == "Name", security_group["Tags"])
                )
                if len(GroupName) > 0:
                    GroupName = GroupName[0].get("Value")
            if not GroupName: GroupName = security_group["GroupName"]
            inbound_rules = []
            for x in IpPermissions:
                if "Ipv6Ranges" in x:
                    del x["Ipv6Ranges"]

                if "PrefixListIds" in x:
                    del x["PrefixListIds"]

                if "ToPort" in x:
                    del x["ToPort"]

                if "IpProtocol" in x and x["IpProtocol"] == "-1":
                    x["IpProtocol"] = "all"
                    x["FromPort"] = -1
                inbound_rules.append(x)
            inbound_rules = sorted(inbound_rules, key=lambda k: k["FromPort"])
            sg_current_insert = "INSERT INTO aws.sg_{} (sg_id, sg_name, inbound_rules, created_on) VALUES (%s,%s,%s,now()) ON CONFLICT (sg_id) DO UPDATE SET sg_name = excluded.sg_name, inbound_rules = excluded.inbound_rules, deleted = 'f', created_on = now();".format(
                tn
            )
            record_to_insert = (GroupId, GroupName, json.dumps(inbound_rules))
            cursor.execute(sg_current_insert, record_to_insert)

            active_instance_ids += (GroupId,)
        if len(active_instance_ids) > 0:
            deleted_instance_select = (
                "SELECT sg_id FROM aws.sg_{} WHERE sg_id not in (".format(tn)
            )
            for x in active_instance_ids:
                deleted_instance_select += "'{}',".format(x)
            deleted_instance_select = deleted_instance_select[0:-1]
            deleted_instance_select += ");"
            cursor.execute(deleted_instance_select)
            deleted_instance = cursor.fetchall()
            for x in deleted_instance:
                cursor.execute(
                    "UPDATE aws.sg_{} set deleted = 't' WHERE sg_id = '{}'".format(tn, x[0])
                )
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to insert the SG Current Records")
    finally:
        if connection:
            cursor.close()
            connection.commit()


def sg_current_merge(only_diff=False, username=""):
    logger.info(
        f"Fetching Current Diff Records for SG - Only Diff - {only_diff} - Username - {username}"
    )
    sg_diff = diff("sg", True)
    cursor = connections["default"].cursor()
    only_diff_dict = {}
    for instance_id in sg_diff:
        diff_select = "SELECT {cl} FROM aws.sg_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["sg"]),
            pk=column_list["sg"][0],
            value=instance_id[0],
        )
        cursor.execute(diff_select)
        current_instance = cursor.fetchone()
        diff_select = "SELECT {cl} FROM aws.sg_baseline WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["sg"]),
            pk=column_list["sg"][0],
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
            for x in range(len(column_list["sg"])):
                if current_instance[x] != baseline_instance[x]:
                    flag = True
                    if x + 1 in array_indexes["sg"]:
                        key = "FromPort"
                        curr = json.loads(current_instance[x])
                        base = json.loads(baseline_instance[x])
                        # curr = current_instance[x]
                        # base = baseline_instance[x]
                        curr_dict = {y[key]: y for y in curr if key in y}
                        base_dict = {y[key]: y for y in base if key in y}

                        deleted = list(
                            map(str, set(base_dict.keys()) - set(curr_dict.keys()))
                        )
                        added = list(
                            map(str, set(curr_dict.keys()) - set(base_dict.keys()))
                        )
                        common_instances = list(
                            set(curr_dict.keys()).intersection(base_dict.keys())
                        )

                        if len(deleted) > 0:
                            desc += (
                                column_list["sg"][x]
                                + " = "
                                + "Deleted "
                                + key
                                + " - "
                                + ", ".join(deleted)
                                + "<br>"
                            )
                        if len(added) > 0:
                            desc += (
                                column_list["sg"][x]
                                + " = "
                                + "Added "
                                + key
                                + " - "
                                + ", ".join(added)
                                + "<br>"
                            )
                        for common_port in common_instances:
                            if curr_dict[common_port] != base_dict[common_port]:
                                for main_key, key_1 in (
                                    ("IpRanges", "CidrIp"),
                                    ("UserIdGroupPairs", "GroupId"),
                                ):
                                    if (
                                        base_dict[common_port][main_key]
                                        != curr_dict[common_port][main_key]
                                    ):
                                        curr_cidr = {
                                            y[key_1]: y
                                            for y in curr_dict[common_port][main_key]
                                            if key_1 in y
                                        }
                                        base_cidr = {
                                            y[key_1]: y
                                            for y in base_dict[common_port][main_key]
                                            if key_1 in y
                                        }
                                        deleted = list(
                                            set(base_cidr.keys())
                                            - set(curr_cidr.keys())
                                        )
                                        added = list(
                                            set(curr_cidr.keys())
                                            - set(base_cidr.keys())
                                        )
                                        common = list(
                                            set(curr_cidr.keys()).intersection(
                                                base_cidr.keys()
                                            )
                                        )

                                        if len(deleted) > 0:
                                            desc += (
                                                column_list["sg"][x]
                                                + " = Port : "
                                                + str(curr_dict[common_port][key])
                                                + " - "
                                                + "Deleted "
                                                + key_1
                                                + " : "
                                                + ", ".join(deleted)
                                                + "<br>"
                                            )
                                        if len(added) > 0:
                                            desc += (
                                                column_list["sg"][x]
                                                + " = Port : "
                                                + str(curr_dict[common_port][key])
                                                + " - "
                                                + "Added "
                                                + key_1
                                                + " : "
                                                + ", ".join(added)
                                                + "<br>"
                                            )

                                        for common_cidr in common:
                                            if (
                                                curr_cidr[common_cidr]
                                                != base_cidr[common_cidr]
                                            ):
                                                curr_ip = curr_cidr[common_cidr]
                                                base_ip = base_cidr[common_cidr]
                                                key_2 = "Description"
                                                if key_2 not in base_ip:
                                                    if key_2 not in curr_ip:
                                                        break
                                                    else:
                                                        desc += (
                                                            column_list["sg"][x]
                                                            + " = Port : "
                                                            + str(
                                                                curr_dict[common_port][
                                                                    key
                                                                ]
                                                            )
                                                            + " - "
                                                            + key_1
                                                            + " : "
                                                            + curr_ip[key_1]
                                                            + " - Description added : "
                                                            + curr_ip[key_2]
                                                            + "<br>"
                                                        )
                                                elif key_2 not in curr_ip:
                                                    desc += (
                                                        column_list["sg"][x]
                                                        + " = Port : "
                                                        + str(
                                                            curr_dict[common_port][key]
                                                        )
                                                        + " - "
                                                        + key_1
                                                        + " : "
                                                        + curr_ip[key_1]
                                                        + " - Description deleted : "
                                                        + base_ip[key_2]
                                                        + "<br>"
                                                    )
                                                elif curr_ip[key_2] != base_ip[key_2]:
                                                    desc += (
                                                        column_list["sg"][x]
                                                        + " = Port : "
                                                        + str(
                                                            curr_dict[common_port][key]
                                                        )
                                                        + " - "
                                                        + key_1
                                                        + " : "
                                                        + curr_ip[key_1]
                                                        + " - Description changed to : "
                                                        + curr_ip[key_2]
                                                        + "<br>"
                                                    )
                    else:
                        desc += (
                            column_list["sg"][x]
                            + " = "
                            + (baseline_instance[x] if baseline_instance[x] else "None")
                            + " --> "
                            + (current_instance[x] if current_instance[x] else "None")
                            + "<br>"
                        )
        if not flag:
            logger.info("SG - Flag falsed")
            continue
        if desc == "":
            desc = "No Changes"
            continue
        only_diff_dict[instance_id[0]] = [name, desc]

        if not only_diff:
            logger.info("Inserting the Diff Records for SG")
            if current_instance is not None:
                # sort the inbound rules in current_instance
                current_instance=list(current_instance)
                inbound_rules = json.loads(current_instance[2])
                inbound_rules = sorted(inbound_rules, key=lambda k: k["FromPort"])
                current_instance[2] = json.dumps(inbound_rules)
                logger.info("Inserting the base SG Record")
                sg_current_insert = "INSERT INTO aws.sg_baseline (sg_id, sg_name, inbound_rules, deleted, created_on) VALUES (%s,%s,%s,%s,now()) ON CONFLICT (sg_id) DO UPDATE SET sg_name = excluded.sg_name, inbound_rules = excluded.inbound_rules, deleted = excluded.deleted, created_on = now();"
                # current_instance = list(current_instance)
                # for x in array_indexes["sg"]:
                #     current_instance[x -
                #                      1] = json.dumps(current_instance[x - 1])
            else:
                sg_current_insert = (
                    "UPDATE aws.sg_baseline set deleted = 't' WHERE sg_id = '{value}'".format(
                        value=instance_id[0]
                    )
                )
            try:
                cursor.execute(sg_current_insert, current_instance)
                audit_log_insert = "INSERT INTO aws.audit_log (service_name,instance_id, log, username) VALUES (%s, %s, %s, %s)"
                cursor.execute(audit_log_insert, ("sg", instance_id[0], desc, username))
            except (Exception, psycopg2.Error) as error:
                send_exection_alert("Failed to insert SG baseline")

    if connection:
        # cursor.close()
        connection.commit()

    return only_diff_dict


def sg_current():
    logger.info("Fetching the Current Records for Security Group")
    sg_current_dict = {}

    try:
        cursor = connections["default"].cursor()
        sg_current_select = "SELECT {cl}, created_on FROM aws.sg_current WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["sg"])
        )
        cursor.execute(sg_current_select)
        sg_current_record = cursor.fetchall()

        for row in sg_current_record:
            rows = list(row)
            del row
            row = rows
            del rows

            key = row[0]
            for x in array_indexes["sg"]:
                row_type = type(row[x - 1])
                # logger.info(f"SG - row[{x - 1}] - type is {row_type}")
                if row_type == str:
                    # logger.info(f"SG - row[{x - 1}] - type is str")
                    row[x - 1] = json.loads(row[x - 1])

            sg_current_dict.setdefault(key, [])
            sg_current_dict[key].append("green")
            for x in range(1, len(row) - 1):
                sg_current_dict[key].append(row[x])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch SG current")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return sg_current_dict
