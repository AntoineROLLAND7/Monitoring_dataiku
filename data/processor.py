# =============================================================================
# data_processor.py
# -----------------------------------------------------------------------------
# Cœur métier du dashboard : nettoyage, normalisation et calculs statistiques.
#
# Ce fichier est organisé en 6 étapes séquentielles :
#   1. normalize_statuses    : uniformise les statuts bruts Dataiku
#   2. filter_by_window      : restreint les données à une fenêtre temporelle
#   3. compute_kpis_7d       : calcule les KPIs affichés dans les cartes du haut
#   4. compute_trend_30d     : construit la série temporelle pour la heatmap calendrier
#   5. compute_heatmap_7d    : pré-agrège les heatmaps 7j par projet et scénario
#   6. enrich_steps          : prépare les données de steps pour le tableau drill-down
#   7. prepare_timeline_data : prépare les données pour le graphique Gantt
#
# Aucune génération HTML ici : ce fichier ne produit que des DataFrames et des dicts.
# =============================================================================

import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Tuple

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

# Seuil "critical" lu depuis config (80% par défaut).
# Le seuil "perfect" est toujours 100% (implicite).
_THRESHOLD_CRITICAL = HEALTH_THRESHOLDS["critical"]


# =============================================================================
# 1. NORMALISATION DES STATUTS
# =============================================================================

