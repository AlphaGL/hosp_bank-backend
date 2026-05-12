#!/usr/bin/env bash
# setup.sh — Vercel build script for the Hospital Diagnostic System
# Vercel runs this automatically during the build phase.
set -e  # exit immediately on any error

echo "──────────────────────────────────────────"
echo " Installing Python dependencies..."
echo "──────────────────────────────────────────"
pip install -r requirements.txt

echo "──────────────────────────────────────────"
echo " Collecting static files..."
echo "──────────────────────────────────────────"
python manage.py collectstatic --noinput

echo "──────────────────────────────────────────"
echo " Running database migrations..."
echo "──────────────────────────────────────────"
python manage.py migrate --noinput

echo "──────────────────────────────────────────"
echo " Build complete."
echo "──────────────────────────────────────────"