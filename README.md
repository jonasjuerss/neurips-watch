# NeurIPS 2026 Sydney ticket watcher

Checks https://neurips.cc/Register/view-registration every 5 minutes and sends
a push notification (via ntfy) when a Sydney session is no longer "Sold Out".

## Setup
1. Install the ntfy app (ntfy.sh) and subscribe to a long random topic name.
2. Create a **public** GitHub repo (Actions minutes are free for public repos)
   and push these files, keeping the `.github/workflows/` folder.
3. Settings → Secrets and variables → Actions → New repository secret:
   `NTFY_TOPIC` = your topic name.
4. Actions tab → enable workflows if prompted → "NeurIPS Sydney ticket watcher"
   → Run workflow. Check the log shows `sold_out` for both Sydney sessions.

To watch different sessions, add a `SESSIONS` env var in the workflow
(comma-separated, exact names as shown on the registration page).
To stop: Actions → the workflow → "..." → Disable workflow.
