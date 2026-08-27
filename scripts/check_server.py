import urllib.request, urllib.error
try:
    r = urllib.request.urlopen("http://localhost:8000/docs", timeout=5)
    print(f"SERVER UP: HTTP {r.status}")
except urllib.error.URLError as e:
    print(f"SERVER DOWN: {e.reason}")
except Exception as e:
    print(f"ERROR: {e}")
