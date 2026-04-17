# styles.py
# CSS complet du dashboard, retourné comme chaîne à injecter dans le <head>

CSS = """
<style>
/* --- VARIABLES & BASE --- */
:root {
    --primary: #4f46e5;
    --primary-light: #818cf8;
    --success: #10b981;
    --failed: #f43f5e;
    --warning: #f59e0b;
    --bg: #f4f4f5;
    --card-bg: rgba(255, 255, 255, 0.8);
    --text: #09090b;
    --text-dim: #71717a;
    --border: rgba(228, 228, 231, 0.8);
    --shadow: 0 1px 3px rgba(0,0,0,0.02), 0 1px 2px rgba(0,0,0,0.04);
}

body {
    font-family: 'Inter', sans-serif;
    background-color: var(--bg);
    background-image:
        radial-gradient(at 0% 0%, rgba(79, 70, 229, 0.05) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.05) 0px, transparent 50%);
    color: var(--text);
    margin: 0;
    display: flex;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
}

/* --- LAYOUT --- */
main { flex: 1; padding: 10px 40px 40px; margin-left: 0; }
.container { max-width: 95%; margin: 0 auto; }

.header-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--border);
    padding-bottom: 10px;
}

/* --- TYPOGRAPHY --- */
h1 { font-size: 2.2rem; font-weight: 800; margin: 0; letter-spacing: -1.5px; color: var(--text); }
h1 span { color: var(--primary); font-weight: 300; text-transform: uppercase; font-size: 1.8rem; letter-spacing: 1px; }
.subtitle { margin: 8px 0 0 0; color: var(--text-dim); font-size: 0.95rem; font-weight: 300; }

/* --- BENTO GRID CARDS --- */
.kpi-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 16px; margin-bottom: 30px; }

.card {
    background: var(--card-bg);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 18px 22px 12px;
    box-shadow: var(--shadow);
    display: flex;
    flex-direction: column;
    transition: all 0.2s ease;
}
.card-value-wrapper { flex: 1; display: flex; align-items: center; justify-content: center; }
.card:hover { transform: translateY(-2px); border-color: var(--primary-light); box-shadow: 0 10px 20px rgba(0,0,0,0.03); }

.chart-card, .global-trend-card {
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    position: relative;
    padding: 20px;
    box-shadow: var(--shadow);
}

.icon-box {
    position: absolute; top: 12px; right: 12px;
    background: rgba(0, 0, 0, 0.05); border-radius: 8px;
    width: 32px; height: 32px;
    display: flex; align-items: center; justify-content: center;
}

/* --- SECTION HEADER --- */
.section-topbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; }
.section-topbar .filter-bar { margin-bottom: 0; }
.section-header { display: flex; align-items: center; gap: 12px; }
.section-title  { font-size: 1.5rem; font-weight: 900; color: var(--text); letter-spacing: -0.02em; margin: 0; }
.section-badge  {
    padding: 3px 10px; background: rgba(79,70,229,0.1); color: var(--primary);
    font-size: 0.6rem; font-weight: 900; border-radius: 6px; text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* --- FILTERS --- */
.filter-bar { margin-bottom: 14px; display: flex; gap: 12px; align-items: center; }

.search-wrapper { position: relative; }
.search-wrapper .search-icon {
    position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
    color: #94a3b8; font-size: 1.1rem; pointer-events: none;
}

.row-filter, .search-input, .status-select {
    background: white !important;
    border: 1px solid var(--border);
    color: var(--text);
    padding: 10px 16px;
    border-radius: 10px;
    font-family: 'Inter', sans-serif;
    font-size: 0.9rem;
    outline: none;
    transition: all 0.2s;
}

.search-input {
    background: var(--card-bg) !important;
    padding-left: 38px;
}

.status-select {
    background: var(--card-bg) !important;
    cursor: pointer; min-width: 220px;
    -webkit-appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2318181b' stroke-width='2.5'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19.5 8.25l-7.5 7.5-7.5-7.5' /%3E%3C/svg%3E") !important;
    background-repeat: no-repeat !important;
    background-position: right 12px center !important;
    background-size: 14px !important;
    padding-right: 40px;
}

.row-filter:focus, .search-input:focus, .status-select:focus {
    border-color: var(--primary);
    box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1);
}
.status-select:focus { background-color: #fff !important; }

/* --- DRILL TABLE CARD --- */
.drill-table-card {
    border-radius: 28px; border: 1px solid var(--border); overflow: hidden;
    box-shadow: var(--shadow); background: white;
}

/* --- TABLE HIERARCHY --- */
table { width: 100%; border-collapse: collapse; }
th { text-align: left; color: var(--text-dim); font-size: 0.75rem; padding: 12px; border-bottom: 1px solid var(--border); }

#masterTable thead tr { background: #f8fafc; border-bottom: 1px solid #f1f5f9; }
#masterTable thead th {
    padding: 18px 24px; font-size: 0.6rem; font-weight: 900; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 0.1em;
}

tr[class^="row-l"] { transition: background 0.2s; color: var(--text); }

.row-l1 { cursor: pointer; background: white; border-top: 8px solid var(--bg) !important; }
.row-l1:first-child { border-top: none !important; }
.row-l1:hover { background: #f8fafc !important; }
.row-l1 td { padding: 18px 24px; font-weight: bold; border-bottom: 1px solid var(--border); }

.row-l2 { border-left: 5px solid var(--secondary); display: none; background: #fafafa; }
.row-l2 td { padding: 12px 15px 12px 40px; font-size: 0.95rem; }

.row-l2bis { border-left: 5px solid var(--primary); display: none; }
.row-l2bis td { padding: 10px 15px 10px 80px; font-size: 0.9rem; }

.row-l3, .row-l4 { display: none; border-left: 5px solid #cbd5e1; background: #fcfcfc; }
.row-l3 td { padding: 8px 15px 8px 120px; font-size: 0.85rem; color: var(--text-dim); }
.row-l4 td { padding: 8px 15px 8px 160px; font-size: 0.85rem; color: var(--text-dim); }

/* Status & Badges */
.status {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 4px 12px; border-radius: 999px;
    font-size: 0.65rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em;
}
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.status.success { color: var(--success); background: #ecfdf5; border: 1px solid #a7f3d0; }
.status.success .status-dot { background: var(--success); }
.status.failed  { color: var(--failed);  background: #fef2f2; border: 1px solid #fecaca; }
.status.failed  .status-dot { background: var(--failed); }
.status-critical { color: var(--failed) !important; font-weight: 700; }

/* --- HEATMAPS --- */
.heatmap-container { display: flex; gap: 4px; align-items: center; }
.heat-square { width: 80%; height: 12px; border-radius: 2px; cursor: help; transition: transform 0.1s; border: 1px solid rgba(0,0,0,0.05); }
.heat-square:hover { transform: scale(1.3); }
.heat-square:last-of-type { outline: 1.5px solid var(--primary); outline-offset: 1px; }

.heat-label { font-size: 0.55rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.05em; margin-left: 6px; color: #94a3b8; }
.heat-label.critical { color: var(--failed); }
.heat-label.unstable { color: var(--warning); }
.heat-label.steady   { color: var(--success); }

.heat-success, .heat-perfect  { background-color: var(--success); }
.heat-failed,  .heat-critical { background-color: var(--failed); }
.heat-warning                 { background-color: var(--warning); }
.heat-NA, .heat-empty         { background-color: #e2e8f0; }

/* Calendar */
.calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; width: fit-content; margin: 5px auto; place-items: center; }
.calendar-label { font-size: 0.65rem; color: var(--text-dim); text-align: center; }
.calendar-day { width: 18px; height: 18px; border-radius: 3px; transition: transform 0.2s; cursor: pointer; }
.calendar-day:hover { transform: scale(1.3); z-index: 10; }

/* UI Elements */
.data-badge {
    background: white; border: 1px solid var(--border);
    padding: 8px 16px; border-radius: 50px; font-size: 0.8rem; color: var(--primary);
    display: flex; align-items: center; gap: 10px; box-shadow: var(--shadow);
}
.pulse-dot {
    width: 8px; height: 8px; background-color: var(--success); border-radius: 50%;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%   { box-shadow: 0 0 0 0   rgba(5, 150, 105, 0.4); }
    70%  { box-shadow: 0 0 0 10px rgba(5, 150, 105, 0); }
    100% { box-shadow: 0 0 0 0   rgba(5, 150, 105, 0); }
}

.toggle-icon { font-size: 1.1rem; color: #cbd5e1; transition: transform 0.2s ease, color 0.2s; vertical-align: middle; margin-right: 6px; }
.row-l1:hover .toggle-icon { color: var(--primary); }
.expanded .toggle-icon { transform: rotate(90deg); }
.hidden { display: none !important; }

#chart-tooltip {
    position: fixed; background: white; color: var(--text); padding: 8px 12px; border-radius: 8px;
    font-size: 0.75rem; pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 1000;
    border: 1px solid var(--border); box-shadow: 0 10px 15px rgba(0,0,0,0.1);
}

.stat-label  { font-size: 0.8rem;  font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 2px;  padding-right: 44px; }
.stat-label2 { font-size: 0.6rem;  font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; padding-right: 44px; }

/* --- TABLE FOOTER --- */
.table-footer { background: #f8fafc; border-top: 1px solid #f1f5f9; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
.table-footer-text { font-size: 0.65rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.08em; }

/* --- CALENDAR CUSTOM TOOLTIP --- */
#cal-tt {
    position: fixed; z-index: 9999; pointer-events: none;
    background: white; border: 1px solid var(--border);
    border-radius: 14px; padding: 14px 16px;
    box-shadow: 0 12px 32px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.06);
    min-width: 175px; max-width: 250px;
    opacity: 0; transition: opacity 0.15s ease;
    font-family: 'Inter', sans-serif;
}
.cal-tt-header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
.cal-tt-dot    { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.cal-tt-date   { font-size: 0.78rem; font-weight: 700; color: var(--text); }
.cal-tt-rate   { display: flex; align-items: baseline; gap: 5px; margin-bottom: 10px; }
.cal-tt-rate-val { font-size: 1.5rem; font-weight: 900; color: var(--text); letter-spacing: -0.03em; line-height: 1; }
.cal-tt-rate-lbl { font-size: 0.62rem; font-weight: 600; color: var(--text-dim); text-transform: uppercase; letter-spacing: 0.04em; }
.cal-tt-fails-title {
    font-size: 0.58rem; font-weight: 800; color: var(--text-dim);
    text-transform: uppercase; letter-spacing: 0.08em;
    border-top: 1px solid var(--border); padding-top: 8px; margin-bottom: 5px;
}
.cal-tt-proj {
    display: block; font-size: 0.7rem; font-weight: 600;
    color: var(--failed); padding: 1px 0;
}
</style>
"""


def get_html_head(title: str = "QA Analytics Dashboard") -> str:
    """Retourne le bloc <head> complet avec les fonts et le CSS."""
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;500;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
    {CSS}
</head>"""
