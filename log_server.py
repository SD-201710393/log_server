import datetime
import json
import os
import time

from flask import Flask
from flask import request
from flask import render_template
from werkzeug.exceptions import BadRequest

from server_services import *

app = Flask(__name__)

global_id = 0
service_timeout = 10        # How many seconds between services? Used to prevent spam abuse and lock the log server
is_service_locked = False   # If true, another service cannot be invoked
def_per_page = 20           # How many entries per page
entry_list = []

known_servers = ["https://sd-rdm.herokuapp.com", "https://sd-201620236.herokuapp.com",
                 "https://sd-jhsq.herokuapp.com", "https://sd-app-server-jesulino.herokuapp.com",
                 "https://sd-mgs.herokuapp.com", "https://sd-dmss.herokuapp.com"]
shadow_servers = ["https://sd-rdm-shadow1.herokuapp.com", "https://sd-rdm-shadow2.herokuapp.com"]
secondary_servers = []


class LogEntry:
    def __init__(self, s_from="Unknown", severity="Information", comm="Not Specified", body=None):
        global global_id
        self.msg_id = global_id
        self.log_from = s_from
        self.severity = severity
        self.comment = comm
        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f - %d/%m/%Y")
        self.body = body
        self.flavor = {  # Cosmetic hints
            "severity": severity_flavor_keys(severity),
            "user_shade": user_shade_flavor_keys()
        }
        global_id += 1

    def json(self):
        out = {
            "id": self.msg_id,
            "from": self.log_from,
            "severity": self.severity,
            "comment": self.comment,
            "timestamp": self.timestamp,
            "body": self.body,
            "flavor": self.flavor
        }
        return out


@app.route('/server/status', methods=["GET"])   # Used to fetch data
def server_fetch():
    internal = {
        "entry_count": len(entry_list),
        "services_timedout": is_service_locked
    }
    return json.dumps(internal), 200


@app.route('/log/clear', methods=["POST"])
def clear_logs():
    try:
        req = request.json
        try:
            req_from = req["from"]
        except KeyError:
            return "The 'from' field MUST be filled before clearing the logs", 403
        try:
            req_comm = req["comment"]
        except KeyError:
            req_comm = "Log Clear Request"
        entry = LogEntry(s_from=req_from, severity="Information", comm=req_comm)
        entry_list.clear()
        entry_list.append(entry)
        return show_recent_entries()
    except BadRequest:
        return "Bad Request Ignored", 400


@app.route('/log', methods=["POST"])
def add_entry():
    try:
        req = request.json
        req_severity = "Unknown"
        req_from = "Unknown"
        req_comm = "Not Specified"
        req_body = {}
        inputs = 4
        try:
            req_severity = req["severity"]
        except KeyError:
            inputs -= 1
        try:
            req_from = req["from"]
        except KeyError:
            inputs -= 1
        try:
            req_comm = req["comment"]
        except KeyError:
            inputs -= 1
        try:
            req_body = req["body"]
        except KeyError:
            inputs -= 1
        if inputs > 0:
            entry_list.append(LogEntry(req_from, req_severity, req_comm, req_body))
            return show_recent_entries()
        else:
            return "Empty Entry Ignored", 400
    except BadRequest:
        return "Bad Entry Ignored", 400


@app.route('/log', methods=['GET'])
def show_recent_entries():
    handle_log_services()
    out, cur_page, max_page, per_page = prepare_page()
    rev = entry_list[::-1]
    for entry in rev[(cur_page - 1) * per_page:]:
        out["entries"].append(entry.json())
        if len(out["entries"]) == per_page:
            break
    return serve_page(out, 200)


@app.route('/log/old', methods=['GET'])
def show_entries():
    handle_log_services()
    out, cur_page, max_page, per_page = prepare_page()
    for entry in entry_list[(cur_page - 1) * per_page:]:
        out["entries"].append(entry.json())
        if len(out["entries"]) == per_page:
            break
    return serve_page(out, 200)


# noinspection PyBroadException
@app.route('/info', methods=['POST'])
def set_info():
    global secondary_servers
    try:
        if "secondary_servers" in request.json:
            secondary_servers = request.json["secondary_servers"]
    except ValueError:
        internal_log(severity="Attention", comment="Invalid value received when setting data", body=request.json)
    except TypeError:
        internal_log(severity="Error", comment="Request have an invalid type", body=request.json)
    except Exception as exc:
        log_uncaught_exception(str(exc), request.json)


@app.route('/info', methods=['GET'])
def info():
    out = {
        "note": "Wrong server for that, pal ;)",
        "componente": "Log Server",
        "versao": "1.0.2",
        "descricao": "Provides a public, default and easy to use visual log interface",
        "ponto_de_acesso": "https://sd-log-server.herokuapp.com",
        "status": "Always up",
        "identificacao": -1,
        "lider": 0,
        "eleicao": "All of them ;)",
        "sobre": ["Fully coded, back & front by Ramon Darwich de Menezes", "https://github.com/XLM-205",
                  "http://lattes.cnpq.br/2510824092604238"],
        "databases": {
            "servers": {
                "known_servers": known_servers,
                "secondary_servers": secondary_servers
            }
        }
    }
    return json.dumps(out), 418


