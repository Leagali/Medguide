"""HTTP request smoke against a running MedGuide API, with disabled source only."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import httpx

from medguide.infrastructure.settings import Settings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--allow-unready", action="store_true")
    args = parser.parse_args()
    token = Settings().admin_token.get_secret_value()
    if not token:
        raise SystemExit("Configure MEDGUIDE_ADMIN_TOKEN in the environment or .env")
    checks = []
    with httpx.Client(
        base_url=args.url, headers={"Authorization": f"Bearer {token}"}, timeout=10, trust_env=False
    ) as client:

        def check(method, path, expected, **kwargs):
            response = client.request(method, path, **kwargs)
            checks.append({"method": method, "path": path, "status": response.status_code})
            assert response.status_code == expected, f"{method} {path}: {response.status_code}"
            return response

        check("GET", "/healthz", 200)
        ready = client.get("/readyz")
        assert ready.status_code == 200 or args.allow_unready
        checks.append({"method": "GET", "path": "/readyz", "status": ready.status_code})
        check("GET", "/api/sources", 401, headers={"Authorization": "Bearer invalid"})
        code = f"smoke_{uuid4().hex[:12]}"
        source = check("POST", "/api/sources", 201, json={"code": code, "enabled": False}).json()
        check("POST", "/api/sources", 409, json={"code": code, "enabled": False})
        check("POST", "/api/sources", 422, json={"connector_key": "unapproved"})
        check("POST", f"/api/sources/{source['id']}/discover", 409)
        check("GET", "/api/guidelines", 200)
        check("GET", "/api/runs", 200)
        check("GET", "/api/jobs", 200)
        check("GET", "/api/metrics", 200)
    output = Path("test-results")
    output.mkdir(exist_ok=True)
    report = {"base_url": args.url, "checks": checks}
    (output / "http-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
