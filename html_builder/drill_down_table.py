# =============================================================================
# html_builder/drill_down_table.py
# -----------------------------------------------------------------------------
# Génère le tableau hiérarchique drill-down à 5 niveaux et le JavaScript associé.
#
# Structure du tableau (chaque niveau est une <tr> avec une classe CSS dédiée) :
#   L1      → Projet        (row-l1)   : statut global + heatmap 7j
#   L2      → Scénario      (row-l2)   : statut global + heatmap 7j
#   L2bis   → Date du run   (row-l2bis): lien vers les logs Dataiku
#   L3      → Heure d'exec  (row-l3)   : lien vers les logs Dataiku
#   L4      → Step individuel(row-l4)  : résultat + catégorie d'erreur
#
# Le JavaScript (constante JAVASCRIPT) gère :
#   - L'accordéon imbriqué (clic sur une ligne → affiche/masque les enfants)
#   - Le filtrage par nom de projet et par statut (all/success/failed/critical-trend)
# =============================================================================

import pandas as pd
import numpy as np
from datetime import timedelta


# =============================================================================
# FONCTIONS HELPERS (privées, usage interne uniquement)
# =============================================================================

def _build_heatmap_squares(
    df_subset: pd.DataFrame,
    date_range: pd.DatetimeIndex,
    date_col: str = "date_column"
) -> tuple:
    """
    Génère les 7 carrés HTML de la heatmap pour un projet ou un scénario,
    ainsi qu'un label de stabilité basé sur les échecs récents.

    Returns:
        tuple[str, tuple[str, str]] : (squares_html, (label_text, label_css_class))
    """
    summary_df = df_subset.groupby(date_col)["run_status"].agg(
        lambda x: "failed" if (x == "FAILED").any() else "success"
    ).reset_index()

    template_df = pd.DataFrame({date_col: date_range})
    final_df    = pd.merge(template_df, summary_df, on=date_col, how="left")
    final_df["run_status"] = final_df["run_status"].fillna("NA")

    statuses = final_df["run_status"].tolist()

    squares = []
    for _, row in final_df.iterrows():
        date_str = row[date_col].date() if hasattr(row[date_col], "date") else row[date_col]
        squares.append(
            f'<div class="heat-square heat-{row.run_status}" '
            f'title="{date_str}: {row.run_status}"></div>'
        )
    squares_html = "\n".join(squares)

    # Label de stabilité basé sur les 2 derniers jours actifs
    recent = [s for s in statuses[-2:] if s != "NA"]
    if recent and any(s == "failed" for s in recent):
        stability = ("Critical", "critical")
    elif any(s == "failed" for s in statuses):
        stability = ("Unstable", "unstable")
    else:
        stability = ("Steady", "steady")

    return squares_html, stability


def _heatmap_wrapper(squares_html: str, stability: tuple) -> str:
    """
    Encapsule les carrés de heatmap dans le conteneur HTML avec un label de stabilité.

    Args:
        squares_html : Chaîne HTML des 7 carrés (retournée par _build_heatmap_squares)
        stability    : Tuple (label_text, css_class) ex: ("Steady", "steady")

    Returns:
        str : Bloc HTML complet de la heatmap pour insertion dans la cellule du tableau
    """
    label_text, label_cls = stability
    return f"""
        <div class="heatmap-container">
            {squares_html}
            <span class="heat-label {label_cls}">{label_text}</span>
        </div>"""


# =============================================================================
# GÉNÉRATION DES LIGNES HTML (5 niveaux imbriqués)
# =============================================================================

