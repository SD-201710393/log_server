import datetime
from datetime import timedelta
import json
import os
import threading
import time
import requests
from operator import itemgetter
from flask import Flask
from flask import request
from flask import render_template
from werkzeug.exceptions import BadRequest

app = Flask(__name__)

global_id = 0
update_cycle = 5    # How many seconds between each update
entry_list = []


class LogEntry:
    def __init__(self, body=None, to="Unknown", s_from="Unknown", comm="Not Specified"):
        global global_id
        self.msg_id = global_id
        self.entry = {
            "to": to,
            "from": s_from,
            "comment": comm,
            "timestamp": datetime.datetime.now().strftime("%d-%m-%Y : %H:%M:%S.%f"),
            "body": {} if None else body
        }
        global_id += 1

    def json(self):
        out = {
            "id": self.msg_id,
            "entry": self.entry
        }
        return out


@app.route('/log/clear', methods=["POST"])
def clear_logs():
    try:
        req = request.json
        req_from = "Unknown"
        req_comm = "Not Specified"
        try:
            req_from = req["from"]
        except KeyError:
            return "The 'from' field MUST be filled before clearing the logs", 403
        try:
            req_comm = req["comment"]
        except KeyError:
            req_comm = "Log Clear Request"
        entry = LogEntry(to="Log Server", s_from=req_from, comm=req_comm)
        entry_list.clear()
        entry_list.append(entry)
        return show_recent_entries()
    except BadRequest:
        return "Bad Request Ignored", 400


@app.route('/log', methods=["POST"])
def add_entry():
    try:
        req = request.json
        req_to = "Unknown"
        req_from = "Unknown"
        req_comm = "Not Specified"
        req_body = {}
        inputs = 0
        try:
            req_to = req["to"]
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
            entry = LogEntry(req_body, req_to, req_from, req_comm)
            entry_list.append(entry)
            return show_recent_entries()
        else:
            return "Empty Entry Ignored", 400
    except BadRequest:
        return "Bad Entry Ignored", 400


@app.route('/log', methods=['GET'])
def show_recent_entries():
    out = {
        "count": len(entry_list),
        "last_update": datetime.datetime.now().strftime("%d-%m-%Y : %H:%M:%S"),
        "entries": []
    }
    for entry in reversed(entry_list):
        out["entries"].append(entry.json())
    return serve_page(out, 200)


@app.route('/log/old', methods=['GET'])
def show_entries():
    out = {
        "count": len(entry_list),
        "last_update": datetime.datetime.now().strftime("%d-%m-%Y : %H:%M:%S"),
        "entries": []
    }
    for entry in entry_list:
        out["entries"].append(entry.json())
    return serve_page(out, 200)


def serve_page(json_data, return_code):
    return render_template("log_table_flask.html", data=json_data), return_code


def main():
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))


if __name__ == "__main__":
    main()
