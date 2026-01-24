import requests
restart_response = requests.post("http://localhost:8083/connectors/events-sink/restart", params={"includeTasks": "true", "silent": "false"})
response = requests.get("http://localhost:8083/connectors/events-sink/status")
response.json()
