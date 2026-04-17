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

    return html