def normalize_statuses(df: pd.DataFrame, df_step: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
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
    for old, new in STATUS_NORMALIZE.items():
        df[COL_RUN_STATUS]       = np.where(df[COL_RUN_STATUS]       == old, new, df[COL_RUN_STATUS])
        df_step[COL_RUN_STATUS]  = np.where(df_step[COL_RUN_STATUS]  == old, new, df_step[COL_RUN_STATUS])
        df_step[COL_STEP_RESULT] = np.where(df_step[COL_STEP_RESULT] == old, new, df_step[COL_STEP_RESULT])
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
    df[COL_RUN_DATE] = pd.to_datetime(df[COL_RUN_DATE])
    reference_date   = df[COL_RUN_DATE].max()
    start_date       = reference_date - timedelta(days=days - 1)
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
          - failed_projects_24h    (int)   : projets en échec sur le dernier jour
          - chronic_projects       (int)   : projets avec ≥ 80% de runs en échec
          - isolated_failures      (int)   : projets avec exactement 1 run en échec
          - avg_success_scenarios  (float) : taux moyen journalier de succès des scénarios (%)
          - avg_success_projects   (float) : taux moyen journalier de succès des projets (%)
          - daily_stats            (DataFrame) : détail jour par jour
    """
    df_7d = df_7d.copy()

    df_7d["is_success"]     = df_7d[COL_RUN_STATUS].str.lower() == "success"
    df_7d["not_is_success"] = ~df_7d["is_success"]

    # Projets en échec sur les dernières 24h (jour le plus récent dans les données)
    last_day        = df_7d[COL_RUN_DATE].dt.date.max()
    df_last_24h     = df_7d[df_7d[COL_RUN_DATE].dt.date == last_day]
    failed_projects_24h = int(
        df_last_24h.groupby(COL_PROJECT_ID)["not_is_success"].max().sum()
    )

    # Chronic vs isolated
    failed_per_proj = (
        df_7d[df_7d[COL_RUN_STATUS] == "FAILED"]
        .groupby(COL_PROJECT_ID)[COL_RUN_ID].nunique()
    )
    total_per_proj  = df_7d.groupby(COL_PROJECT_ID)[COL_RUN_ID].nunique()
    failure_rate    = (failed_per_proj / total_per_proj).fillna(0)

    chronic_projects  = int((failure_rate >= 0.8).sum())
    isolated_failures = int(((failed_per_proj == 1) & (failure_rate < 0.8)).sum())

    daily_stats = df_7d.groupby(df_7d[COL_RUN_DATE].dt.date).agg(
        pct_success_scenarios=("is_success", "mean"),
        pct_success_projects=(
            "is_success",
            lambda x: df_7d.loc[x.index].groupby(COL_PROJECT_ID)["is_success"].all().mean(),
        ),
        nb_fail_projects=(
            "is_success",
            lambda x: (
                df_7d.loc[x.index].groupby(COL_PROJECT_ID)["not_is_success"].max() == 1
            ).sum(),
        ),
    ).reset_index()

    daily_stats["pct_success_scenarios"] *= 100
    daily_stats["pct_success_projects"]  *= 100

    return {
        "distinct_projects":     df_7d[COL_PROJECT_ID].nunique(),
        "failed_projects_24h":   failed_projects_24h,
        "chronic_projects":      chronic_projects,
        "isolated_failures":     isolated_failures,
        "avg_success_scenarios": daily_stats["pct_success_scenarios"].mean(),
        "avg_success_projects":  daily_stats["pct_success_projects"].mean(),
        "daily_stats":           daily_stats,
    }


# =============================================================================
# 4. TENDANCE 30 JOURS (heatmap calendrier)
# =============================================================================

def _get_failed_list(x: pd.DataFrame) -> str:
    """
    Construit une chaîne listant les projets en échec pour un groupe de lignes (un jour).
    Utilisée en interne par compute_trend_30d().

    Returns:
        Chaîne formatée pour l'attribut HTML title, ex: "\\n•PROJ_A\\n•PROJ_B"
    """
    failed_ids = x.loc[x["is_success"] == False, COL_PROJECT_ID].unique()
    return "\n•" + "\n•".join(failed_ids)


def compute_trend_30d(df_30d: pd.DataFrame) -> pd.DataFrame:
    """
    Construit un DataFrame de 30 lignes (une par jour calendaire) pour la heatmap.

    Pour chaque jour :
      - pct_success_projects   : % de projets 100% verts ce jour-là
      - list_failed_projects   : liste des projets en échec (pour tooltip)
      - health_status          : "perfect" / "warning" / "critical"
      - week_of_day            : jour de la semaine (ex: "Monday")

    Logique health_status (basée sur _THRESHOLD_CRITICAL = 80%) :
      pct == 100                    → "perfect"  (vert)
      _THRESHOLD_CRITICAL <= pct < 100 → "warning"  (orange)
      pct < _THRESHOLD_CRITICAL     → "critical" (rouge)

    Args:
        df_30d : DataFrame filtré sur 30 jours (issu de filter_by_window)

    Returns:
        DataFrame de 30 lignes prêt pour build_calendar_html()
    """
    df_30d = df_30d.copy()
    df_30d["is_success"] = df_30d[COL_RUN_STATUS].str.lower() == "success"

    daily = df_30d.groupby(df_30d[COL_RUN_DATE].dt.date).apply(
        lambda x: pd.Series({
            "pct_success_projects": x.groupby(COL_PROJECT_ID)["is_success"].all().mean(),
            "list_failed_projects": _get_failed_list(x),
        })
    ).reset_index()

    daily["date_column"] = pd.to_datetime(daily[COL_RUN_DATE]).dt.normalize()

    date_range  = pd.date_range(end=pd.Timestamp.now().normalize(), periods=30, freq="D")
    template_df = pd.DataFrame({"date_column": date_range})

    daily["date_column"]       = daily["date_column"].dt.tz_localize(None).dt.tz_localize("UTC")
    template_df["date_column"] = template_df["date_column"].dt.tz_localize(None).dt.tz_localize("UTC")

    final_df = pd.merge(template_df, daily, on="date_column", how="left")
    final_df["pct_success_projects"] = round(final_df["pct_success_projects"] * 100, 1).fillna(0)

    # Attribution du statut de santé — logique explicite en 3 cas mutuellement exclusifs
    final_df["health_status"] = np.where(
        final_df["pct_success_projects"] == 100,
        "perfect",
        np.where(
            final_df["pct_success_projects"] < _THRESHOLD_CRITICAL,
            "critical",
            "warning",
        ),
    )

    final_df["week_of_day"] = [
        x.strftime("%A") if pd.notna(x) else "" for x in final_df["date_column"]
    ]

    return final_df


# =============================================================================
# 5. PRÉ-AGRÉGATION DES HEATMAPS 7J (par projet et par scénario)
# =============================================================================

def compute_heatmap_7d(df_7d: pd.DataFrame) -> dict:
    """
    Pré-calcule les statuts journaliers sur 7 jours pour chaque projet et scénario.

    Cette fonction évite de recalculer les heatmaps dans la boucle HTML de
    drill_down_table.py (qui itère sur chaque projet × scénario × run).
    Le résultat est un dict indexé par (project_id, scenario_id) pour un accès O(1).

    Logique :
      - Un projet/scénario est "failed" pour un jour si au moins un run_status == FAILED
      - Les jours sans run sont marqués "NA" (case grise dans la heatmap)

    Args:
        df_7d : DataFrame filtré sur 7 jours (issu de filter_by_window).
                Doit contenir : project_id, scenario_id, run_exec, run_status.

    Returns:
        dict avec deux clés :
          "project"  → {project_id: {date_str: "success"|"failed"|"NA"}}
          "scenario" → {(project_id, scenario_id): {date_str: "success"|"failed"|"NA"}}
    """
    df = df_7d.copy()

    # Référentiel des 7 derniers jours calendaires (se termine aujourd'hui)
    today      = pd.Timestamp.now().normalize()
    date_range = pd.date_range(end=today, periods=7, freq="D")
    all_dates  = [d.strftime("%Y-%m-%d") for d in date_range]

    # Colonne date normalisée (YYYY-MM-DD string) pour le groupby
    df["_date"] = pd.to_datetime(df["run_exec"]).dt.strftime("%Y-%m-%d")

    # ── Niveau projet ──────────────────────────────────────────────────────────
    proj_agg = (
        df.groupby([COL_PROJECT_ID, "_date"])[COL_RUN_STATUS]
        .apply(lambda x: "failed" if (x == "FAILED").any() else "success")
        .reset_index()
    )

    project_heatmaps: dict = {}
    for proj_id, grp in proj_agg.groupby(COL_PROJECT_ID):
        day_map = dict(zip(grp["_date"], grp[COL_RUN_STATUS]))
        project_heatmaps[proj_id] = {d: day_map.get(d, "NA") for d in all_dates}

    # ── Niveau scénario ────────────────────────────────────────────────────────
    scen_agg = (
        df.groupby([COL_PROJECT_ID, "scenario_id", "_date"])[COL_RUN_STATUS]
        .apply(lambda x: "failed" if (x == "FAILED").any() else "success")
        .reset_index()
    )

    scenario_heatmaps: dict = {}
    for (proj_id, scen_id), grp in scen_agg.groupby([COL_PROJECT_ID, "scenario_id"]):
        day_map = dict(zip(grp["_date"], grp[COL_RUN_STATUS]))
        scenario_heatmaps[(proj_id, scen_id)] = {d: day_map.get(d, "NA") for d in all_dates}

    return {
        "dates":    all_dates,
        "project":  project_heatmaps,
        "scenario": scenario_heatmaps,
    }


# =============================================================================
# 6. ENRICHISSEMENT DES STEPS (pour le tableau drill-down)
# =============================================================================

def enrich_steps(df_step: pd.DataFrame, df_run: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare le DataFrame des steps pour l'affichage dans le tableau hiérarchique.

    Transformations appliquées :
      1. Parse la date/heure depuis le run_id (format : YYYY-MM-DD-HH-MM-SS-ms)
      2. Filtre sur les 7 derniers jours et exclut les projets système
      3. Extrait l'heure d'exécution (HH:MM) et la date du run (YYYY-MM-DD)
      4. Formate le type de step en version lisible (ex: "build_flowitem" → "BUILD")
      5. Construit un libellé court de step (type + nom, tronqué à 30 caractères)
      6. Assigne une catégorie d'erreur selon le type de step qui a échoué
      7. Joint la durée d'exécution (run_time) depuis df_run et calcule l'indicateur de tendance

    Args:
        df_step : DataFrame brut des steps (issu de load_raw_data + normalize_statuses)
        df_run  : DataFrame des runs scénario (issu de load_raw_data + normalize_statuses)
                  Doit contenir les colonnes run_id et run_time.

    Returns:
        DataFrame enrichi prêt à être consommé par build_drill_down_html()
    """
    df_step = df_step.copy()

    # --- 1. Parse de la date depuis le run_id ---
    df_step[COL_RUN_DATE] = pd.to_datetime(df_step[COL_RUN_ID], format="%Y-%m-%d-%H-%M-%S-%f")

    # --- 2. Filtrage temporel (7 jours) ---
    reference_date = df_step[COL_RUN_DATE].max()
    seven_days_ago = reference_date - timedelta(days=WINDOW_7_DAYS - 1)
    df_step = df_step[
        (df_step[COL_RUN_DATE] >= seven_days_ago)
        & (~df_step[COL_PROJECT_ID].isin(EXCLUDED_PROJECTS))
    ].copy()

    # --- 3. Extraction de l'heure et de la date depuis le run_id ---
    df_step["heure_exec"] = [x[11:16].replace("-", ":") for x in df_step[COL_RUN_ID]]
    df_step["run_exec"]   = [x[0:10]                    for x in df_step[COL_RUN_ID]]

    # --- 4. Formatage du type de step ---
    df_step["step_type"] = [
        x.replace("_", " ").upper().replace("FLOWITEM", "").strip()
        for x in df_step["step_type"]
    ]

    # --- 5. Libellé complet et version courte ---
    df_step["step_name_complete"] = df_step["step_type"] + " " + df_step["step_name"]
    df_step["step_id_short"]      = [x[0:30] for x in df_step["step_name_complete"]]

    # --- 6. Catégorie d'erreur selon le type de step ---
    error_map = {
        "COMPUTE METRICS": "Compute Metrics Error",
        "CHECK DATASET":   "Dataset Metrics Error",
        "EXEC SQL":        "BigQuery Error",
        "CUSTOM PYTHON":   "Python Error",
    }

    df_step["error_category"] = np.nan
    for step_type, error_label in error_map.items():
        mask = (df_step["step_type"] == step_type) & (df_step[COL_STEP_RESULT] == "FAILED")
        df_step.loc[mask, "error_category"] = error_label

    df_step["project_tags"] = df_step["project_tags"].fillna("")

    # --- 7. Durée d'exécution et indicateur de tendance ---
    if "run_time" in df_run.columns:
        run_durations = (
            df_run[["run_id", "run_time"]]
            .drop_duplicates("run_id")
            .copy()
        )
        run_durations["run_duration_s"] = (
            pd.to_timedelta(run_durations["run_time"]).dt.total_seconds()
        )
        df_step = df_step.merge(
            run_durations[["run_id", "run_duration_s"]], on="run_id", how="left"
        )

        # Moyenne glissante sur les N dernières exécutions du même scénario
        # On trie par run_id (qui encode la date) pour avoir l'ordre chronologique
        N_LAST_RUNS = 10  # Nombre de runs précédents à considérer pour la moyenne

        runs_dedup = (
            df_step.drop_duplicates(subset=["project_id", "scenario_id", "run_id"])
            [["project_id", "scenario_id", "run_id", "run_duration_s"]]
            .sort_values(["project_id", "scenario_id", "run_id"])
            .copy()
        )

        # Pour chaque run, on calcule la moyenne des N runs PRÉCÉDENTS (excluant le run courant)
        # en utilisant un expanding/rolling avec shift(1) pour éviter le data leakage
        runs_dedup["avg_duration_s"] = (
            runs_dedup
            .groupby(["project_id", "scenario_id"])["run_duration_s"]
            .transform(lambda x: x.shift(1).rolling(window=N_LAST_RUNS, min_periods=1).mean())
        )

        # Nombre de runs utilisés pour la moyenne (pour l'afficher dans le tooltip)
        runs_dedup["n_runs_avg"] = (
            runs_dedup
            .groupby(["project_id", "scenario_id"])["run_duration_s"]
            .transform(lambda x: x.shift(1).rolling(window=N_LAST_RUNS, min_periods=1).count())
        )

        df_step = df_step.merge(
            runs_dedup[["project_id", "scenario_id", "run_id", "avg_duration_s", "n_runs_avg"]],
            on=["project_id", "scenario_id", "run_id"],
            how="left"
        )
    else:
        df_step["run_duration_s"] = np.nan
        df_step["avg_duration_s"] = np.nan

    return df_step


# =============================================================================
# 7. DONNÉES POUR LE GRAPHIQUE TIMELINE (Gantt concurrence)
# =============================================================================

def prepare_timeline_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare le DataFrame scénario pour le graphique timeline (Gantt).

    Pour chaque run, calcule start_s et end_s (secondes écoulées depuis minuit)
    afin de positionner des barres horizontales sur un axe 0h–24h.

    Args:
        df : DataFrame scénario normalisé (issu de normalize_statuses).
             Doit contenir : project_id, scenario_id, run_id, run_date,
             run_status et run_time.

    Returns:
        DataFrame avec colonnes :
          project_id, scenario_id, run_id, run_status,
          run_day (YYYY-MM-DD), start_s, end_s, run_duration_s
    """
    df = df.copy()
    df = df[~df[COL_PROJECT_ID].isin(EXCLUDED_PROJECTS)].copy()
    df[COL_RUN_DATE] = pd.to_datetime(df[COL_RUN_DATE])

    if "run_time" in df.columns:
        df["run_duration_s"] = (
            pd.to_timedelta(df["run_time"]).dt.total_seconds().fillna(0)
        )
    else:
        df["run_duration_s"] = 0.0

    max_date = df[COL_RUN_DATE].max()
    df = df[df[COL_RUN_DATE] >= (max_date - timedelta(days=WINDOW_7_DAYS - 1)).normalize()].copy()

    df["run_day"] = df[COL_RUN_DATE].dt.strftime("%Y-%m-%d")
    df["start_s"] = (df[COL_RUN_DATE] - df[COL_RUN_DATE].dt.normalize()).dt.total_seconds()
    df["end_s"]   = (df["start_s"] + df["run_duration_s"]).clip(upper=86400.0)

    # ── Moyenne glissante sur les N dernières exécutions du même scénario ────
    # Même logique que dans enrich_steps() : shift(1) pour exclure le run courant
    N_LAST_RUNS = 10
    df_sorted = df.sort_values([COL_PROJECT_ID, "scenario_id", COL_RUN_ID]).copy()
    df_sorted["avg_duration_s"] = (
        df_sorted
        .groupby([COL_PROJECT_ID, "scenario_id"])["run_duration_s"]
        .transform(lambda x: x.shift(1).rolling(window=N_LAST_RUNS, min_periods=1).mean())
    )
    df_sorted["n_runs_avg"] = (
        df_sorted
        .groupby([COL_PROJECT_ID, "scenario_id"])["run_duration_s"]
        .transform(lambda x: x.shift(1).rolling(window=N_LAST_RUNS, min_periods=1).count())
    )
    df = df_sorted

    keep = [COL_PROJECT_ID, "scenario_id", COL_RUN_ID, COL_RUN_STATUS,
            "run_day", "start_s", "end_s", "run_duration_s", "avg_duration_s", "n_runs_avg"]
    return df[[c for c in keep if c in df.columns]].copy()
