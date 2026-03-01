import sys
from webui import app
with app.app_context():
    client = app.test_client()
    response = client.get('/api/stats')
    print("Status:", response.status_code)
    print("Data:", response.data.decode('utf-8'))