def build_table_rows_html(df: pd.DataFrame) -> str:
    """
    Parcourt le DataFrame de steps enrichi et génère toutes les lignes <tr> du tableau.

    Les lignes sont générées dans l'ordre hiérarchique : pour chaque projet, on génère
    ses scénarios ; pour chaque scénario ses dates de run ; etc.
    Toutes les lignes filles (L2, L2bis, L3, L4) ont display:none par défaut et sont
    révélées par le JavaScript au clic sur la ligne parente.

    Statut d'un projet  : "failed" si au moins un run_id est FAILED sur la période
    Statut d'un scénario: "failed" si au moins un run_status == "FAILED" dans le groupe
    Statut d'un run_exec: min alphabétique ("FAILED" < "SUCCESS") → FAILED l'emporte

    Args:
        df : DataFrame enrichi issu de enrich_steps() dans data_processor.py

    Returns:
        str : Toutes les lignes <tr> concaténées, prêtes pour insertion dans <tbody>
    """
    # Référentiel de 7 jours calendaires pour les heatmaps (se termine aujourd'hui)
    today      = pd.Timestamp.now().normalize()
    date_range = pd.date_range(end=today, periods=7, freq="D")

    html_rows = []

    # =========================================================================
    # NIVEAU 1 : PROJET
    # =========================================================================
    for project_id, project_df in df.groupby("project_id", sort=False):
        project_df = project_df.copy()
        # Normalisation de la date pour le merge avec date_range (date sans heure)
        project_df["date_column"] = pd.to_datetime(project_df["run_exec"]).dt.normalize()

        # Un projet est "failed" s'il a au moins un run_id avec statut FAILED
        failed_runs = project_df[project_df["run_status"] == "FAILED"]["run_id"].nunique()
        proj_status = "failed" if failed_runs > 0 else "success"

        # Heatmap 7 jours du projet
        squares, stability = _build_heatmap_squares(project_df, date_range)
        heatmap = _heatmap_wrapper(squares, stability)

        html_rows.append(f"""
    <tr class="row-l1" data-status="{proj_status}" onclick="toggleRow(this, 'row-l2')">
        <td><span class="material-symbols-outlined toggle-icon">chevron_right</span> <strong>{project_id}</strong></td>
        <td>---</td>
        <td><span class="status {proj_status}"><span class="status-dot"></span>{proj_status.capitalize()}</span></td>
        <td>{heatmap}</td>
    </tr>""")

        # =====================================================================
        # NIVEAU 2 : SCÉNARIO
        # =====================================================================
        for scenario_id, scenario_df in project_df.groupby("scenario_id", sort=False):
            scen_status = "failed" if (scenario_df["run_status"] == "FAILED").any() else "success"
            squares_s, stability_s = _build_heatmap_squares(scenario_df, date_range)
            heatmap_s = _heatmap_wrapper(squares_s, stability_s)

            html_rows.append(f"""
        <tr class="row-l2" data-status="{scen_status}" onclick="toggleRow(this, 'row-l2bis')">
            <td style="padding-left: 40px;"><span class="material-symbols-outlined toggle-icon">chevron_right</span> {scenario_id}</td>
            <td>---</td>
            <td><span class="status {scen_status}"><span class="status-dot"></span>{scen_status.capitalize()}</span></td>
            <td>{heatmap_s}</td>
        </tr>""")

            # Tri anti-chronologique : runs les plus récents en premier
            scenario_df = scenario_df.sort_values("run_exec", ascending=False)

            # =================================================================
            # NIVEAU 2bis : DATE DU RUN (run_exec = YYYY-MM-DD)
            # =================================================================
            for run_exec, run_df in scenario_df.groupby("run_exec", sort=False):
                # min() alphabétique : "FAILED" < "SUCCESS" → si un step est FAILED, run = failed
                run_status = run_df["run_status"].min().lower()
                # Transformation de l'URL Dataiku : /settings → /runs/list pour accéder aux logs
                log_link   = run_df["scenario_link"].iloc[0].replace("settings", "runs/list")

                html_rows.append(f"""
            <tr class="row-l2bis" data-status="{run_status}" onclick="toggleRow(this, 'row-l3')">
                <td style="padding-left: 80px;"><span class="material-symbols-outlined toggle-icon">chevron_right</span> {run_exec}</td>
                <td>-</td>
                <td><span class="status {run_status}"><span class="status-dot"></span>{run_status.capitalize()}</span></td>
                <td><a href="{log_link}" target="_blank" style="color:var(--primary)">🔗 Logs (right click + Open)</a></td>
            </tr>""")

                # Tri chronologique des exécutions dans la même journée
                run_df = run_df.sort_values("heure_exec", ascending=True)

                # =============================================================
                # NIVEAU 3 : HEURE D'EXÉCUTION (heure_exec = HH:MM)
                # =============================================================
                for heure_exec, exec_df in run_df.groupby("heure_exec", sort=False):
                    exec_status   = exec_df["run_status"].min().lower()
                    log_link_exec = exec_df["scenario_link"].iloc[0].replace("settings", "runs/list")

                    html_rows.append(f"""
                <tr class="row-l3" data-status="{exec_status}" onclick="toggleRow(this, 'row-l4')">
                    <td style="padding-left: 120px;"><span class="material-symbols-outlined toggle-icon">chevron_right</span> Execution of {heure_exec}</td>
                    <td>{heure_exec}</td>
                    <td><span class="status {exec_status}"><span class="status-dot"></span>{exec_status.capitalize()}</span></td>
                    <td><a href="{log_link_exec}" target="_blank" style="color:var(--primary)">Logs (right click + Open)</a></td>
                </tr>""")

                    # Tri par ordre d'exécution des steps (step_order = indice dans le scénario)
                    exec_df = exec_df.sort_values("step_order", ascending=True)

                    # =========================================================
                    # NIVEAU 4 : STEP INDIVIDUEL
                    # =========================================================
                    for _, step in exec_df.iterrows():
                        # Résultat du step : on recompare la valeur brute pour être robuste
                        step_res     = "success" if step["step_result"].upper() == "SUCCESS" else "failed"
                        # error_category est NaN pour les steps en succès → on affiche rien
                        error_detail = step["error_category"] if pd.notna(step.get("error_category")) else ""

                        # └ est un caractère Unicode pour représenter visuellement la hiérarchie
                        html_rows.append(f"""
                    <tr class="row-l4">
                        <td style="padding-left: 160px; font-size: 0.9em;">└ {step['step_id_short']}</td>
                        <td>-</td>
                        <td><span class="status {step_res}">{step_res}</span></td>
                        <td>{error_detail}</td>
                    </tr>""")

    return "\n".join(html_rows)


