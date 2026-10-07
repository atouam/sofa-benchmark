#!/bin/bash
set -euo pipefail
# Protect tests even if Harbor's upload restores their host permissions.
chmod -R go-rwx /tests
python -I /tests/verify.py
