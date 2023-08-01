import requests
from status.essentials import *


def refresh_func():
    try:
        flex_validation_dict = {}
        url_ibflex = get_property("IB_FLEX_URL")
        logger.info(f"Checking Flex Validation - {url_ibflex}")
        status_ibflex = requests.get(url_ibflex, timeout=10).text
        url_saxoreport = get_property("SAXO_REPORT_URL")
        logger.info(f"Checking Saxo Report - {url_saxoreport}")
        status_saxoreport = requests.get(url_saxoreport, timeout=10).text
        if int(status_ibflex) == 0:
            key = 'ibflex'
            flex_validation_dict.setdefault(key, [])
            flex_validation_dict[key].append('Green')
            flex_validation_dict[key].append(status_ibflex)

        elif int(status_ibflex) == 1:
            key = 'ibflex'
            flex_validation_dict.setdefault(key, [])
            flex_validation_dict[key].append('Yellow')
            flex_validation_dict[key].append(status_ibflex)

        else:
            key = 'ibflex'
            flex_validation_dict.setdefault(key, [])
            flex_validation_dict[key].append('Red')
            flex_validation_dict[key].append(status_ibflex)
            send_alert(key, 'Red', "flex")

        if int(status_saxoreport) == 0:
            key = 'saxoreport'
            flex_validation_dict.setdefault(key, [])
            flex_validation_dict[key].append('Green')
            flex_validation_dict[key].append(status_saxoreport)

        elif int(status_saxoreport) == 1:
            key = 'saxoreport'
            flex_validation_dict.setdefault(key, [])
            flex_validation_dict[key].append('Yellow')
            flex_validation_dict[key].append(status_saxoreport)

        else:
            key = 'saxoreport'
            flex_validation_dict.setdefault(key, [])
            flex_validation_dict[key].append('Red')
            flex_validation_dict[key].append(status_saxoreport)
            send_alert(key, 'Red', "flex")
    except Exception as e:
        if (ENV != "dev"): send_exection_alert("Error while checking flex validation")
    return flex_validation_dict
