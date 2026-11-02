#!/usr/bin/env bash
# Render start command.
#
# Seeding runs on every boot but writes nothing when the database already has
# users, so a restart cannot wipe a live deployment. Without it, a fresh deploy
# would have no exam office account and therefore no way in at all.
set -e

python seed.py || echo "Seed skipped."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
