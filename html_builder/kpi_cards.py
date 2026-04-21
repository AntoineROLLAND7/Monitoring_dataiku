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
                <div class="stat-label">30-Day Trend</div>
                <div class="stat-label2">(health per day)</div>
                <div class="card-value-wrapper">
                    {calendar_html}
                </div>
                <div style="display:flex;justify-content:center;gap:10px;
                            padding-top:6px;margin-top:4px;
                            border-top:1px solid var(--border);">
                    <span style="display:flex;align-items:center;gap:4px;">
                        <span style="width:9px;height:9px;border-radius:2px;
                                     background:var(--success);display:inline-block;flex-shrink:0;"></span>
                        <span style="font-size:0.55rem;font-weight:800;color:var(--success);
                                     text-transform:uppercase;letter-spacing:.04em;">Steady</span>
                    </span>
                    <span style="display:flex;align-items:center;gap:4px;">
                        <span style="width:9px;height:9px;border-radius:2px;
                                     background:var(--warning);display:inline-block;flex-shrink:0;"></span>
                        <span style="font-size:0.55rem;font-weight:800;color:var(--warning);
                                     text-transform:uppercase;letter-spacing:.04em;">Unstable</span>
                    </span>
                    <span style="display:flex;align-items:center;gap:4px;">
                        <span style="width:9px;height:9px;border-radius:2px;
                                     background:var(--failed);display:inline-block;flex-shrink:0;"></span>
                        <span style="font-size:0.55rem;font-weight:800;color:var(--failed);
                                     text-transform:uppercase;letter-spacing:.04em;">Critical</span>
                    </span>
                </div>
            </div>

        </div>

        <div style="display:flex;align-items:center;gap:18px;padding:4px 2px 14px;flex-wrap:wrap;">
            <span style="font-size:0.58rem;font-weight:900;text-transform:uppercase;
                         letter-spacing:.08em;color:#94a3b8;">Legend</span>
            <span style="display:flex;align-items:center;gap:6px;">
                <span style="width:8px;height:8px;border-radius:50%;
                             background:var(--success);display:inline-block;flex-shrink:0;"></span>
                <span style="font-size:0.6rem;font-weight:700;color:var(--success);">Steady — no failures</span>
            </span>
            <span style="display:flex;align-items:center;gap:6px;">
                <span style="width:8px;height:8px;border-radius:50%;
                             background:var(--warning);display:inline-block;flex-shrink:0;"></span>
                <span style="font-size:0.6rem;font-weight:700;color:var(--warning);">Unstable — < 80% error </span>
            </span>
            <span style="display:flex;align-items:center;gap:6px;">
                <span style="width:8px;height:8px;border-radius:50%;
                             background:var(--failed);display:inline-block;flex-shrink:0;"></span>
                <span style="font-size:0.6rem;font-weight:700;color:var(--failed);">Critical — > 80% error</span>
            </span>
        </div>
    </div>
"""