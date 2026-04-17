# html_builder/kpi_cards.py
# Génère les cartes KPI du haut du dashboard


def build_kpi_cards_html(
    distinct_projects: int,
    failed_projects_24h: int,
    chronic_projects: int,
    isolated_failures: int,
    avg_success_projects: float,
    avg_success_scenarios: float,
    calendar_html: str,
) -> str:
    """
    Retourne le HTML de la grille de KPIs.

    Ligne 1 (6 colonnes) : # Projects | Failed 24h | Chronic | Isolated | Proj. Success | Scen. Success
    Ligne 2 (pleine largeur) : heatmap 30 jours

    Args:
        distinct_projects    : Nombre de projets actifs sur 7 jours
        failed_projects_24h  : Nombre de projets en échec sur les dernières 24h
        chronic_projects     : Projets avec taux d'échec ≥ 80 % sur 7 jours
        isolated_failures    : Projets avec exactement 1 run FAILED sur 7 jours (taux < 80 %)
        avg_success_projects : Taux moyen de succès projets sur 7 jours (%)
        avg_success_scenarios: Taux moyen de succès scénarios sur 7 jours (%)
        calendar_html        : HTML de la heatmap calendrier 30 jours
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
                <div class="icon-box" style="color: var(--failed);"><span class="material-symbols-outlined">release_alert</span></div>
                <div class="stat-label" style="margin-right: 10px;">Failed Projects</div>
                <div class="stat-label2" style="margin-right: 10px;">(last 24h)</div>
                <div class="stat-value" style="font-size: 2.2rem; font-weight: bold; color: var(--failed);">
                    <span id="nb-failed-projects">{failed_projects_24h}</span>
                </div>
            </div>

            <div class="card">
                <div class="icon-box" style="color: var(--failed);"><span class="material-symbols-outlined">sync_problem</span></div>
                <div class="stat-label" style="margin-right: 10px;">Chronic Failures</div>
                <div class="stat-label2" style="margin-right: 10px;">(≥ 80 % fail rate, 7d)</div>
                <div class="stat-value" style="font-size: 2.2rem; font-weight: bold; color: var(--failed);">
                    <span id="nb-chronic">{chronic_projects}</span>
                </div>
            </div>

            <div class="card">
                <div class="icon-box" style="color: var(--warning);"><span class="material-symbols-outlined">bolt</span></div>
                <div class="stat-label" style="margin-right: 10px;">Isolated Failures</div>
                <div class="stat-label2" style="margin-right: 10px;">(single fail, 7d)</div>
                <div class="stat-value" style="font-size: 2.2rem; font-weight: bold; color: var(--warning);">
                    <span id="nb-isolated">{isolated_failures}</span>
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

            <div class="card kpi-trend-wide">
                <div class="icon-box"><span class="material-symbols-outlined">insights</span></div>
                <span><i class="stats-icon" style="margin-right: 10px;"></i>Last 30 days trend</span>
                {calendar_html}
            </div>

        </div>
    </div>
"""
