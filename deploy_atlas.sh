#!/bin/bash

# --- CONFIGURATION REQUIRED: ONLY GITHUB_USERNAME SHOULD BE INCLUDED HERE! ---
# The PAT_TOKEN is now read from the environment variable $GITHUB_TOKEN for security.
GITHUB_USERNAME="smithdanieldavid-cpu"
PAT_TOKEN="${GITHUB_TOKEN}" # SECURED: Reads the token from the GITHUB_TOKEN environment variable

# 1. Navigate to the project directory
cd /Users/dansmith/PersonalProjects/atlas-dashboard

# 2. Run the Python script to generate the latest data
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Atlas data generation."
/Users/dansmith/PersonalProjects/atlas-dashboard/.venv/bin/python update_atlas.py

# Check if the Python script succeeded before continuing
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Python script failed. Aborting Git push."
    exit 1
fi

# 3. Add, Commit, and Push the updated JSON file
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Git deployment."

git add data/atlas-latest.json

# Commit the changes.
git commit -m "Atlas update: $(date '+%Y-%m-%d %H:%M')"

# --- PUSH USING HTTPS AND THE ENVIRONMENT VARIABLE TOKEN ---
# This constructs the secure URL using the GITHUB_USERNAME and the PAT_TOKEN from the environment.
GIT_URL_WITH_PAT="https://${GITHUB_USERNAME}:${PAT_TOKEN}@github.com/smithdanieldavid-cpu/atlas-dashboard.git"

# The PAT must be valid and must have been set in the environment where this script runs (e.g., in your cron job).
git push ${GIT_URL_WITH_PAT} main

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deployment complete."