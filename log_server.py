import datetime
import json
import os
import server_services

from flask import Flask
from flask import request
from flask import render_template
from werkzeug.exceptions import BadRequest

app = Flask(__name__)

global_id = 0
service_timeout = 10        # How many seconds between services? Used to prevent spam abuse and lock the log server
is_service_locked = False   # If true, another service cannot be invoked
def_per_page = 20           # How many entries per page
entry_list = []


class LogEntry:
    def __init__(self, s_from="Unknown", severity="Information", comm="Not Specified", body=None):
        global global_id
        self.msg_id = global_id
        self.log_from = s_from + nickname(s_from)
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
        # "services_timedout": is_service_locked
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
    # handle_log_services() # Disabled on this version
    out, cur_page, max_page, per_page = prepare_page()
    rev = entry_list[::-1]
    for entry in rev[(cur_page - 1) * per_page:]:
        out["entries"].append(entry.json())
        if len(out["entries"]) == per_page:
            break
    return serve_page(out, 200)


@app.route('/log/old', methods=['GET'])
def show_entries():
    # handle_log_services() # Disabled on this version
    out, cur_page, max_page, per_page = prepare_page()
    for entry in entry_list[(cur_page - 1) * per_page:]:
        out["entries"].append(entry.json())
        if len(out["entries"]) == per_page:
            break
    return serve_page(out, 200)


# noinspection PyBroadException
# @app.route('/info', methods=['POST'])
# def set_info():
#    global secondary_servers
#    try:
#        if "secondary_servers" in request.json:
#            secondary_servers = request.json["secondary_servers"]
#    except ValueError:
#        internal_log(severity="Attention", comment="Invalid value received when setting data", body=request.json)
#    except TypeError:
#        internal_log(severity="Error", comment="Request have an invalid type", body=request.json)
#    except Exception as exc:
#        log_uncaught_exception(str(exc), request.json)


@app.route('/info', methods=['GET'])
def info():
    out = {
        "note": "Wrong server for that, pal ;)",
        "componente": "Log Server",
        "versao": "1.2.0",
        "descricao": "Provides a public, standardized and easy to use visual log interface",
        "ponto_de_acesso": "https://sd-log-server.herokuapp.com",
        "status": "Always up",
        "identificacao": -1,
        "lider": 0,
        "eleicao": "All of them ;)",
        "sobre": ["Fully coded, back & front by Ramon Darwich de Menezes", "https://github.com/XLM-205",
                  "http://lattes.cnpq.br/2510824092604238"],
        "databases": {
            "servers": {
                "known_servers": server_services.known_servers,
                # "secondary_servers": secondary_servers
            }
        }
    }
    return json.dumps(out), 418


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


def nickname(url):
    try:
        for server in server_services.known_servers:
            if server["url"] == url:
                return "(" + server["nome"] + ")"
    except KeyError:
        internal_log(severity="Error", comment="Known server list's 'url' key is missing!")
    except Exception as exc:
        log_uncaught_exception(str(exc), request.json)
    return ""


def internal_log(severity="Information", comment="Not Specified", body=None):
    global entry_list
    entry_list.append(LogEntry("Internal", severity, comment, body))
    entry_list[-1].flavor["user_shade"] = "internal"


def log_uncaught_exception(exc, body_json):
    internal_log(severity="Critical", comment=f"Uncaught exception: '{exc}'", body=body_json)


def d_fill_server():
    for i in range(100):
        internal_log("Testing", "Navigation Test")


def main():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    internal_log(severity="Success", comment="Log Server Started successfully")
    main()
