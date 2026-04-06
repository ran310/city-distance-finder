#!/bin/bash
# CodeDeploy: systemd unit (must match aws-infra ec2-nginx userData bootstrap port 8086).
set -euxo pipefail

cat > /etc/systemd/system/city-distance-finder.service <<'UNIT'
[Unit]
Description=City distance finder (Gunicorn)
After=network.target
ConditionPathExists=/opt/city-distance-finder/venv/bin/gunicorn

[Service]
Type=simple
User=root
WorkingDirectory=/opt/city-distance-finder/app
EnvironmentFile=/etc/city-distance-finder.env
ExecStart=/opt/city-distance-finder/venv/bin/gunicorn --bind 127.0.0.1:8086 --workers 2 --threads 2 --timeout 120 app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable city-distance-finder
systemctl restart city-distance-finder
systemctl is-active city-distance-finder
