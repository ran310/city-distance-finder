#!/bin/bash
# CodeDeploy: stop this app, replace app tree (venv is outside the tree).
set -euxo pipefail

systemctl stop city-distance-finder || true

rm -rf /opt/city-distance-finder/app
mkdir -p /opt/city-distance-finder/app
