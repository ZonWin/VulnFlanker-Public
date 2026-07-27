from __future__ import annotations

import argparse
import json
import socket
import sys
from datetime import datetime, timezone
from urllib import request


def build_payload(agent_id: str, hostname: str) -> dict[str, object]:
    return {
        "agent_id": agent_id,
        "agent_version": "0.1.0",
        "hostname": hostname,
        "primary_ip": "10.10.20.15",
        "platform": "linux",
        "os_family": "ubuntu",
        "os_version": "22.04",
        "kernel_version": "5.15.0-105-generic",
        "architecture": "x86_64",
        "environment_type": "production",
        "exposure_type": "internet",
        "business_system": "payments",
        "owner_team": "sre",
        "owner_person": "alice",
        "criticality": "high",
        "allow_auto_verify": True,
        "components": [
            {
                "component_name": "nginx",
                "component_type": "package",
                "version": "1.24.0",
                "source_type": "dpkg",
                "install_path": "/usr/sbin/nginx",
            },
            {
                "component_name": "openssl",
                "component_type": "package",
                "version": "3.0.2",
                "source_type": "dpkg",
            },
        ],
        "exposures": [
            {
                "exposure_kind": "network_service",
                "address": "203.0.113.20",
                "port": 443,
                "protocol": "tcp",
                "service_name": "https",
                "product": "nginx",
                "version": "1.24.0",
                "state": "open",
                "is_public": True,
                "banner": "nginx",
            }
        ],
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Submit a mock Linux asset snapshot to VulnFlanker.",
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8000/api/v1/agents/snapshots",
        help="Asset snapshot ingestion endpoint.",
    )
    parser.add_argument(
        "--agent-id",
        default=f"mock-{socket.gethostname()}",
        help="Stable mock agent identifier.",
    )
    parser.add_argument(
        "--hostname",
        default=socket.gethostname(),
        help="Asset hostname to include in the snapshot.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Only print the payload without sending it.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args.agent_id, args.hostname)

    if args.print_only:
        print(json.dumps(payload, indent=2))
        return 0

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        args.url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req) as response:
        print(f"HTTP {response.status}")
        print(response.read().decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
