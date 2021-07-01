import datetime
import os
import unicodedata

from flask import Flask
from flask import request
from flask import render_template
from werkzeug.exceptions import BadRequest

app = Flask(__name__)

global_id = 0
update_cycle = 5    # How many seconds between each update
def_per_page = 20   # How many entries per page
entry_list = []


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
            "severity": severity_flavor_keys(severity)
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
        inputs = 0
        try:
            req_severity = req["severity"]
            inputs += 1
        except KeyError:
            pass
        try:
            req_from = req["from"]
            inputs += 1
        except KeyError:
            pass
        try:
            req_comm = req["comment"]
            inputs += 1
        except KeyError:
            pass
        try:
            req_body = req["body"]
            inputs += 1
        except KeyError:
            pass
        if inputs > 0:
            entry = LogEntry(req_from, req_severity, req_comm, req_body)
            entry_list.append(entry)
            return show_recent_entries()
        else:
            return "Empty Entry Ignored", 400
    except BadRequest:
        return "Bad Entry Ignored", 400


@app.route('/log', methods=['GET'])
def show_recent_entries():
    out, cur_page, max_page, per_page = prepare_page()
    rev = entry_list[::-1]
    for entry in rev[(cur_page - 1) * per_page:]:
        out["entries"].append(entry.json())
        if len(out["entries"]) == per_page:
            break
    return serve_page(out, 200)


@app.route('/log/old', methods=['GET'])
def show_entries():
    out, cur_page, max_page, per_page = prepare_page()
    for entry in entry_list[(cur_page - 1) * per_page:]:
        out["entries"].append(entry.json())
        if len(out["entries"]) == per_page:
            break
    return serve_page(out, 200)


def get_page_format():     # Returns the page, max page and epp based on the url arguments
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


def d_fill_server():
    for i in range(100):
        entry = LogEntry("Internal", "Testing", "Navigation Test", {})
        entry_list.append(entry)


def main():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    entry_list.append(LogEntry("Internal", "Success", "Log Server Started", {}))
    d_fill_server()
    main()
