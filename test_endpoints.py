import sys
from webui import app
with app.app_context():
    client = app.test_client()
    for route in ['/', '/api/stats', '/api/projects', '/api/config', '/api/genres']:
        try:
            res = client.get(route)
            print(f"{route}: {res.status_code}")
            if res.status_code == 500:
                print("Error Data:", res.data.decode('utf-8'))
        except Exception as e:
            print(f"{route}: CRASH - {e}")
