#!/bin/bash
set -e

echo "Building project for Vercel..."
python3 -m pip install -r requirements.txt
python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput

echo "Build complete!"
