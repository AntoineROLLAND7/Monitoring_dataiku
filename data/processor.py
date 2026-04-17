# =============================================================================
# data_processor.py
# -----------------------------------------------------------------------------
# Cœur métier du dashboard : nettoyage, normalisation et calculs statistiques.
#
# Ce fichier est organisé en 5 étapes séquentielles :
#   1. normalize_statuses  : uniformise les statuts bruts Dataiku
#   2. filter_by_window    : restreint les données à une fenêtre temporelle
#   3. compute_kpis_7d     : calcule les KPIs affichés dans les cartes du haut
#   4. compute_trend_30d   : construit la série temporelle pour la heatmap calendrier
#   5. enrich_steps        : prépare les données de steps pour le tableau drill-down
#
# Aucune génération HTML ici : ce fichier ne produit que des DataFrames et des dicts.
# =============================================================================

import pandas as pd
import numpy as np
from datetime import timedelta

# Imports centralisés depuis config.py pour éviter les magic strings/numbers
from config import (
    STATUS_NORMALIZE,    # Dict de remplacement des statuts bruts
    EXCLUDED_PROJECTS,   # Projets à ignorer (ex: ADMIN)
    WINDOW_7_DAYS,       # Fenêtre courte pour KPIs
    WINDOW_30_DAYS,      # Fenêtre longue pour tendance (non utilisée directement ici)
    HEALTH_THRESHOLDS,   # Seuils pour la colorisation de la heatmap
    COL_RUN_DATE,        # Nom de la colonne date
    COL_RUN_STATUS,      # Nom de la colonne statut de run
    COL_STEP_RESULT,     # Nom de la colonne résultat de step
    COL_PROJECT_ID,      # Nom de la colonne identifiant projet
    COL_RUN_ID,          # Nom de la colonne identifiant run (contient la date encodée)
)


# =============================================================================
# 1. NORMALISATION DES STATUTS
# =============================================================================

