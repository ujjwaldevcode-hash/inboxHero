"""Generate the final security-first InboxHero dashboard."""
from pathlib import Path
from dashboard_security_first import BASE_DIR, INBOX_PATH, load_inbox, build_dashboard, render_dashboard

if __name__ == "__main__":
    root = Path(BASE_DIR)
    messages = load_inbox(INBOX_PATH)
    data = build_dashboard(messages, root)
    render_dashboard(root, data)
    print(f"Generated {root / 'dashboard.html'}")
