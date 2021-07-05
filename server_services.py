import random
import string
import threading
import requests


# Calls target and returns data in the format tuple(<error_code>, <json>)
# Error codes: 0- No errors | 1- Connection Error | 2- Empty response
def server_request_info(target, data):
    endpoint = '/info'
    try:
        t_data = requests.get(target + endpoint).json()
        if t_data is None or t_data == {}:
            data.append((2, target, t_data))
        else:
            data.append((0, target, t_data))
    except requests.ConnectionError:
        data.append((1, target, None))


def pull_info(urls):
    server_data = []
    thrs = []
    for url in urls:
        thrs.append(threading.Thread(target=server_request_info, args=(url, server_data)))
        thrs[-1].start()
    for t in thrs:
        t.join()
    pi_data = []
    valid_list = []         # Holds the URLs of valid servers and it's election type
    invalid_list = []       # Holds all invalid servers
    for index, svr in enumerate(server_data):
        pi_info = {
            "invalid": 1,  # If 1, the server should not be used
            "server": "",
            "severity": "Information",
            "is_down": True,
            "id": -1,
            "election": "Not Specified",
            "message": "Not Specified",
            "body": None
        }
        try:
            pi_info["server"] = svr[1]
            if svr[0] == 1:
                pi_info["message"] = f"'{svr[1]}' is Offline"
                invalid_list.append(pi_info)
            elif svr[0] == 2:
                pi_info["message"] = f"'{svr[1]}' didn't responded"
                invalid_list.append(pi_info)
            elif svr[0] == 0:
                pi_info["invalid"] = 0
                pi_info["is_down"] = svr[2]["status"]
                pi_info["id"] = svr[2]["identificacao"]
                pi_info["election"] = svr[2]["eleicao"]
                pi_info["severity"] = "Success"
                pi_info["message"] = f"'{svr[1]}' ID:[{pi_info['id']}] is Online"
                if pi_info["is_down"] == 'down':                    # Is the server up?
                    pi_info["message"] += " but is down "
                elif pi_info["is_down"] == 'up':
                    pi_info["message"] += ", up "
                else:
                    pi_info["message"] += " but in an invalid state "
                    pi_info["invalid"] = 1
                if pi_info["election"] == 'anel' or 'valentao':     # Which election mode it is in?
                    pi_info["message"] += f" and using '{pi_info['election']}' election "
                else:
                    pi_info["message"] += f" and using the invalid election of '{pi_info['election']}' "
                    pi_info["invalid"] = 1
                if pi_info["invalid"] == 1:
                    pi_info["severity"] = "Warning"
                    invalid_list.append(pi_info)
                else:
                    valid_list.append((pi_info["server"], pi_info["election"]))
            else:
                pi_info["message"] = f"'{svr[1]}' didn't responded correctly"
                pi_info["severity"] = "Attention"
                invalid_list.append(pi_info)
        except KeyError:
            pi_info["message"] = f"'{svr[1]}' doesn't have the required keys"
            pi_info["severity"] = "Error"
            invalid_list.append(pi_info)
        except TypeError:
            pi_info["message"] = f"'{svr[1]}' didn't responded correctly"
            pi_info["severity"] = "Error"
            invalid_list.append(pi_info)
        except Exception as exc:
            pi_info["message"] = f"'{svr[1]}' produced an unknown exception: {str(exc)}"
            pi_info["severity"] = "Critical"
            invalid_list.append(pi_info)
        pi_info["body"] = svr[2]
        pi_data.append(pi_info)
    return pi_data, valid_list, invalid_list


def simulate_election(targets, election_type):     # Returns the starter server and a log entry in a tuple
    random.shuffle(targets)
    log_entry = []
    election = {
        "id": "LogServer_" + ''.join(random.choices(string.ascii_letters + string.digits, k=5)),
        "participantes": []
    }
    for server in targets:
        try:
            response = requests.post(server + '/eleicao', json=election)
            if response.status_code == 200:
                log_entry.append(("Success",
                                  f"'{election_type}' Election '{election['id']}' request to server '{server}' was successful", election))
                return log_entry
            elif response.status_code == 400:
                log_entry.append(("Error",
                                  f"The Log Server sent a request that wasn't accepted by '{server}' [400]", election))
                return log_entry
            elif response.status_code == 409:
                log_entry.append(("Warning", f"There is an election already running [409]", None))
                return log_entry
            else:
                log_entry.append(("Attention",
                                  f"'{server}' responded with the untreated code of [{response.status_code}]", election))
        except requests.ConnectionError:
            log_entry.append(("Attention", f"'{server}' couldn't be reached. Attempting another server...", None))
        except Exception as exc:
            log_entry.append(("Critical", f"Uncaught exception: '{str(exc)}'", election))
            return log_entry
    log_entry.append(("Error", f"No server could be reached", election))
    return log_entry
