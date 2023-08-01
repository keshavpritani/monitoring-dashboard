import boto3
from django.http import HttpResponse

from infra.common_baseline import *

ec2_client = boto3.client("ec2", region_name=region)


def route_current_insert(tn="current"):
    logger.info(f"Inserting the Current Records for Route Table - Type - {tn}")
    response = ec2_client.describe_route_tables()['RouteTables']
    active_route_ids = ()
    try:
        cursor = connections["default"].cursor()
        for route_table in response:
            id = route_table['RouteTableId']
            name = ""
            if "Tags" in route_table.keys():
                tags = list(filter(lambda x: x["Key"] == "Name", route_table["Tags"]))
                if tags:
                    name = tags[0]["Value"]
            routes=[]
            for route in route_table['Routes']:
                destination = ""
                for i in ("DestinationCidrBlock", "DestinationPrefixListId", "DestinationIpv6CidrBlock"):
                    if i in route.keys():
                        destination = route[i]
                        del route[i]

                state = route['State']
                del route['State']
                del route['Origin']

                desc = ""

                for key, value in route.items():
                    desc = f"{key} - {value}"

                routes.append({"destination": destination, "state": state, "desc": desc})

            subnet_ids = []
            for association in route_table['Associations']:
                if "SubnetId" in association.keys():
                    subnet_ids.append(association['SubnetId'])

            route_current_insert = "INSERT INTO aws.route_{} (route_id, route_name, routes, subnet_ids, created_on) VALUES (%s,%s,%s,%s,now()) ON CONFLICT (route_id) DO UPDATE SET route_name = excluded.route_name, routes = excluded.routes, subnet_ids = excluded.subnet_ids, deleted = 'f', created_on = now();".format(
                tn
            )
            cursor.execute(
                route_current_insert,
                (
                    id,
                    name,
                    json.dumps(routes),
                    json.dumps(subnet_ids),
                ),
            )

            active_route_ids += (id,)
        if len(active_route_ids) > 0:
            deleted_instance_select = (
                "SELECT route_id FROM aws.route_{} WHERE route_id not in (".format(
                    tn
                )
            )
            for x in active_route_ids:
                deleted_instance_select += "'{}',".format(x)
            deleted_instance_select = deleted_instance_select[0:-1]
            deleted_instance_select += ");"
            cursor.execute(deleted_instance_select)
            deleted_instance = cursor.fetchall()
            for x in deleted_instance:
                cursor.execute(
                    "UPDATE aws.route_{} set deleted = 't' WHERE route_id = '{}'".format(tn, x[0])
                )
    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to insert the Route Table Current Records")
    finally:
        if connection:
            cursor.close()
            connection.commit()


