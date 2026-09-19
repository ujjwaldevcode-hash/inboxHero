"""Build the reproducible R6 dashboard artifacts."""
import html
import json
from pathlib import Path
from .commitments import extract_commitments, scheduling_conflicts
from .rules import triage
from .security import scan_inbox


def build_dashboard(messages):
    decisions = triage(messages)
    threats = scan_inbox(messages)
    by_id = {m.id: m for m in messages}

    pending = []
    for d in decisions:
        if d.disposition != "archive":
            pending.append({
                "message_id": d.message_id,
                "subject": by_id[d.message_id].subject,
                "disposition": d.disposition,
                "reason": d.reason,
                "risk": d.risk,
            })

    flagged = [{
        "message_id": t.message_id,
        "category": t.category,
        "attempted_action": t.attempted_action,
        "evidence": t.evidence,
        "decision": "refused",
    } for t in threats]

    return {
        "panes": {
            "pending_actions": pending,
            "flagged": flagged,
            "commitments": extract_commitments(messages),
        },
        "conflicts": scheduling_conflicts(messages),
        "metadata": {
            "messages_processed": len(messages),
            "pending_count": len(pending),
            "flagged_count": len(flagged),
        },
    }


def write_dashboard(root: Path, data: dict):
    (root / "dashboard.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    p = data["panes"]
    pending_rows = "".join(
        f"<tr><td>{html.escape(x['message_id'])}</td><td>{html.escape(x['subject'])}</td>"
        f"<td>{html.escape(x['disposition'])}</td><td>{html.escape(x['reason'])}</td></tr>"
        for x in p["pending_actions"]
    ) or "<tr><td colspan='4'>None</td></tr>"

    flagged_rows = "".join(
        f"<tr><td>{html.escape(x['message_id'])}</td><td>{html.escape(x['category'])}</td>"
        f"<td>{html.escape(x['attempted_action'])}</td><td>REFUSED</td></tr>"
        for x in p["flagged"]
    ) or "<tr><td colspan='4'>None</td></tr>"

    commitment_rows = "".join(
        f"<tr><td>{html.escape(x['title'])}</td><td>{html.escape(x['when'])}</td>"
        f"<td>{html.escape(x['status'])}</td><td>{html.escape(', '.join(x['source_message_ids']))}</td></tr>"
        for x in p["commitments"]
    ) or "<tr><td colspan='4'>None</td></tr>"

    conflict_html = "".join(
        f"<div class='conflict'><strong>CONFLICT:</strong> {html.escape(c['description'])} "
        f"Sources: {html.escape(', '.join(c['messages']))}. {html.escape(c['resolution'])}</div>"
        for c in data["conflicts"]
    )

    # The dashboard is intentionally self-contained: no CDN, framework, or server is
    # required.  It remains reproducible from dashboard.json and keeps exactly three
    # content panes required by R6.
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>InboxHero · Dashboard</title>
<style>
:root {{
  --bg:#f4f6f8; --surface:#fff; --ink:#172033; --muted:#687386;
  --line:#e5e9ef; --accent:#4f46e5; --accent-soft:#eef2ff;
  --danger:#b42318; --danger-soft:#fff1f0; --warn:#9a6700; --warn-soft:#fff8e6;
  --success:#16794a; --success-soft:#ecfdf3; --shadow:0 8px 28px rgba(31,41,55,.07);
}}
* {{ box-sizing:border-box }}
body {{ margin:0; font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  background:linear-gradient(180deg,#f8fafc 0%,var(--bg) 100%); color:var(--ink); }}
main {{ max-width:1500px; margin:0 auto; padding:30px 24px 48px; }}
header {{ display:flex; justify-content:space-between; align-items:flex-end; gap:24px; margin-bottom:22px; }}
h1 {{ margin:0; font-size:clamp(1.8rem,3vw,2.5rem); letter-spacing:-.04em; }}
.subtitle {{ color:var(--muted); margin-top:7px; font-size:.96rem; }}
.brand {{ display:flex; align-items:center; gap:12px; }}
.logo {{ width:42px; height:42px; border-radius:12px; display:grid; place-items:center; background:var(--accent); color:white; font-weight:800; box-shadow:0 6px 16px rgba(79,70,229,.25); }}
.generated {{ color:var(--muted); font-size:.8rem; text-align:right; }}
.metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:22px; }}
.metric {{ background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:15px 17px; box-shadow:var(--shadow); }}
.metric .value {{ font-size:1.6rem; font-weight:800; line-height:1.1; }}
.metric .label {{ color:var(--muted); font-size:.78rem; margin-top:4px; text-transform:uppercase; letter-spacing:.06em; }}
.grid {{ display:grid; grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr); gap:18px; }}
.pane {{ background:var(--surface); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); overflow:hidden; min-width:0; }}
.commitments {{ grid-column:1/-1; }}
.pane-head {{ display:flex; justify-content:space-between; align-items:center; gap:14px; padding:18px 20px; border-bottom:1px solid var(--line); }}
.pane-title {{ display:flex; align-items:center; gap:10px; }}
h2 {{ margin:0; font-size:1.05rem; letter-spacing:-.01em; }}
.count {{ display:inline-flex; align-items:center; justify-content:center; min-width:28px; height:24px; padding:0 8px; border-radius:999px; background:var(--accent-soft); color:var(--accent); font-size:.76rem; font-weight:800; }}
.flagged .count {{ background:var(--danger-soft); color:var(--danger); }}
.search {{ width:min(260px,45%); border:1px solid var(--line); border-radius:9px; padding:9px 11px; font:inherit; outline:none; background:#fbfcfe; }}
.search:focus {{ border-color:#a5b4fc; box-shadow:0 0 0 3px var(--accent-soft); }}
.table-wrap {{ overflow:auto; max-height:430px; }}
table {{ width:100%; border-collapse:separate; border-spacing:0; }}
th,td {{ text-align:left; padding:11px 14px; border-bottom:1px solid var(--line); vertical-align:top; font-size:.84rem; }}
th {{ position:sticky; top:0; z-index:1; background:#f8fafc; color:#566174; font-size:.72rem; text-transform:uppercase; letter-spacing:.055em; }}
tbody tr:hover {{ background:#fafbff; }}
td:first-child {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:700; white-space:nowrap; }}
.subject {{ min-width:190px; font-weight:650; }}
.reason {{ color:#596579; line-height:1.45; min-width:260px; }}
.badge {{ display:inline-flex; align-items:center; padding:4px 8px; border-radius:999px; font-size:.7rem; font-weight:800; text-transform:uppercase; letter-spacing:.035em; white-space:nowrap; }}
.badge-defer {{ background:var(--warn-soft); color:var(--warn); }}
.badge-escalate {{ background:var(--danger-soft); color:var(--danger); }}
.badge-reply {{ background:var(--success-soft); color:var(--success); }}
.badge-archive {{ background:#eef2f6; color:#526071; }}
.badge-refused {{ background:var(--danger-soft); color:var(--danger); }}
.flagged td:nth-child(3) {{ color:#596579; }}
.commitment-date {{ white-space:nowrap; font-weight:700; }}
.source {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; color:#4f46e5; font-size:.76rem; }}
.status {{ color:#596579; }}
.conflicts {{ padding:16px 20px 20px; }}
.conflict {{ padding:13px 15px; border:1px solid #f2b8b5; border-left:4px solid var(--danger); border-radius:10px; background:var(--danger-soft); }}
.conflict strong {{ color:var(--danger); }}
.conflict .meta {{ display:block; color:#7a3b36; margin-top:6px; font-size:.8rem; line-height:1.4; }}
.empty {{ text-align:center; color:var(--muted); padding:30px; }}
.footer {{ margin-top:16px; color:var(--muted); font-size:.78rem; text-align:center; }}
@media (max-width:900px) {{ .grid {{ grid-template-columns:1fr; }} .commitments {{ grid-column:auto; }} header {{ align-items:flex-start; flex-direction:column; }} .generated {{ text-align:left; }} }}
@media (max-width:640px) {{ main {{ padding:20px 12px 34px; }} .metrics {{ grid-template-columns:1fr; }} .pane-head {{ align-items:flex-start; flex-direction:column; }} .search {{ width:100%; max-width:none; }} th,td {{ padding:9px 10px; }} }}
</style>
</head>
<body>
<main>
<header>
  <div class="brand"><div class="logo">IH</div><div><h1>InboxHero</h1>
    <div class="subtitle">Inbox intelligence · completed run · {data['metadata']['messages_processed']} messages processed</div></div></div>
  <div class="generated">R6 Dashboard<br>Reproducible static view</div>
</header>

<div class="metrics" aria-label="Run summary">
  <div class="metric"><div class="value">{data['metadata']['pending_count']}</div><div class="label">Pending actions</div></div>
  <div class="metric"><div class="value">{data['metadata']['flagged_count']}</div><div class="label">Flagged</div></div>
  <div class="metric"><div class="value">{len(p['commitments'])}</div><div class="label">Commitments</div></div>
</div>

<div class="grid">
<section class="pane" id="pending-pane">
  <div class="pane-head"><div class="pane-title"><h2>Pending actions</h2><span class="count">{len(p['pending_actions'])}</span></div>
    <input class="search" data-table="pending-table" placeholder="Filter pending…" aria-label="Filter pending actions"></div>
  <div class="table-wrap"><table id="pending-table"><thead><tr><th>ID</th><th>Subject</th><th>Disposition</th><th>Why human review</th></tr></thead><tbody>{pending_rows}</tbody></table></div>
</section>

<section class="pane flagged" id="flagged-pane">
  <div class="pane-head"><div class="pane-title"><h2>Flagged</h2><span class="count">{len(p['flagged'])}</span></div>
    <input class="search" data-table="flagged-table" placeholder="Filter flagged…" aria-label="Filter flagged messages"></div>
  <div class="table-wrap"><table id="flagged-table"><thead><tr><th>ID</th><th>Category</th><th>Attempted action</th><th>Decision</th></tr></thead><tbody>{flagged_rows}</tbody></table></div>
</section>

<section class="pane commitments" id="commitments-pane">
  <div class="pane-head"><div class="pane-title"><h2>Commitments</h2><span class="count">{len(p['commitments'])}</span></div>
    <input class="search" data-table="commitments-table" placeholder="Filter commitments…" aria-label="Filter commitments"></div>
  <div class="table-wrap"><table id="commitments-table"><thead><tr><th>Commitment</th><th>When</th><th>Status</th><th>Source messages</th></tr></thead><tbody>{commitment_rows}</tbody></table></div>
  <div class="conflicts">{conflict_html or '<div class="empty">No scheduling conflicts surfaced.</div>'}</div>
</section>
</div>
<div class="footer">InboxHero keeps untrusted messages visible, irreversible work gated, and commitments traceable to source message IDs.</div>
</main>
<script>
document.querySelectorAll('.search').forEach(function(input) {{
  input.addEventListener('input', function() {{
    const q = input.value.toLowerCase().trim();
    const table = document.getElementById(input.dataset.table);
    table.querySelectorAll('tbody tr').forEach(function(row) {{
      row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
    }});
  }});
}});
</script>
</body></html>"""
    (root / "dashboard.html").write_text(page, encoding="utf-8")