# =============================================================================
# ASSEMBLAGE DU BLOC FILTRES + TABLEAU
# =============================================================================

def build_drill_down_html(df: pd.DataFrame) -> str:
    """
    Assemble le bloc HTML complet : barre de filtres + tableau hiérarchique.

    Les filtres disponibles :
      - Recherche texte sur le nom du projet (filtre en temps réel via onkeyup)
      - Filtre statut : All / Success / Failed / critical-trend (échec hier ou aujourd'hui)

    Args:
        df : DataFrame enrichi issu de enrich_steps()

    Returns:
        str : HTML complet du bloc filtres + tableau, à insérer dans le body
    """
    from config import COL_PROJECT_ID
    n_projects = df[COL_PROJECT_ID].nunique()
    rows_html  = build_table_rows_html(df)

    return f"""
    <div class="container">

        <!-- Section header + filtres sur la même ligne -->
        <div class="section-topbar">
            <div class="section-header">
                <h2 class="section-title">Project Execution Log</h2>
            </div>
            <div class="filter-bar">
                <div class="search-wrapper">
                    <span class="material-symbols-outlined search-icon">search</span>
                    <input type="text" id="projSearch" class="search-input"
                           placeholder="Search project..." onkeyup="filterData()">
                </div>
                <select id="statusFilter" class="status-select" onchange="filterData()">
                    <option value="all">All Status</option>
                    <option value="success">Success</option>
                    <option value="failed">Failed</option>
                    <option value="critical-trend">⚠️ Today's &amp; yesterday's failures</option>
                </select>
            </div>
        </div>

        <!-- Tableau principal -->
        <div class="drill-table-card">
            <table id="masterTable">
                <thead>
                    <tr>
                        <th>Identify / Scope</th>
                        <th>Reference Date</th>
                        <th>Health State</th>
                        <th>7D Performance Matrix</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            <div class="table-footer">
                <span class="table-footer-text">Showing {n_projects} active projects</span>
            </div>
        </div>
    </div>
"""


# =============================================================================
# JAVASCRIPT : ACCORDÉON + FILTRES
# =============================================================================
# Injecté en fin de <body> dans main.py via la constante JAVASCRIPT.
# Les fonctions sont globales (pas de module ES6) pour être accessibles
# depuis les attributs onclick des lignes générées dynamiquement en Python.

