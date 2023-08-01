import psycopg2
from django.db import connection
from datetime import datetime
from status.essentials import *
import boto3
from django.http import JsonResponse

docker_images_time = {}
last_refresh_ecr = ""
region = properties['AWS_REGION']

def db_docker_images_status():
    global docker_images_time
    tags = []
    logger.info("Checking Docker Images Status")
    try:
        cursor = connection.cursor()
        postgreSQL_select_Query = "select DISTINCT tag from docker_images_status;"
        cursor.execute(postgreSQL_select_Query)
        tags_temp = cursor.fetchall()
        for i in tags_temp:
            tags.append(i[0])

        postgreSQL_select_Query = "select image_name, tag, last_updated from docker_images_status order by last_updated desc;"
        cursor.execute(postgreSQL_select_Query)
        docker_status = cursor.fetchall()
        for docker in docker_status:
            image_name = docker[0]
            tag = docker[1]
            date = docker[2]
            delta = datetime.now() - date
            delta = str(delta).split('.')[0]
            docker_images_time.setdefault(image_name, {})
            docker_images_time[image_name][tag] = delta

    except (Exception, psycopg2.Error) as error:
        send_exection_alert("Error while fetching data from docker_images_status")

    finally:
        # closing database connection.
        if connection:
            connection.close()

    return docker_images_time, tags

def ecr_docker_images_status(request):
    global docker_images_time, last_refresh_ecr, region
    logger.info("Checking Docker Images Status")
    image_tag = get_property('DOCKER_IMAGE_TAG')
    client = boto3.client('ecr', region_name=region)
    repos = client.describe_repositories().get('repositories')
    repos_time = {}
    for repo in repos:
        repo_name = repo['repositoryName']
        if "base" in repo_name or "confluent" in repo_name or "nginx" in repo_name:
            continue
        try:
            response = client.describe_images(repositoryName=repo_name,imageIds=[{'imageTag': image_tag}])['imageDetails']
            image_pushed = response[0]['imagePushedAt']
            image_pushed = image_pushed.replace(tzinfo=None)
            delta = datetime.now() - image_pushed
            repos_time[repo_name] = delta.total_seconds()
        except Exception as e:
            # logger.error(f"Error while fetching data from ECR for - {repo_name}: {e}")
            continue
    docker_images_time = sorted(repos_time.items(), key=lambda x: x[1])
    last_refresh_ecr = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return JsonResponse({"status": "success"})

@csrf_exempt
def validate_deployed_images(request):
    logger.info("Checking Docker Images Deploy Validation")
    data = json.loads(request.body)

    if "stack" not in data or "docker_tag" not in data: return JsonResponse({"status": "failed", "msg": "stack and docker_tag keys are required"}, status=422)
    stack = str(data["stack"]).strip()
    docker_tag = str(data['docker_tag']).strip()
    # docker_tag = f"{ENV}-{data['docker_tag']}"
    app_name = str(data["app_name"]).strip() if "app_name" in data and str(data["app_name"]).strip() else ".*"
    tier = data["tier"].split(",") if "tier" in data else []

    extra_query = ".*"
    for type in tier:
        type = str(type).strip()
        if type: extra_query += f'{type}-{stack}-.*|'

    alert_key = stack
    if app_name != ".*": alert_key += f" - App - {app_name}"

    logger.info(f"Checking Docker image details for Stack - {alert_key} - {tier} - {docker_tag}")

    prometheus_url = get_property('PROMETHEUS_URL')
    # IGNORE_DOCKER_LIST = json.loads(get_property("IGNORE_DOCKER_LIST"))

    query = 'kube_pod_container_info{namespace="dev-apps", container=~"' + app_name + '", image=~".+/' + stack + '/.+:.+", pod=~"' + extra_query + '"}'
    print(query)
    query = requests.utils.quote(query)
    response = requests.get(f"{prometheus_url}/api/v1/query?query={query}")
    if response.status_code != 200: 
        send_exection_alert(f"Docker Validation Prometheus Query Error: {response.status_code}")
        return JsonResponse({"status": "failed", "msg": "Something went wrong"},status=500)
    data = json.loads(response.text)["data"]["result"]
    failed_for = {}
    for i in data:
        kube_docker_tag = str(i['metric']['image']).split(":")[1]
        kube_app_name = str(i['metric']['container'])
        if (kube_docker_tag != docker_tag): failed_for.setdefault(kube_app_name,[]).append(kube_docker_tag)

    if data:
        extra_message = f", This container is not properly deployed (Running on Older Image), Checking for `{docker_tag}` but found"
        for key, values in failed_for.items(): extra_message += f"\n{key} = {', '.join(values)}"
    else:
        failed_for[alert_key] = True
        extra_message = ", This Stack/App is not deployed"

    logger.info("Docker Images Deploy Validation Completed")

    if data and not failed_for.keys(): return JsonResponse({"status": "success"})
    else:
        send_alert(f"Deploy Validation - Stack - {alert_key}", "Yellow", "deploy_validation", extra_message)
        return JsonResponse({"status": "failed", "msg": f"Validation Failed for {', '.join(failed_for.keys())}"}, status=400)

