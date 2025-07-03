from flask import Flask, request, jsonify, render_template
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(mongo_uri)
db = client["github_actions"]
events_collection = db["events"]

def format_timestamp(timestamp_str):
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%dT%H:%M:%SZ")
        return dt.strftime("%d %B %Y - %I:%M %p UTC")
    except ValueError:
        return timestamp_str

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json
    event_type = request.headers.get("X-GitHub-Event")

    event_data = {
        "_id": None,
        "request_id": None,
        "author": None,
        "action": None,
        "from_branch": None,
        "to_branch": None,
        "timestamp": None
    }

    if event_type == "push":
        event_data["action"] = "PUSH"
        event_data["request_id"] = payload["after"]
        event_data["author"] = payload["pusher"]["name"]
        event_data["to_branch"] = payload["ref"].split("/")[-1]
        event_data["timestamp"] = format_timestamp(payload["head_commit"]["timestamp"])
        event_data["from_branch"] = None

    elif event_type == "pull_request":
        pr_action = payload["action"]
        if pr_action in ["opened", "reopened"]:
            event_data["action"] = "PULL_REQUEST"
            event_data["request_id"] = str(payload["pull_request"]["id"])
            event_data["author"] = payload["pull_request"]["user"]["login"]
            event_data["from_branch"] = payload["pull_request"]["head"]["ref"]
            event_data["to_branch"] = payload["pull_request"]["base"]["ref"]
            event_data["timestamp"] = format_timestamp(payload["pull_request"]["created_at"])
        elif pr_action == "closed" and payload["pull_request"]["merged"]:
            event_data["action"] = "MERGE"
            event_data["request_id"] = str(payload["pull_request"]["id"])
            event_data["author"] = payload["pull_request"]["user"]["login"]
            event_data["from_branch"] = payload["pull_request"]["head"]["ref"]
            event_data["to_branch"] = payload["pull_request"]["base"]["ref"]
            event_data["timestamp"] = format_timestamp(payload["pull_request"]["merged_at"])

    if event_data["action"]:
        events_collection.insert_one(event_data)
        return jsonify({"status": "success"}), 200

    return jsonify({"status": "ignored"}), 200

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/events", methods=["GET"])
def get_events():
    events = list(events_collection.find().sort("timestamp", -1).limit(50))
    for event in events:
        event["_id"] = str(event["_id"])
    return jsonify(events)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)