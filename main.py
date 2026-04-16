# =============================================================================
# main.py
# -----------------------------------------------------------------------------
# Point d'entrée du dashboard de monitoring.
#
# Ce fichier orchestre l'ensemble du pipeline en appelant les modules dans l'ordre :
#
#   [data_loader]      → chargement brut depuis Dataiku
#       ↓
#   [data_processor]   → nettoyage, normalisation, calculs métier
#       ↓
#   [html_builder/*]   → assemblage des composants HTML
#       ↓
#   [dataiku.insights] → export en base64 vers l'interface Dataiku
#
# Pour exécuter : lancer ce fichier comme recipe Python dans Dataiku,
# ou en ligne de commande : python main.py
# =============================================================================

import base64               # Encodage du HTML en base64 pour l'export Dataiku
from datetime import datetime  # Pour afficher la date du jour dans le header

import dataiku.insights     # API Dataiku pour publier un insight HTML

# --- Configuration ---
from config import INSIGHT_NAME  # Nom de l'insight cible dans Dataiku

# --- Chargement des données ---
from data.loader import load_raw_data  # Lecture des datasets Dataiku

# --- Traitement métier ---
from data.processor import (
    normalize_statuses,   # Uniformise ABORTED/WARNING en FAILED/SUCCESS
    filter_by_window,     # Restreint aux N derniers jours
    compute_kpis_7d,      # Calcule les indicateurs pour les cartes KPI
    compute_trend_30d,    # Prépare la série journalière pour la heatmap
    enrich_steps,         # Enrichit les steps pour le tableau drill-down
)

# --- Génération HTML ---
from html_builder.styles import get_html_head                 # <head> + CSS complet
from html_builder.header import build_header_html             # Bandeau titre + badge date
from html_builder.kpi_cards import build_kpi_cards_html       # 4 cartes KPI du haut
from html_builder.calendar import build_calendar_html         # Heatmap calendrier 30 jours
from html_builder.drill_down_table import (
    build_drill_down_html,  # Tableau hiérarchique 5 niveaux + filtres
    JAVASCRIPT,             # Code JS (accordéon + filtres) à injecter en fin de body
)


# =============================================================================
# PIPELINE PRINCIPAL
# =============================================================================

def build_dashboard() -> str:
    """
    Orchestre le pipeline complet et retourne le HTML final du dashboard.

    Étapes :
      1. Chargement brut (data_loader)
      2. Normalisation des statuts
      3. Filtrage sur 7j (KPIs + steps) et 30j (heatmap calendrier)
      4. Calcul des KPIs agrégés
      5. Construction de la tendance 30 jours
      6. Enrichissement des steps pour le drill-down
      7. Assemblage séquentiel des composants HTML

    Returns:
        str : Document HTML complet, auto-suffisant (CSS et JS inclus inline).
    """

    # --- Étape 1 : Chargement ---
    # On récupère les deux DataFrames bruts depuis Dataiku
    df_raw, df_step_raw = load_raw_data()

    # --- Étape 2 : Normalisation ---
    # ABORTED → FAILED, WARNING → SUCCESS (sur les deux DataFrames, trois colonnes)
    df, df_step = normalize_statuses(df_raw, df_step_raw)

    # --- Étape 3 : Filtrage temporel ---
    # On crée deux vues temporelles différentes à partir du même DataFrame normalisé
    df_7d  = filter_by_window(df, days=7)   # Pour les KPIs et heatmaps par projet
    df_30d = filter_by_window(df, days=30)  # Pour la heatmap calendrier globale

    # --- Étape 4 : KPIs 7 jours ---
    # Retourne un dict avec les taux de succès et le nombre de projets actifs
    kpis = compute_kpis_7d(df_7d)

    # --- Étape 5 : Tendance 30 jours ---
    # DataFrame de 30 lignes avec health_status et pct_success_projects par jour
    trend_30d = compute_trend_30d(df_30d)

    # --- Étape 6 : Enrichissement des steps ---
    # Ajout des colonnes heure_exec, run_exec, step_id_short, error_category, etc.
    df_steps_enriched = enrich_steps(df_step)

    # --- Étape 7 : Assemblage HTML ---
    # Date du jour formatée pour le badge dans le header (ex: "April 14, 2025")
    date_str = datetime.today().strftime("%B %d, %Y")

    # La heatmap calendrier est construite séparément pour être injectée dans la carte KPI
    calendar_html = build_calendar_html(trend_30d)

    # Assemblage séquentiel des blocs HTML dans l'ordre d'affichage
    html  = get_html_head()                          # <!DOCTYPE html> ... <head> ... </head>
    html += "<body>\n"
    html += build_header_html(date_str)              # Bandeau titre + badge date
    html += build_kpi_cards_html(                    # Grille des 4 cartes KPI
        distinct_projects    = kpis["distinct_projects"],
        avg_success_projects = kpis["avg_success_projects"],
        avg_success_scenarios= kpis["avg_success_scenarios"],
        calendar_html        = calendar_html,        # Heatmap injectée dans la 4e carte
    )
    html += build_drill_down_html(df_steps_enriched) # Filtres + tableau hiérarchique
    html += "\n    </main>\n"
    html += JAVASCRIPT                               # JS accordéon + filtrage (fin de body)
    html += "\n</body>\n</html>"

    return html


# =============================================================================
# EXPORT VERS DATAIKU
# =============================================================================

def export_to_dataiku(html_content: str) -> None:
    """
    Encode le HTML en base64 et le publie comme insight dans Dataiku.

    Dataiku Insights permet d'afficher du contenu HTML personnalisé directement
    dans l'interface du projet, accessible depuis l'onglet "Insights".

    L'encodage base64 est requis par l'API dataiku.insights.save_data pour
    les contenus de type text/html.

    Args:
        html_content : Chaîne HTML complète retournée par build_dashboard()
    """
    # Encodage UTF-8 → bytes → base64
    encoded = base64.b64encode(html_content.encode("utf-8"))

    dataiku.insights.save_data(
        INSIGHT_NAME,           # Nom de l'insight dans Dataiku (défini dans config.py)
        payload=encoded,        # Contenu encodé en base64
        content_type="text/html",
        label=None,             # Pas de label additionnel
        encoding="base64",      # Indique à Dataiku de décoder avant affichage
    )
    print(f"✅ Dashboard exporté avec succès : {INSIGHT_NAME}")


# =============================================================================
# EXÉCUTION
# =============================================================================

if __name__ == "__main__":
    # Point d'entrée unique : construire puis exporter
    html_content = build_dashboard()
    export_to_dataiku(html_content)
