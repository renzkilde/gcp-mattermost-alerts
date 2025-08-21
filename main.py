from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Mattermost Webhook URL
MATTERMOST_WEBHOOK_URL = os.getenv('MATTERMOST_WEBHOOK_URL')

@app.route('/gcloud-webhook', methods=['POST'])
def handle_gcloud_alert(request):
    # Flask will automatically pass the 'request' object
    incident_data = request.json  # Parse incoming JSON payload

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

    # Building the incident description dynamically
    incident_description = f"Condition: {incident_condition_name}\nPolicy: {incident_policy_name}\nProject: {project_id}\nModule: {module_id}\nVersion: {version_id}"

    # Constructing the Mattermost payload
    mattermost_payload = {
        "username": "Google Cloud Alert",  # Change the bot name here
        "icon_url": "https://fontawesome.com/icons/robot?f=classic&s=solid",
        "text": f"GCP Monitoring Notification: {incident_summary}",
        "attachments": [
            {
                "title": "Incident Details",
                "text": f"Summary: {incident_summary}\nDescription:\n {incident_description}\nURL: {incident_url}",
                "color": "danger"
            }
        ]
    }

    # Send the payload to Mattermost
    response = requests.post(MATTERMOST_WEBHOOK_URL, json=mattermost_payload)

    # Return a success response if Mattermost responded OK
    if response.status_code == 200:
        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'status': 'failure'}), 500

if __name__ == "__main__":
    # Flask will listen on the default port (8080) for HTTP requests
    app.run(debug=True, host='0.0.0.0', port=8080)
