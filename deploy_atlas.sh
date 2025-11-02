#!/bin/bash

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

# Use --allow-empty just in case the file content didn't change, but we still want a log entry.
git commit -m "Atlas update: $(date '+%Y-%m-%d %H:%M')"

# Use 'main' or 'master' depending on your repository's default branch
git push origin main

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Deployment complete."