def normalize_statuses(df: pd.DataFrame, df_step: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Uniformise les statuts bruts Dataiku en deux valeurs métier : SUCCESS et FAILED.

    Dataiku peut retourner plusieurs variantes de statuts selon la cause d'arrêt :
      - ABORTED : arrêt manuel ou timeout → traité comme FAILED
      - WARNING : succès avec alertes     → traité comme SUCCESS

    La normalisation est appliquée sur trois colonnes :
      - run_status  dans df      (niveau scénario)
      - run_status  dans df_step (niveau step)
      - step_result dans df_step (résultat de l'étape individuelle)

    Args:
        df      : DataFrame des runs scénario (brut, issu de load_raw_data)
        df_step : DataFrame des runs step     (brut, issu de load_raw_data)

    Returns:
        Tuple (df, df_step) avec les statuts normalisés en place.
    """
    # On itère sur le dictionnaire STATUS_NORMALIZE défini dans config.py
    # pour appliquer chaque remplacement (ABORTED→FAILED, WARNING→SUCCESS)
    for old, new in STATUS_NORMALIZE.items():
        # np.where est plus performant que .replace() sur de grands DataFrames
        df[COL_RUN_STATUS]      = np.where(df[COL_RUN_STATUS]      == old, new, df[COL_RUN_STATUS])
        df_step[COL_RUN_STATUS] = np.where(df_step[COL_RUN_STATUS] == old, new, df_step[COL_RUN_STATUS])
        df_step[COL_STEP_RESULT]= np.where(df_step[COL_STEP_RESULT]== old, new, df_step[COL_STEP_RESULT])
    return df, df_step


# =============================================================================
# 2. FILTRAGE PAR FENÊTRE TEMPORELLE
# =============================================================================

def filter_by_window(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """
    Restreint le DataFrame aux N derniers jours et exclut les projets système.

    La date de référence est la date MAX présente dans les données (et non
    la date d'aujourd'hui), ce qui garantit un comportement cohérent même si
    les données ont un léger retard d'ingestion.

    Exemple : si days=7 et que la date max est le 14/04, on garde du 08/04 au 14/04 inclus
              (7 jours → on soustrait days-1 pour inclure le jour de référence).

    Args:
        df   : DataFrame à filtrer (doit contenir COL_RUN_DATE et COL_PROJECT_ID)
        days : Nombre de jours à conserver (ex: 7 ou 30)

    Returns:
        Copie filtrée du DataFrame.
    """
    df = df.copy()

    # Conversion en datetime si la colonne est encore en string (cas fréquent après get_dataframe)
    df[COL_RUN_DATE] = pd.to_datetime(df[COL_RUN_DATE])

    # Date de référence = date la plus récente dans les données (pas forcément aujourd'hui)
    reference_date = df[COL_RUN_DATE].max()

    # On calcule le début de la fenêtre : on soustrait days-1 pour inclure reference_date
    start_date = reference_date - timedelta(days=days - 1)

    # Double condition : fenêtre temporelle ET exclusion des projets système (ex: ADMIN)
    mask = (df[COL_RUN_DATE] >= start_date) & (~df[COL_PROJECT_ID].isin(EXCLUDED_PROJECTS))

    return df[mask].copy()


# =============================================================================
# 3. KPIs SUR 7 JOURS
# =============================================================================

def compute_kpis_7d(df_7d: pd.DataFrame) -> dict:
    """
    Calcule les indicateurs clés de performance (KPIs) affichés dans les cartes du haut.

    Logique métier :
      - Un scénario est en succès si son run_status == 'success'
      - Un projet est en succès pour une journée si TOUS ses scénarios sont en succès ce jour-là
        (logique AND : un seul scénario en échec suffit à faire tomber le projet)

    Les taux sont calculés jour par jour, puis moyennés sur 7 jours pour obtenir
    un indicateur de tendance stable (moins sensible aux pics ponctuels).

    Args:
        df_7d : DataFrame filtré sur les 7 derniers jours (issu de filter_by_window)

    Returns:
        dict avec les clés :
          - distinct_projects      (int)   : nombre de projets actifs sur la période
          - avg_success_scenarios  (float) : taux moyen journalier de succès des scénarios (%)
          - avg_success_projects   (float) : taux moyen journalier de succès des projets (%)
          - daily_stats            (DataFrame) : détail jour par jour
    """
    df_7d = df_7d.copy()

    # Colonne booléenne : True si le run est un succès
    df_7d["is_success"]     = df_7d[COL_RUN_STATUS].str.lower() == "success"
    # Colonne booléenne inverse : True si le run est un échec (utile pour compter les projets en échec)
    df_7d["not_is_success"] = ~df_7d["is_success"]

    # Projets en échec sur les dernières 24h (jour le plus récent dans les données)
    last_day = df_7d[COL_RUN_DATE].dt.date.max()
    df_last_24h = df_7d[df_7d[COL_RUN_DATE].dt.date == last_day]
    failed_projects_24h = int(
        df_last_24h.groupby(COL_PROJECT_ID)["not_is_success"].max().sum()
    )

    daily_stats = df_7d.groupby(df_7d[COL_RUN_DATE].dt.date).agg(
        # Taux de succès des scénarios : moyenne simple (nb succès / nb total runs)
        pct_success_scenarios=("is_success", "mean"),

        # Taux de succès des projets : un projet est "OK" ce jour seulement si tous
        # ses runs sont OK → on utilise .all() par projet, puis .mean() sur les projets
        pct_success_projects=(
            "is_success",
            lambda x: df_7d.loc[x.index].groupby(COL_PROJECT_ID)["is_success"].all().mean(),
        ),

        # Nombre de projets en échec ce jour : au moins un run FAILED dans le projet
        nb_fail_projects=(
            "is_success",
            lambda x: (
                df_7d.loc[x.index].groupby(COL_PROJECT_ID)["not_is_success"].max() == 1
            ).sum(),
        ),
    ).reset_index()

    # Passage en pourcentage (la moyenne de booléens donne une proportion entre 0 et 1)
    daily_stats["pct_success_scenarios"] *= 100
    daily_stats["pct_success_projects"]  *= 100

    return {
        "distinct_projects":     df_7d[COL_PROJECT_ID].nunique(),
        "failed_projects_24h":   failed_projects_24h,
        "avg_success_scenarios": daily_stats["pct_success_scenarios"].mean(),
        "avg_success_projects":  daily_stats["pct_success_projects"].mean(),
        "daily_stats":           daily_stats,  # Conservé pour usage futur (graphiques, etc.)
    }


# =============================================================================
# 4. TENDANCE 30 JOURS (heatmap calendrier)
# =============================================================================

def _get_failed_list(x: pd.DataFrame) -> str:
    """
    Fonction interne (préfixe _ = usage privé) appelée dans le groupby de compute_trend_30d.

    Construit une chaîne HTML listant les projets en échec pour un groupe de lignes (un jour).
    Le séparateur &#10; est un saut de ligne HTML dans les attributs title (tooltip au survol).

    Args:
        x : sous-DataFrame correspondant à un jour (passé automatiquement par groupby.apply)

    Returns:
        Chaîne formatée pour l'attribut HTML title, ex: "&#10;•PROJ_A&#10;•PROJ_B"
    """
    # On filtre les lignes où is_success est False, on récupère les project_id uniques
    failed_ids = x.loc[x["is_success"] == False, COL_PROJECT_ID].unique()
    # &#10; = \n en HTML dans les attributs → affiche une liste à puces dans le tooltip
    return "&#10;•" + "&#10;•".join(failed_ids)


def compute_trend_30d(df_30d: pd.DataFrame) -> pd.DataFrame:
    """
    Construit un DataFrame de 30 lignes (une par jour calendaire) pour la heatmap.

    Pour chaque jour, on calcule :
      - pct_success_projects   : % de projets 100% verts ce jour-là
      - list_failed_projects   : liste HTML des projets en échec (pour tooltip)
      - health_status          : "perfect" / "warning" / "critical" selon les seuils de config
      - week_of_day            : jour de la semaine en lettres (ex: "Monday")

    Points techniques importants :
      - On aligne sur les 30 derniers jours CALENDAIRES (y compris les jours sans run)
      - Les jours sans données sont comblés avec pct=0 et health_status="critical"
      - L'alignement timezone (UTC) est nécessaire pour le merge sans erreur pandas

    Args:
        df_30d : DataFrame filtré sur 30 jours (issu de filter_by_window)

    Returns:
        DataFrame de 30 lignes prêt pour build_calendar_html()
    """
    df_30d = df_30d.copy()

    # Colonne booléenne de succès (True = succès)
    df_30d["is_success"] = df_30d[COL_RUN_STATUS].str.lower() == "success"

    # Agrégation par jour : taux de succès projet + liste des projets en échec
    daily = df_30d.groupby(df_30d[COL_RUN_DATE].dt.date).apply(
        lambda x: pd.Series({
            # Un projet est "OK" ce jour seulement si tous ses runs sont SUCCESS
            "pct_success_projects": x.groupby(COL_PROJECT_ID)["is_success"].all().mean(),
            # Liste des projets ayant au moins un run FAILED ce jour
            "list_failed_projects": _get_failed_list(x),
        })
    ).reset_index()

    # --- Alignement sur le calendrier complet (30 jours, même sans données) ---
    daily["date_column"] = pd.to_datetime(daily[COL_RUN_DATE]).dt.normalize()

    # Référentiel de 30 jours consécutifs jusqu'à aujourd'hui
    date_range  = pd.date_range(end=pd.Timestamp.now().normalize(), periods=30, freq="D")
    template_df = pd.DataFrame({"date_column": date_range})

    # Harmonisation des timezones pour éviter les erreurs de merge pandas
    daily["date_column"]       = daily["date_column"].dt.tz_localize(None).dt.tz_localize("UTC")
    template_df["date_column"] = template_df["date_column"].dt.tz_localize(None).dt.tz_localize("UTC")

    # Merge LEFT pour conserver tous les jours, même ceux sans données
    final_df = pd.merge(template_df, daily, on="date_column", how="left")

    # Jours sans run → pct = 0 (on considère qu'un jour sans donnée est potentiellement critique)
    final_df["pct_success_projects"] = round(final_df["pct_success_projects"] * 100, 1).fillna(0)

    # --- Attribution du statut de santé selon les seuils définis dans config.py ---
    threshold_critical = HEALTH_THRESHOLDS["critical"]  # 80%
    final_df["health_status"] = np.where(
        final_df["pct_success_projects"] == 100,   # Tous les projets OK → perfect (vert)
        "perfect",
        np.where(
            final_df["pct_success_projects"] < threshold_critical,  # < 80% → critical (rouge)
            "critical",
            "warning",  # Entre 80% et 100% → warning (orange)
        ),
    )

    # Nom du jour de la semaine pour un usage éventuel (tri, affichage)
    final_df["week_of_day"] = [
        x.strftime("%A") if pd.notna(x) else "" for x in final_df["date_column"]
    ]

    return final_df


# =============================================================================
# 5. ENRICHISSEMENT DES STEPS (pour le tableau drill-down)
# =============================================================================

def enrich_steps(df_step: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare le DataFrame des steps pour l'affichage dans le tableau hiérarchique.

    Transformations appliquées :
      1. Parse la date/heure depuis le run_id (format : YYYY-MM-DD-HH-MM-SS-ms)
      2. Filtre sur les 7 derniers jours et exclut les projets système
      3. Extrait l'heure d'exécution (HH:MM) et la date du run (YYYY-MM-DD)
      4. Formate le type de step en version lisible (ex: "build_flowitem" → "BUILD")
      5. Construit un libellé court de step (type + nom, tronqué à 30 caractères)
      6. Assigne une catégorie d'erreur selon le type de step qui a échoué

    Args:
        df_step : DataFrame brut des steps (issu de load_raw_data + normalize_statuses)

    Returns:
        DataFrame enrichi prêt à être consommé par build_drill_down_html()
    """
    df_step = df_step.copy()

    # --- 1. Parse de la date depuis le run_id ---
    # Le run_id encode la date/heure de lancement, ex : "2025-04-08-14-30-00-000"
    df_step[COL_RUN_DATE] = pd.to_datetime(df_step[COL_RUN_ID], format="%Y-%m-%d-%H-%M-%S-%f")

    # --- 2. Filtrage temporel (7 jours) ---
    reference_date  = df_step[COL_RUN_DATE].max()
    seven_days_ago  = reference_date - timedelta(days=WINDOW_7_DAYS - 1)
    df_step = df_step[
        (df_step[COL_RUN_DATE] >= seven_days_ago)
        & (~df_step[COL_PROJECT_ID].isin(EXCLUDED_PROJECTS))
    ].copy()

    # --- 3. Extraction de l'heure et de la date depuis le run_id (string brut) ---
    # On reparse depuis la chaîne run_id pour éviter les problèmes de timezone
    df_step["heure_exec"] = [x[11:16].replace("-", ":") for x in df_step[COL_RUN_ID]]  # ex: "14:30"
    df_step["run_exec"]   = [x[0:10]                    for x in df_step[COL_RUN_ID]]  # ex: "2025-04-08"

    # --- 4. Formatage du type de step ---
    # Dataiku retourne des types comme "build_flowitem_recipe" → on nettoie pour l'affichage
    df_step["step_type"] = [
        x.replace("_", " ").upper().replace("FLOWITEM", "").strip()
        for x in df_step["step_type"]
    ]

    # --- 5. Libellé complet et version courte (pour affichage dans le tableau) ---
    df_step["step_name_complete"] = df_step["step_type"] + " " + df_step["step_name"]
    df_step["step_id_short"]      = [x[0:30] for x in df_step["step_name_complete"]]  # Tronqué à 30 chars

    # --- 6. Catégorie d'erreur selon le type de step ---
    # Permet d'afficher un message d'erreur contextualisé dans la colonne "Info / Error"
    # Chaque type de step en échec reçoit une catégorie différente pour faciliter le triage
    error_map = {
        "COMPUTE METRICS": "Compute Metrics Error",  # Erreur de calcul de métriques DSS
        "CHECK DATASET":   "Dataset Metrics Error",  # Contrôle qualité de dataset échoué
        "EXEC SQL":        "BigQuery Error",          # Requête SQL BigQuery en erreur
        "CUSTOM PYTHON":   "Python Error",            # Script Python personnalisé en erreur
    }

    df_step["error_category"] = np.nan  # Valeur par défaut (steps en succès ou type non mappé)
    for step_type, error_label in error_map.items():
        # On n'assigne la catégorie que si le step a FAILED (pas de catégorie d'erreur si succès)
        mask = (df_step["step_type"] == step_type) & (df_step[COL_STEP_RESULT] == "FAILED")
        df_step.loc[mask, "error_category"] = error_label

    return df_step
