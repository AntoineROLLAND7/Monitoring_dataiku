# =============================================================================
# config.py
# -----------------------------------------------------------------------------
# Fichier de configuration centrale du dashboard de monitoring.
# Toutes les constantes métier, techniques et structurelles sont regroupées ici
# pour faciliter la maintenance : modifier une valeur ici suffit pour l'appliquer
# partout dans le projet, sans avoir à chercher dans le code.
# =============================================================================


# -----------------------------------------------------------------------------
# DATASETS DATAIKU
# -----------------------------------------------------------------------------
# Noms exacts des datasets dans le projet Dataiku.
# Ces datasets sont lus au démarrage par data_loader.py.

DATASET_SCENARIO      = "monitoring_scenario"       # Runs au niveau projet/scénario
DATASET_STEP_SCENARIO = "monitoring_step_scenario"  # Runs au niveau step (étape)


# -----------------------------------------------------------------------------
# EXPORT DATAIKU
# -----------------------------------------------------------------------------
# Nom de l'insight Dataiku dans lequel le dashboard HTML sera publié.
# Visible dans l'onglet "Insights" du projet Dataiku.

INSIGHT_NAME = "Monitoring_view"


# -----------------------------------------------------------------------------
# FENÊTRES TEMPORELLES (en jours)
# -----------------------------------------------------------------------------
# Définissent les périodes d'analyse utilisées dans les calculs et l'affichage.
#   - WINDOW_7_DAYS  : fenêtre courte pour les KPIs et heatmaps du tableau
#   - WINDOW_30_DAYS : fenêtre longue pour la tendance calendrier

WINDOW_7_DAYS  = 7   # Utilisé pour les KPIs et les heatmaps par projet/scénario
WINDOW_30_DAYS = 30  # Utilisé pour la heatmap calendrier globale


# -----------------------------------------------------------------------------
# PROJETS EXCLUS
# -----------------------------------------------------------------------------
# Liste des project_id à ignorer dans tous les calculs.
# Le projet ADMIN est un projet système Dataiku sans valeur métier à monitorer.

EXCLUDED_PROJECTS = ["ADMIN"]


# -----------------------------------------------------------------------------
# NORMALISATION DES STATUTS
# -----------------------------------------------------------------------------
# Dictionnaire de remplacement appliqué sur les colonnes run_status et step_result.
# Permet d'unifier les statuts Dataiku en seulement deux valeurs métier :
#   - FAILED  : toute forme d'échec ou d'interruption
#   - SUCCESS : toute forme de succès, même partiel (WARNING)
#
# Clé   = statut brut retourné par Dataiku
# Valeur = statut normalisé utilisé dans le dashboard

STATUS_NORMALIZE = {
    "ABORTED": "FAILED",   # Run interrompu manuellement → considéré en échec
    "WARNING": "SUCCESS",  # Run en avertissement → considéré en succès
}


# -----------------------------------------------------------------------------
# SEUILS DE SANTÉ (en %)
# -----------------------------------------------------------------------------
# Définissent les niveaux de couleur de la heatmap calendrier 30 jours.
# Le taux calculé est le % de projets ayant eu 100% de runs SUCCESS sur la journée.
#
# Logique d'attribution (dans data_processor.py) :
#   pct == 100                          → "perfect"  (vert)
#   HEALTH_THRESHOLDS["critical"] <= pct < 100  → "warning"  (orange)
#   pct < HEALTH_THRESHOLDS["critical"] → "critical" (rouge)
#
# ⚠️  Ne modifier que la valeur "critical" : le seuil "perfect" est toujours 100%.

HEALTH_THRESHOLDS = {
    "critical": 80,   # En dessous de ce seuil → statut "critical" (rouge)
    # "perfect" est implicitement 100% : tout projet à 100% est vert.
    # "warning" est la zone intermédiaire : entre critical et 100%.
}


# -----------------------------------------------------------------------------
# NOMS DES COLONNES CLÉS
# -----------------------------------------------------------------------------
# Centralisés ici pour éviter les chaînes hardcodées partout dans le code.
# Si le schéma d'un dataset change, il suffit de modifier la valeur ici.

COL_RUN_DATE    = "run_date"    # Date d'exécution du run (parsée depuis run_id pour les steps)
COL_RUN_STATUS  = "run_status"  # Statut global du run (SUCCESS / FAILED après normalisation)
COL_STEP_RESULT = "step_result" # Statut d'une étape individuelle (SUCCESS / FAILED)
COL_PROJECT_ID  = "project_id"  # Identifiant du projet Dataiku
COL_SCENARIO_ID = "scenario_id" # Identifiant du scénario dans le projet
COL_RUN_ID      = "run_id"      # Identifiant unique du run (format : YYYY-MM-DD-HH-MM-SS-ms)
