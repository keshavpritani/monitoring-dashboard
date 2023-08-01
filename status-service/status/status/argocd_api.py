import requests, json
from pprint import pprint

def get_argocd_outofsync_unhealthy():
    ARGOCD_SERVER = "https://staging-argocd.kristal.ai"
    ARGOCD_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIzNzE4ZTk2Zi1jNWM1LTQ0YzctYmJkMy04OWUwYWJlYzRiZjYiLCJpYXQiOjE2NzAzNTI5ODgsImlzcyI6ImFyZ29jZCIsIm5iZiI6MTY3MDM1Mjk4OCwic3ViIjoia2VzaGF2OmFwaUtleSJ9.mk3AFC3_w-dLIXTig3nkaCos-Zst_MzbpOksP1YbQg4"
    
    headers = {
        "Authorization": f"Bearer {ARGOCD_TOKEN}",
    }

    data = requests.get(f"{ARGOCD_SERVER}/api/v1/applications", headers=headers)
    json_data = json.loads(data.text)["items"]
    outofsync_unhealthy_resources = {}
    for i in json_data:
        status = i["status"]
        if status["sync"]["status"] != "Synced" or status["health"]["status"] != "Healthy":
            for j in list(filter(lambda resources: resources['status'] != 'Synced' or resources['health']['status'] != 'Healthy', status["resources"])):
                text = ""
                if j['status'] != "Synced": text = j['status']
                if j['status'] != "Synced" and j['health']['status'] != "Healthy": text += " and "
                if j['health']['status'] != "Healthy": text = f"{j['health']['status']} - {j['health']['message']}"
                outofsync_unhealthy_resources[j['name']] = text
    
    if outofsync_unhealthy_resources: pprint(outofsync_unhealthy_resources)


if __name__ == "__main__":
    get_argocd_outofsync_unhealthy()