# noinspection PyBroadException
def handle_log_services():     # If supplied by the url, execute services
    try:
        urls = []
        if request.args.get("ssrc") is None:        # If no 'ssrc', 'Server SouRCe' supplied, just abort handling
            return
        elif "all" in request.args.get("ssrc"):     # Use all known servers
            urls = known_servers
        elif "shadow" in request.args.get("ssrc"):  # Use the shadow servers
            urls = shadow_servers
        elif "secondary" in request.args.get("ssrc"):
            if len(secondary_servers) == 0:
                internal_log(severity="Attention",
                             comment="Request for internal service with empty secondary url database defined!")
            else:
                urls = secondary_servers
        else:
            internal_log(severity="Error", comment="Request for internal service without url database defined!")
            return
        # All ready to process the request
        if is_service_locked is False:
            internal_log(severity="Success", comment="Working on your service request. Results coming shortly...")
            arg_list = [request.args.get("pi"),     # Order is: [0] - Pull Info Mode | [1] - Run Election | [2] - Set All
                        request.args.get("sime"),
                        request.args.get("stt")]
            threading.Thread(target=handle_demanding, args=(urls, arg_list)).start()
        else:
            internal_log(severity="Warning",
                         comment=f"Services are in time out. Please wait {service_timeout} seconds before another request")
        threading.Thread(target=enforce_timeout).start()
    except Exception as exc:
        log_uncaught_exception(str(exc), request.json)


def handle_demanding(urls, args=None):    # All demanding tasks that require an update afterwards
    try:
        if args is None:
            internal_log(severity="Attention", comment="Empty Demanding request ignored")
            return
        pi_data, valid_servers, invalid_servers = pull_info(urls)
        if args[0] is not None:
            if 'v' in args[0]:
                for server in pi_data:
                    internal_log(severity=server["severity"], comment=server["message"], body=server["body"])
            else:
                for server in invalid_servers:
                    internal_log(severity=server["severity"], comment=server["message"], body=server["body"])
            internal_log(severity="Success",
                         comment=f"Server pull finished. {len(valid_servers)} servers are ready",
                         body=valid_servers)
        if args[1] is not None:
            if 'ring' in args[1]:
                election_servers = [svr for svr, elec in valid_servers if 'anel' in elec]
            elif 'bully' in args[1]:
                election_servers = [svr for svr, elec in valid_servers if 'valentao' in elec]
            else:
                internal_log(severity="Warning", comment=f"Unsupported election of type '{args[1]}' requested")
                return
            if len(election_servers) == 0:
                internal_log(severity="Attention", comment=f"There are no servers running '{args[1]}' elections")
            elif len(election_servers) == 1:
                internal_log(severity="Warning", comment=f"Only '{election_servers[0]}' is running '{args[1]}' elections")
            entry_dump = simulate_election(election_servers, args[1])
            for entry in entry_dump:
                internal_log(entry[0], entry[1], entry[2])
        if args[2] is not None:
            if 'ring' in args[2]:
                tgt_election = 'anel'
            elif 'bully' in args[2]:
                tgt_election = 'valentao'
            else:
                internal_log(severity="Warning", comment=f"Unsupported election of type '{args[2]}' requested")
                return
            internal_log(severity="Information", comment=f"Attempting to set all servers to '{tgt_election}'...")
            entry_dump = set_all_elections(valid_servers, tgt_election)
            for entry in entry_dump:
                internal_log(entry[0], entry[1], entry[2])
    except Exception as exc:
        log_uncaught_exception(str(exc), request.json)


def get_page_format():      # Returns the page, max page and epp based on the url arguments
    entry_count = len(entry_list)
    try:
        if request.args.get("epp") is not None and 0 < int(request.args.get("epp")) <= entry_count:
            per_page = int(request.args.get("epp"))
        else:
            per_page = def_per_page
    except ValueError:  # Field 'epp=" was too big
        per_page = def_per_page
    div = entry_count % per_page
    if div == 0:
        max_page = int(entry_count / per_page)
    else:
        max_page = int(entry_count / per_page) + 1
    try:
        if request.args.get("p") is not None and max_page >= int(request.args.get("p")) > 0:
            cur_page = int(request.args.get("p"))
        else:
            cur_page = 1
    except ValueError:  # Field 'p=' wasn't an integer
        cur_page = 1
    return cur_page, max_page, per_page


def prepare_page():
    cur_page, max_page, per_page = get_page_format()
    entries = len(entry_list)
    out = {
        "page": (cur_page if entries > 0 else 0),
        "page_max": max_page,
        "epp": per_page,
        "count": entries,
        "last_update": datetime.datetime.now().strftime("%H:%M:%S - %d/%m/%Y"),
        "entries": []
    }
    return out, cur_page, max_page, per_page


def serve_page(json_data, return_code):
    return render_template("log_table_flask.html", data=json_data), return_code


def severity_flavor_keys(severity: str):
    sev = severity.lower()
    if sev == "warning" or sev == "aviso":
        return "sev_warning"
    if sev == "attention" or sev == "atencao" or sev == "alerta":
        return "sev_attention"
    if sev == "error" or sev == "erro":
        return "sev_error"
    if sev == "critical" or sev == "critico":
        return "sev_critical"
    if sev == "success" or sev == "sucesso":
        return "sev_success"
    else:
        return "sev_default"


def user_shade_flavor_keys():
    # usr = user_shade.lower()
    # If more users want colors, add them here, but NEVER add the "Internal", that should be handled manually!
    return "usr_default"


def internal_log(severity="Information", comment="Not Specified", body=None):
    global entry_list
    entry_list.append(LogEntry("Internal", severity, comment, ({} if body is None else body)))
    entry_list[-1].flavor["user_shade"] = "internal"


def log_uncaught_exception(exc, body_json):
    internal_log(severity="Critical", comment=f"Uncaught exception: '{exc}'", body=body_json)


def enforce_timeout():
    global is_service_locked
    is_service_locked = True
    time.sleep(service_timeout)
    is_service_locked = False


def d_fill_server():
    for i in range(100):
        internal_log("Testing", "Navigation Test")


def main():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    internal_log(severity="Success", comment="Log Server Started successfully")
    main()