JAVASCRIPT = """
<script>
    /**
     * filterData()
     * Filtre les lignes L1 (projets) selon la recherche textuelle et le statut sélectionné.
     * Les lignes L2+ des projets masqués sont également cachées pour éviter les artefacts visuels.
     *
     * Filtre "critical-trend" : vérifie les deux derniers carrés de la heatmap du projet
     * (heatSquares[lastIndex] = aujourd'hui, heatSquares[lastIndex-1] = hier)
     */
    function filterData() {
        const searchTerm   = document.getElementById('projSearch').value.toLowerCase();
        const statusFilter = document.getElementById('statusFilter').value;
        const rows         = document.querySelectorAll('#masterTable tbody .row-l1');

        rows.forEach(row => {
            const projectName   = row.querySelector('td').textContent.toLowerCase();
            const projectStatus = row.getAttribute('data-status');

            // Lecture des carrés de heatmap pour le filtre "critical-trend"
            const heatSquares    = row.querySelectorAll('.heat-square');
            const lastIndex      = heatSquares.length - 1;
            const failedToday    = heatSquares[lastIndex]?.classList.contains('heat-failed');
            const failedYesterday= heatSquares[lastIndex - 1]?.classList.contains('heat-failed');

            const matchesSearch = projectName.includes(searchTerm);
            let   matchesStatus = false;

            if (statusFilter === 'all') {
                matchesStatus = true;                             // Pas de filtre statut
            } else if (statusFilter === 'critical-trend') {
                matchesStatus = failedToday || failedYesterday;  // Échec récent (hier ou aujourd'hui)
            } else {
                matchesStatus = (projectStatus === statusFilter); // Filtre exact success/failed
            }

            if (matchesSearch && matchesStatus) {
                row.style.display = "";  // Affiche la ligne projet
            } else {
                row.style.display = "none";
                // Masque également toutes les lignes enfants (L2, L2bis, L3, L4)
                getNextRows(row).forEach(r => r.style.display = "none");
                row.classList.remove('expanded');
            }
        });
    }

    /**
     * getNextRows(row)
     * Retourne toutes les lignes situées après `row` jusqu'à la prochaine ligne L1.
     * Utilisé pour masquer les enfants d'un projet filtré.
     */
    function getNextRows(row) {
        let nextRows = [];
        let next = row.nextElementSibling;
        while (next && !next.classList.contains('row-l1')) {
            nextRows.push(next);
            next = next.nextElementSibling;
        }
        return nextRows;
    }

    /**
     * toggleRow(row, targetClass)
     * Gère l'accordéon : affiche ou masque les lignes enfants immédiates (targetClass).
     * Les niveaux plus profonds restent masqués jusqu'à un nouveau clic.
     *
     * Algorithme :
     *   1. Toggle la classe "expanded" sur la ligne cliquée (pour rotation de la flèche ▶)
     *   2. Parcourt les siblings suivants jusqu'à une ligne de niveau égal ou supérieur
     *   3. Affiche ou masque uniquement les lignes de `targetClass`
     *   4. Si on ferme, appelle closeChildren() récursivement pour fermer tous les sous-niveaux
     */
    function toggleRow(row, targetClass) {
        row.classList.toggle('expanded');
        let next         = row.nextElementSibling;
        const currentLevel = row.classList[0];

        while (next) {
            if (isSameOrHigherLevel(currentLevel, next)) break; // Fin de la section courante
            if (next.classList.contains(targetClass)) {
                // Affiche si expanded, masque sinon
                next.style.display = row.classList.contains('expanded') ? 'table-row' : 'none';
                if (!row.classList.contains('expanded')) {
                    next.classList.remove('expanded');
                    closeChildren(next); // Fermeture récursive des sous-niveaux ouverts
                }
            }
            next = next.nextElementSibling;
        }
    }

    /**
     * closeChildren(row)
     * Ferme récursivement tous les niveaux enfants d'une ligne (utilisé lors du collapse).
     */
    function closeChildren(row) {
        let next           = row.nextElementSibling;
        const currentLevel = row.classList[0];
        while (next) {
            if (isSameOrHigherLevel(currentLevel, next)) break;
            next.style.display = 'none';
            next.classList.remove('expanded');
            next = next.nextElementSibling;
        }
    }

    /**
     * isSameOrHigherLevel(currentLevel, nextRow)
     * Retourne true si nextRow est au même niveau ou à un niveau parent que currentLevel.
     * Utilisé comme condition d'arrêt pour les parcours de siblings.
     *
     * Hiérarchie des niveaux (du plus haut au plus bas) :
     *   row-l1 > row-l2 > row-l2bis > row-l3 > row-l4
     */
    function isSameOrHigherLevel(currentLevel, nextRow) {
        const levels       = ['row-l1', 'row-l2', 'row-l2bis', 'row-l3', 'row-l4'];
        const currentIndex = levels.indexOf(currentLevel);
        // Si nextRow a une classe de niveau <= currentIndex → on s'arrête
        return levels.some((level, index) =>
            index <= currentIndex && nextRow.classList.contains(level)
        );
    }

    /**
     * checkSuccessRates()
     * Colorie en rouge les KPIs de taux de succès inférieurs à 100%.
     * Appelée une seule fois au chargement de la page.
     */
    function checkSuccessRates() {
        ['project-rate', 'scenario-rate'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                const value = parseFloat(el.textContent);
                // Ajoute/retire la classe CSS "status-critical" (rouge) selon le seuil
                el.classList.toggle('status-critical', value < 100);
            }
        });
    }

    // Exécution au chargement de la page
    checkSuccessRates();
</script>
"""
