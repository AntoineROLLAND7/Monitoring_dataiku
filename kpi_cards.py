# html_builder/kpi_cards.py
# Génère les 4 cartes KPI du haut du dashboard


def build_kpi_cards_html(
    distinct_projects: int,
    avg_success_projects: float,
    avg_success_scenarios: float,
    calendar_html: str,
) -> str:
    """
    Retourne le HTML de la grille de 4 cartes KPI.

    Args:
        distinct_projects      : Nombre de projets actifs sur 7 jours
        avg_success_projects   : Taux moyen de succès projets sur 7 jours (%)
        avg_success_scenarios  : Taux moyen de succès scénarios sur 7 jours (%)
        calendar_html          : HTML de la heatmap calendrier 30 jours
    """
    return f"""
    <div class="container">
        <div class="kpi-grid">

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">folder_open</span></div>
                <div class="stat-label" style="margin-right: 10px;"># Projects</div>
                <div class="stat-label2" style="margin-right: 10px;">(last 7 days)</div>
                <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;">
                    <span id="nb-projects">{distinct_projects}</span>
                </div>
            </div>

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">verified</span></div>
                <div class="stat-label" style="margin-right: 10px;">Project Success Rate</div>
                <div class="stat-label2" style="margin-right: 10px;">(last 7 days)</div>
                <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;">
                    <span id="project-rate">{round(avg_success_projects, 1)}%</span>
                </div>
            </div>

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">query_stats</span></div>
                <div class="stat-label" style="margin-right: 10px;">Scenario Success Rate</div>
                <div class="stat-label2" style="margin-right: 10px;">(last 7 days)</div>
                <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;">
                    <span id="scenario-rate">{round(avg_success_scenarios, 1)}%</span>
                </div>
            </div>

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">insights</span></div>
                <span><i class="stats-icon" style="margin-right: 10px;"></i>Last 30 days trend</span>
                {calendar_html}
            </div>

        </div>
    </div>
"""
