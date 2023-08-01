import requests
import json
from status.essentials import *

flag = dict()
red_flag = dict()


def saxo_tokens_func():
    saxo_tokens_update = {}
    try:
        global flag, last_alert_time
        url = get_property("SAXO_TOKEN_URL")
        logger.info(f"Checking Saxo Tokens - {url} - {flag} - {red_flag}")
        data_str = requests.get(url, timeout=10)
        if(data_str.status_code != 200):
            if (ENV != "dev"): send_exection_alert(f"Error while checking Saxo Tokens - status code - {data_str.status_code}")
            return
        saxo_tokens = {}
        data_str = data_str.text
        # flag.setdefault("null",False)
        # if data_str == "":
        #     if not flag["null"]:
        #         flag["null"] = True
        #         logger.info(f"Saxo Tokens, Empty response from Saxo Tokens")
        #     elif ENV == 'prod':
        #         send_alert("Saxo tokens are not available","Red","saxo")
        #     return
        # else:
        #     flag["null"] = False
        data_str = data_str.split()
        for i in data_str:
            a, b = i.split(':')
            saxo_tokens[a] = b

        saxo_tokens_list = set(sorted(json.loads(get_property("SAXO_TOKENS_LIST"))))
        current_saxo_tokens_list = set(sorted(saxo_tokens.keys()))

        not_found = saxo_tokens_list - current_saxo_tokens_list
        for i in not_found:
            saxo_tokens[i] = 0

        for i in saxo_tokens:
            flag.setdefault(i, False)
            red_flag.setdefault(i, False)
            if int(saxo_tokens[i]) == 5:
                key = i
                saxo_tokens_update.setdefault(key, [])
                saxo_tokens_update[key].append('Green')
                saxo_tokens_update[key].append(saxo_tokens[i])
                flag[i] = False
                red_flag[i] = False
                if f"Saxo-Token-{key}" in last_alert_time: del last_alert_time[f"Saxo-Token-{key}"]
            elif 3 <= int(saxo_tokens[i]) <= 4:
                key = i
                saxo_tokens_update.setdefault(key, [])
                saxo_tokens_update[key].append('Yellow')
                saxo_tokens_update[key].append(saxo_tokens[i])
                if flag[i]:
                    saxo_slack(key, 'Yellow', saxo_tokens[i])
                flag[i] = True
                red_flag[i] = False

            else:
                key = i
                saxo_tokens_update.setdefault(key, [])
                saxo_tokens_update[key].append('Red')
                saxo_tokens_update[key].append(saxo_tokens[i])
                if red_flag[i]:
                    groups=[]
                    only_groups=["trade_ops"]
                    if ENV == 'prod' and ( 
                        f"Saxo-Token-{key}" not in last_alert_time
                        or last_alert_time[f"Saxo-Token-{key}"][0] + timedelta(minutes=30) < datetime.now()
                    ):
                        groups = only_groups
                        only_groups = []
                        last_alert_time[f"Saxo-Token-{key}"] = [datetime.now(), True]
                    saxo_slack(key, 'Red', saxo_tokens[i],groups=groups,only_groups=only_groups)
                red_flag[i] = True
    except Exception as e:
        send_exection_alert("Error while checking saxo tokens")

    return saxo_tokens_update


def saxo_slack(key, status, saxo_token,groups=[],only_groups=["trade_ops"]):
    extra_message = 'Saxo token has expired for : {}\nCurrent Value : {}'.format(key, saxo_token)
    send_alert(f"Saxo-Token-{key}",status,"saxo",f"\n{extra_message}",groups=groups,only_groups=only_groups)
