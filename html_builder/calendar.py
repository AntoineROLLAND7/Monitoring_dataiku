# =============================================================================
# html_builder/calendar.py
# -----------------------------------------------------------------------------
# Génère la heatmap calendrier sur 30 jours affichée dans la 4e carte KPI.
#
# Rendu visuel :
#   - Grille CSS de 7 colonnes (lundi → dimanche)
#   - Chaque case = un jour, colorée selon health_status (perfect/warning/critical)
#   - Tooltip au survol : date, % de succès, liste des projets en échec
#   - Le dernier jour (aujourd'hui) est encadré en violet pour le repérer facilement
# =============================================================================

import pandas as pd


def build_calendar_html(final_df: pd.DataFrame, date_col: str = "date_column") -> str:
    """
    Convertit le DataFrame 30 jours en grille HTML calendrier (7 colonnes = jours de la semaine).

    La grille utilise la classe CSS "calendar-grid" définie dans styles.py, qui applique
    un display:grid à 7 colonnes. Les cases sont colorées via les classes "heat-{status}".

    Alignement :
      On calcule le décalage du premier jour (weekday() : 0=lundi, 6=dimanche)
      et on insère des cases vides au début pour que lundi tombe toujours en colonne 1.

    Args:
        final_df (pd.DataFrame) : DataFrame issu de compute_trend_30d(), contenant
                                   les colonnes : date_column, health_status,
                                   pct_success_projects, list_failed_projects
        date_col (str)          : Nom de la colonne datetime (par défaut "date_column")

    Returns:
        str : Bloc HTML <div class="calendar-grid">...</div> prêt à injecter dans la page.
    """
    df = final_df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col)  # Tri chronologique obligatoire pour l'affichage en grille

    # --- Calcul du décalage initial ---
    # weekday() retourne 0 pour lundi, 6 pour dimanche
    # On insère autant de cases vides que nécessaire pour aligner le premier jour sur le bon jour
    premier_jour   = df[date_col].min()
    decalage_debut = premier_jour.weekday()  # Ex: si le premier jour est mercredi → 2 cases vides

    # Libellés des colonnes (une lettre par jour de la semaine, dans l'ordre lundi-dimanche)
    jours_labels = ["M", "T", "W", "T", "F", "S", "S"]

    html = '<div class="calendar-grid">\n'

    # --- En-tête : libellés des jours de la semaine ---
    for label in jours_labels:
        html += f'    <div class="calendar-label">{label}</div>\n'

    # --- Cases vides pour aligner le premier jour sur la bonne colonne ---
    for _ in range(decalage_debut):
        html += '    <div class="calendar-day empty"></div>\n'

    # --- Cases de données (une par jour du DataFrame) ---
    derniere_date = df[date_col].max()  # Utilisé pour identifier "aujourd'hui"

    for _, row in df.iterrows():
        current_date = row[date_col]

        # Le dernier jour reçoit un outline violet pour indiquer "aujourd'hui"
        style = ""
        if current_date == derniere_date:
            style = ' style="outline: 2px solid var(--primary); outline-offset: 2px;"'

        health_status = row.get("health_status", "empty")
        pct           = round(float(row.get("pct_success_projects", 0)), 1)
        failed_list   = str(row.get("list_failed_projects", "") or "")
        date_label    = current_date.strftime("%A %d %B %Y")

        html += (
            f'    <div class="calendar-day heat-{health_status}" '
            f'data-date="{date_label}" data-pct="{pct}" '
            f'data-status="{health_status}" data-failed="{failed_list}" '
            f'onclick="showCalPopup(this)" '
            f'onmouseenter="showCalTT(this,event)" onmouseleave="hideCalTT()"'
            f'{style}></div>\n'
        )

    html += "</div>\n"

    # Tooltip custom + JS (position: fixed → non clippé par le parent)
    html += """
<div id="cal-tt">
    <div class="cal-tt-header">
        <span class="cal-tt-dot" id="cal-tt-dot"></span>
        <span class="cal-tt-date" id="cal-tt-date"></span>
    </div>
    <div class="cal-tt-rate">
        <span class="cal-tt-rate-val" id="cal-tt-rate"></span>
        <span class="cal-tt-rate-lbl">projects OK</span>
    </div>
    <div id="cal-tt-fails" style="display:none">
        <div class="cal-tt-fails-title">Failed projects</div>
        <div id="cal-tt-fails-list"></div>
    </div>
</div>
<script>
    const _calTT = document.getElementById('cal-tt');
    function showCalTT(el, e) {
        document.getElementById('cal-tt-date').textContent = el.dataset.date;
        document.getElementById('cal-tt-rate').textContent = el.dataset.pct + '%';
        const dot = document.getElementById('cal-tt-dot');
        dot.className = 'cal-tt-dot heat-' + el.dataset.status;
        const projects = el.dataset.failed
            ? el.dataset.failed.split('\\n\u2022').filter(s => s.trim())
            : [];
        const failsSection = document.getElementById('cal-tt-fails');
        if (projects.length) {
            document.getElementById('cal-tt-fails-list').innerHTML =
                projects.map(p => `<span class="cal-tt-proj">${p}</span>`).join('');
            failsSection.style.display = 'block';
        } else {
            failsSection.style.display = 'none';
        }
        _posCalTT(e);
        _calTT.style.opacity = '1';
    }
    function hideCalTT() { _calTT.style.opacity = '0'; }
    function _posCalTT(e) {
        _calTT.style.left = '-9999px';
        _calTT.style.top  = '-9999px';
        const tw = _calTT.offsetWidth  || 190;
        const th = _calTT.offsetHeight || 130;
        const x  = e.clientX + 16;
        const y  = e.clientY - 10;
        _calTT.style.left = (x + tw > window.innerWidth  ? x - tw - 32 : x) + 'px';
        _calTT.style.top  = (y + th > window.innerHeight ? y - th      : y) + 'px';
    }
</script>"""

    # ── Popup modal (clic sur un jour) ───────────────────────────────────────────
    html += """
<div id="cal-popup-overlay" onclick="closeCalPopup()" style="
    display:none; position:fixed; inset:0; z-index:10000;
    background:rgba(9,9,11,0.45); backdrop-filter:blur(3px);
    align-items:center; justify-content:center;">
    <div onclick="event.stopPropagation()" style="
        background:white; border-radius:20px; padding:24px 26px;
        min-width:270px; max-width:400px; max-height:72vh; overflow-y:auto;
        box-shadow:0 28px 64px rgba(0,0,0,0.22); position:relative;
        font-family:'Inter',sans-serif;">
        <button onclick="closeCalPopup()" title="Close" style="
            position:absolute; top:14px; right:16px;
            background:rgba(0,0,0,0.06); border:none; border-radius:6px;
            width:26px; height:26px; font-size:1rem; line-height:1;
            cursor:pointer; color:#71717a; transition:background .15s;"
            onmouseover="this.style.background='rgba(0,0,0,0.12)'"
            onmouseout="this.style.background='rgba(0,0,0,0.06)'">&#x2715;</button>
        <div id="cal-popup-content"></div>
    </div>
</div>

<script>
(function(){
    const COLORS = {
        perfect: {dot:'#10b981', bg:'rgba(16,185,129,.09)',  border:'rgba(16,185,129,.28)', label:'Steady'},
        warning: {dot:'#f59e0b', bg:'rgba(245,158,11,.09)',  border:'rgba(245,158,11,.28)', label:'Unstable'},
        critical:{dot:'#f43f5e', bg:'rgba(244,63,94,.09)',   border:'rgba(244,63,94,.28)',  label:'Critical'},
        empty:   {dot:'#cbd5e1', bg:'rgba(203,213,225,.09)', border:'rgba(203,213,225,.28)','label':'No data'},
    };

    window.showCalPopup = function(el) {
        const status   = el.dataset.status || 'empty';
        const pct      = parseFloat(el.dataset.pct) || 0;
        const date     = el.dataset.date  || '';
        const rawFails = el.dataset.failed || '';
        const c        = COLORS[status] || COLORS.empty;

        // Parse failed project list (séparateur \\n• encodé dans data-failed)
        const projects = rawFails
            .split(/\\n•/)
            .map(s => s.trim())
            .filter(Boolean);

        const pctDisplay = Number.isInteger(pct) ? pct : pct.toFixed(1);

        const projHtml = projects.length
            ? '<div style="font-size:.6rem;font-weight:900;text-transform:uppercase;letter-spacing:.08em;color:#94a3b8;margin:14px 0 8px;">'
              + projects.length + ' Failed project' + (projects.length > 1 ? 's' : '')
              + '</div>'
              + projects.map(p =>
                  '<div style="display:flex;align-items:center;gap:9px;padding:6px 0;border-bottom:1px solid #f1f5f9;">'
                  + '<span style="width:6px;height:6px;border-radius:50%;background:#f43f5e;flex-shrink:0;"></span>'
                  + '<span style="font-size:.78rem;font-weight:600;color:#09090b;">' + p + '</span>'
                  + '</div>'
              ).join('')
            : '<div style="display:flex;align-items:center;gap:8px;margin-top:14px;padding:10px 14px;'
              + 'background:rgba(16,185,129,.08);border-radius:10px;border:1px solid rgba(16,185,129,.2);">'
              + '<span style="font-size:1rem;">✓</span>'
              + '<span style="font-size:.78rem;font-weight:700;color:#10b981;">All projects successful</span>'
              + '</div>';

        document.getElementById('cal-popup-content').innerHTML =
            '<div style="display:flex;align-items:center;gap:9px;margin-bottom:12px;padding-right:24px;">'
          +   '<div style="width:10px;height:10px;border-radius:50%;background:' + c.dot + ';flex-shrink:0;"></div>'
          +   '<span style="font-size:.95rem;font-weight:800;color:#09090b;">' + date + '</span>'
          + '</div>'
          + '<div style="display:flex;align-items:baseline;gap:7px;margin-bottom:10px;">'
          +   '<span style="font-size:2.4rem;font-weight:900;color:#09090b;letter-spacing:-.05em;line-height:1;">' + pctDisplay + '%</span>'
          +   '<span style="font-size:.65rem;font-weight:700;color:#71717a;text-transform:uppercase;letter-spacing:.05em;">projects OK</span>'
          + '</div>'
          + '<span style="display:inline-flex;align-items:center;gap:5px;padding:3px 11px;border-radius:999px;'
          +   'background:' + c.bg + ';border:1px solid ' + c.border + ';">'
          +   '<span style="font-size:.62rem;font-weight:900;color:' + c.dot + ';text-transform:uppercase;letter-spacing:.06em;">' + c.label + '</span>'
          + '</span>'
          + projHtml;

        const overlay = document.getElementById('cal-popup-overlay');
        overlay.style.display = 'flex';
    };

    window.closeCalPopup = function() {
        document.getElementById('cal-popup-overlay').style.display = 'none';
    };

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') closeCalPopup();
    });
})();
</script>"""

    return html
