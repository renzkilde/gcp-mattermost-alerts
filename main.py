from flask import Flask, request, jsonify
import requests
import os
from google.auth import default
from google.auth.transport.requests import Request

app = Flask(__name__)

# Mattermost Webhook URL
MATTERMOST_WEBHOOK_URL = os.getenv('MATTERMOST_WEBHOOK_URL')
RECENT_LOG_COUNT = os.getenv('RECENT_LOG_COUNT')

def get_access_token():
    """Get an access token using the service account attached to Cloud Run."""
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    return credentials.token

def fetch_logs(instance_id: str, project_id: str, filter_query: str, limit: int = RECENT_LOG_COUNT):
    """Fetch logs with a given filter from Cloud Logging."""
    token = get_access_token()
    url = "https://logging.googleapis.com/v2/entries:list"
    headers = {"Authorization": f"Bearer {token}"}

    body = {
        "resourceNames": [f"projects/{project_id}"],
        "pageSize": limit,
        "orderBy": "timestamp desc",
        "filter": filter_query
    }

    response = requests.post(url, headers=headers, json=body)

    if response.status_code == 200:
        entries = response.json().get("entries", [])
        logs = []
        for entry in entries:
            logs.append(entry.get("textPayload") or str(entry.get("jsonPayload")) or "No log content")
        return logs if logs else ["No logs found."]
    else:
        return [f"Failed to fetch logs: {response.status_code} - {response.text}"]

@app.route('/gcloud-webhook', methods=['POST'])
def handle_gcloud_alert(request):  
    # Parse incoming JSON payload
    incident_data = request.json

    # Extracting relevant fields with fallback in case of missing keys
    incident_summary = incident_data['incident'].get('summary', 'No summary provided')
    incident_condition_name = incident_data['incident'].get('condition_name', 'No condition name provided')
    incident_policy_name = incident_data['incident'].get('policy_name', 'No policy name provided')
    incident_url = incident_data['incident'].get('url', 'No URL provided')

    # Handling missing resource labels with a fallback
    resource_labels = incident_data['incident'].get('resource', {}).get('labels', {})
    project_id = resource_labels.get('project_id', 'No project ID provided')
    module_id = resource_labels.get('module_id', 'No module ID provided')
    version_id = resource_labels.get('version_id', 'No version ID provided')
    instance_id = resource_labels.get('instance_id', 'No Instance ID provided')

    # Logs from GCE instance
    gce_logs = []
    if instance_id and project_id:
        gce_filter = f'resource.type="gce_instance" AND resource.labels.instance_id="{instance_id}"'
        gce_logs = fetch_logs(instance_id, project_id, gce_filter, limit=RECENT_LOG_COUNT)

    # Error Reporting logs
    error_logs = []
    if instance_id and project_id:
        error_filter = f'resource.type="gce_instance" AND resource.labels.instance_id="{instance_id}" AND severity=ERROR'
        error_logs = fetch_logs(instance_id, project_id, error_filter, limit=RECENT_LOG_COUNT)

    # Build the incident description including logs
    incident_description = (
        f"Condition: {incident_condition_name}\n"
        f"Policy: {incident_policy_name}\n"
        f"Project: {project_id}\n"
        f"Module: {module_id}\n"
        f"Version: {version_id}\n\n"
        # Uncomment if want to Display Instance Logs
        # f"Current Instance Logs:\n```\n" + "\n---\n".join(gce_logs) + "\n```\n\n"
        f"Recent Error Logs:\n```\n" + "\n---\n".join(error_logs) + "\n```"
    )

    # Constructing the Mattermost payload
    mattermost_payload = {
        "username": "Google Cloud Alert",
        "icon_url": "https://fontawesome.com/icons/robot?f=classic&s=solid",
        "text": f"GCP Monitoring Notification: {incident_summary}",
        "attachments": [
            {
                "title": "Incident Details",
                "text": f"Summary: {incident_summary}\nDescription:\n{incident_description}\nURL: {incident_url}",
                "color": "danger"
            }
        ]
    }

    # Send the payload to Mattermost
    response = requests.post(MATTERMOST_WEBHOOK_URL, json=mattermost_payload)

    if response.status_code == 200:
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'status': 'failure', 'detail': response.text}), 500

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