@csrf_exempt
def validate_deployed_images_old(request):
    global region
    if ENV == "dev": return
    logger.info("Checking Docker Images SHA Validation")
    client = boto3.client('ecr', region_name=region)
    data = json.loads(request.body)
    stacks = []
    stacks_str = ".+"
    if "stacks" in data and data["stacks"] != "":
        stacks = str(data["stacks"])
        stacks = stacks.split(",")
        stacks_str = "|".join(stacks)
    image_tag = get_property('DOCKER_IMAGE_TAG')
    prometheus_url = get_property('PROMETHEUS_URL')
    IGNORE_DOCKER_LIST = json.loads(get_property("IGNORE_DOCKER_LIST"))
    query = 'container_start_time_seconds{container_label_com_docker_stack_namespace=~"' + stacks_str + '",container_label_com_docker_stack_namespace!~"swarmpit"}'
    query = requests.utils.quote(query)
    response = requests.get(f"{prometheus_url}/api/v1/query?query={query}")
    if response.status_code != 200: 
        send_exection_alert(f"Error: {response.status_code}")
        return JsonResponse({"status": "failed", "msg": "Something went wrong"},status=500)
    flag = True
    data = json.loads(response.text)["data"]["result"]
    stacks_found = set()
    for i in data:
        stacks_found.add(str(i['metric']['container_label_com_docker_stack_namespace']))
        image_with_tag_with_sha = str(i['metric']['image']).split("@")
        sha = "".join(image_with_tag_with_sha[1:])
        image = image_with_tag_with_sha[0].split(f":{image_tag}")[0]
        repo_name = "/".join(image.split("/")[1:])
        if any(sub in repo_name for sub in IGNORE_DOCKER_LIST): continue
        if "base" in repo_name or "confluent" in repo_name or "nginx" in repo_name:
            continue
        try:
            response = client.describe_images(repositoryName=repo_name,imageIds=[{'imageTag': image_tag}])['imageDetails']
            ecr_sha = response[0]['imageDigest']
            if sha != ecr_sha:
                extra_message = ", This container is not properly deployed (Running on Older Image (Image SHA not matching with ECR))"
                send_alert(f"ECR - {repo_name}", "Red", "docker_sha", extra_message)
                flag = False
        except Exception as e:
            send_exection_alert(f"Error while fetching data from ECR for - {repo_name}: {e}")
            flag = False
            continue

    stacks_not_found = set(stacks) - stacks_found
    for stack in stacks_not_found:
        extra_message = ", This Stack is not deployed(Didn't find details from CAdvisor)"
        send_alert(f"Docker_Stack - {stack}", "Red", "docker_sha", extra_message)
        flag = False
    logger.info("Docker Images SHA Validation Completed")

    if flag: return JsonResponse({"status": "success"})
    else: return JsonResponse({"status": "failed", "msg": "Something went wrong"},status=500)

def docker_full_status(request):
    global docker_images_time, last_refresh_ecr, region
    logger.info("Checking Docker Images Status")
    image_tag=get_property('DOCKER_IMAGE_TAG')
    client = boto3.client('ecr', region_name=region)
    ecr_repos = client.describe_repositories().get('repositories')

    repos = {}
    for repo in ecr_repos:
        repo_name = repo['repositoryName']
        if "base" in repo_name or "confluent" in repo_name or "nginx" in repo_name:
            continue
        try:
            response = client.describe_images(repositoryName=repo_name,imageIds=[{'imageTag': image_tag}])['imageDetails']
            image_pushed = response[0]['imagePushedAt']
            image_pushed = image_pushed.replace(tzinfo=None)
            delta = datetime.now() - image_pushed
            sha = response[0]['imageDigest']
            repos[repo_name] = {"image_pushed": delta.total_seconds(), "sha": sha, "status": "Not Deployed"}
        except Exception as e:
            continue

    swarmpit = json.loads(get_property('SWARMPIT_DATA'))

    for i in swarmpit:
        url = i['url']
        token = i['token']
        headers = {
            'Authorization': 'Bearer ' + token,
        }
        response = requests.get(f"{url}/api/services", headers=headers).json()
        logger.info(f"Checking for {url}")
        for service in response:
            repo_name = service['repository']['name']
            try:
                flag = True
                for name in ("swarmpit", "influxdb", "couchdb", "nginx"): 
                    if name in repo_name:
                        flag = False
                        break
                if not flag: continue
                repo_name = repo_name.split("amazonaws.com/")[1]

                temp = service['updatedAt']
                temp = temp.split(".")[0]
                last_updated_date = datetime.strptime(temp, '%Y-%m-%dT%H:%M:%S')
                delta = datetime.now() - last_updated_date
                repos.setdefault(repo_name, {})
                if "sha" in repos[repo_name] and repos[repo_name]['sha'] == service['repository']['imageDigest']: repos[repo_name]['status'] = "Same"
                else: repos[repo_name]['status'] = "Not Same"
                repos[repo_name]['last_updated'] = delta.total_seconds()
            except Exception as e:
                print(repo_name, e)

    docker_images_time = repos
    last_refresh_ecr = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    return JsonResponse({"status": "success", "data": docker_images_time})
