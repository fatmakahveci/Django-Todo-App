"""Check HTTP readiness through the same HTTPS proxy contract as production."""

import os
from urllib.request import Request, urlopen

host = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")[0].strip()
request = Request(
    "http://127.0.0.1:8000/healthz/",
    headers={"Host": host, "X-Forwarded-Proto": "https"},
)
with urlopen(request, timeout=4) as response:
    if response.status != 200:
        raise SystemExit("Application is not ready")