def route_current_merge(only_diff=False, username=""):
    logger.info(
        f"Fetching Current Diff Records for Route Table - Only Diff - {only_diff} - Username - {username}"
    )
    route_diff = diff("route", True)
    cursor = connections["default"].cursor()
    only_diff_dict = {}
    for route_id in route_diff:
        diff_select = "SELECT {cl} FROM aws.route_current WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["route"]),
            pk=column_list["route"][0],
            value=route_id[0],
        )

        cursor.execute(diff_select)
        current_instance = cursor.fetchone()

        diff_select = "SELECT {cl} FROM aws.route_baseline WHERE {pk} = '{value}' AND NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["route"]),
            pk=column_list["route"][0],
            value=route_id[0],
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
            for x in range(len(column_list["route"])):
                if current_instance[x] != baseline_instance[x]:
                    flag = True
                    if x + 1 in array_indexes["route"]:
                        curr = json.loads(current_instance[x])
                        base = json.loads(baseline_instance[x])
                        # curr = current_instance[x]
                        # base = baseline_instance[x]
                        
                        deleted = []
                        added = []
                        common_instances = []
                        curr_dict = {}
                        base_dict= {}

                        if column_list["route"][x] == "routes":
                            key = "destination"
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
                        else:
                            deleted = list(set(base) - set(curr))
                            added = list(set(curr) - set(base))

                        if len(deleted) > 0:
                            desc += (
                                column_list["route"][x]
                                + " = "
                                + "Deleted - "
                                + ";".join(deleted)
                                + "<br>"
                            )
                        if len(added) > 0:
                            desc += (
                                column_list["route"][x]
                                + " = "
                                + "Added - "
                                + ";".join(added)
                                + "<br>"
                            )
                        for common_dest in common_instances:
                            if curr_dict[common_dest] != base_dict[common_dest]:
                                for key in ("desc", "state"):
                                    if (base_dict[common_dest][key] != curr_dict[common_dest][key]):
                                        desc += (
                                            column_list["route"][x]
                                            + " = "
                                            + base_dict[common_dest][key] if base_dict[common_dest][key] else "None"
                                            + " --> "
                                            + curr_dict[common_dest][key] if curr_dict[common_dest][key] else "None"
                                            + "<br>"
                                        )
                    else:
                        desc += (
                            column_list["route"][x]
                            + " = "
                            + (baseline_instance[x] if baseline_instance[x] else "None")
                            + " --> "
                            + (current_instance[x] if current_instance[x] else "None")
                            + "<br>"
                        )
        if not flag:
            logger.info("Route Table - Flag falsed")
            continue
        if desc == "":
            desc = "No Changes"
            continue
        only_diff_dict[route_id[0]] = [name, desc]

        if not only_diff:
            logger.info("Inserting the Diff Records for Route Table")
            if current_instance is not None:
                route_current_insert = "INSERT INTO aws.route_baseline (route_id, route_name, routes, subnet_ids, deleted, created_on) VALUES (%s,%s,%s,%s,%s,now()) ON CONFLICT (route_id) DO UPDATE SET route_name = excluded.route_name, routes = excluded.routes, subnet_ids = excluded.subnet_ids, deleted = excluded.deleted, created_on = now();"
                # current_instance = list(current_instance)
                # for x in array_indexes["route"]:
                #     current_instance[x -
                #                      1] = json.dumps(current_instance[x - 1])
            else:
                route_current_insert = (
                    "UPDATE aws.route_baseline set deleted = 't' WHERE route_id = '{value}'".format(
                        value=route_id[0]
                    )
                )

            try:
                cursor.execute(route_current_insert, current_instance)
                audit_log_insert = "INSERT INTO aws.audit_log (service_name, instance_id, log, username) VALUES (%s, %s, %s, %s)"
                cursor.execute(
                    audit_log_insert, ("route", route_id[0], desc, username)
                )
            except (Exception, psycopg2.Error) as error:
                send_exection_alert("Failed to insert the Route Table Diff Records")
    if connection:
        # cursor.close()
        connection.commit()

    return only_diff_dict


def route_current():
    logger.info("Fetching the Current Records for Route Table")

    route_current_dict = {}

    try:
        cursor = connections["default"].cursor()
        route_current_select = "SELECT {cl}, created_on FROM aws.route_current WHERE NOT deleted ORDER BY created_on DESC;".format(
            cl=",".join(column_list["route"])
        )
        cursor.execute(route_current_select)
        route_current_records = cursor.fetchall()

        for row in route_current_records:
            rows = list(row)
            del row
            row = rows
            del rows

            for x in array_indexes["route"]:
                row_type = type(row[x - 1])
                # logger.info(f"route - row[{x - 1}] - type is {row_type}")
                if row_type == str:
                    # logger.info(f"route - row[{x - 1}] - type is str")
                    row[x - 1] = json.loads(row[x - 1])

            key = row[0]
            route_current_dict.setdefault(key, [])
            route_current_dict[key].append("green")
            for x in range(1, len(row) - 1):
                route_current_dict[key].append(row[x])

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Failed to fetch the Route Table Current Records")

    finally:
        if connection:
            cursor.close()
            connection.close()

    return route_current_dict
