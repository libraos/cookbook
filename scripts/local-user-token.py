"""Local password login helper; stdout is only the token for shell capture."""
import getpass
import os
import sys

import httpx

print("Normal user's email: ", end="", file=sys.stderr, flush=True)
email = input()
password = getpass.getpass("Password: ")
response = httpx.post(
    os.environ.get("LIBRA_OS_URL", "http://localhost:8900") + "/api/auth/login",
    json={"email": email, "password": password}, timeout=30,
)
response.raise_for_status()
print(response.json()["access_token"])
