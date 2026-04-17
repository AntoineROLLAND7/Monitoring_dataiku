# html_builder/kpi_cards.py
# Génère les cartes KPI du haut du dashboard


def build_kpi_cards_html(
    distinct_projects: int,
    failed_projects_24h: int,
    chronic_projects: int,
    isolated_failures: int,
    avg_success_projects: float,
    calendar_html: str,
) -> str:
    """
    Retourne le HTML de la grille de 6 cartes KPI sur une seule ligne.

    Active Projects | Failing Today | Always Failing | One-off Failures | Project Success Rate | 30d Trend
    """
    return f"""
    <div class="container">
        <div class="kpi-grid">

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">folder_open</span></div>
                <div class="stat-label">Active Projects</div>
                <div class="stat-label2">(last 7 days)</div>
                <div class="card-value-wrapper">
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;">
                        <span id="nb-projects">{distinct_projects}</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="icon-box" style="color: var(--failed);"><span class="material-symbols-outlined">release_alert</span></div>
                <div class="stat-label">Failing Today</div>
                <div class="stat-label2">(last 24h)</div>
                <div class="card-value-wrapper">
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold; color: var(--failed);">
                        <span id="nb-failed-projects">{failed_projects_24h}</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="icon-box" style="color: var(--failed);"><span class="material-symbols-outlined">sync_problem</span></div>
                <div class="stat-label">Always Failing</div>
                <div class="stat-label2">(≥ 80 % fail rate, 7d)</div>
                <div class="card-value-wrapper">
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold; color: var(--failed);">
                        <span id="nb-chronic">{chronic_projects}</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="icon-box" style="color: var(--warning);"><span class="material-symbols-outlined">bolt</span></div>
                <div class="stat-label">One-off Failures</div>
                <div class="stat-label2">(single fail, 7d)</div>
                <div class="card-value-wrapper">
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold; color: var(--warning);">
                        <span id="nb-isolated">{isolated_failures}</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">verified</span></div>
                <div class="stat-label">Project Success Rate</div>
                <div class="stat-label2">(last 7 days)</div>
                <div class="card-value-wrapper">
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;">
                        <span id="project-rate">{round(avg_success_projects, 1)}%</span>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="icon-box"><span class="material-symbols-outlined">insights</span></div>
                <span>Last 30 days trend</span>
                {calendar_html}
            </div>

        </div>
    </div>
"""
