# =============================================================================
# tests/test_processor.py
# -----------------------------------------------------------------------------
# Tests unitaires pour data/processor.py.
#
# Ces tests utilisent des DataFrames mockés (sans connexion Dataiku) pour
# valider la logique métier de chaque fonction de transformation.
#
# Lancer les tests :
#   python -m pytest tests/ -v
# =============================================================================

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# On importe directement les fonctions à tester
from data.processor import (
    normalize_statuses,
    filter_by_window,
    compute_kpis_7d,
    compute_trend_30d,
    compute_heatmap_7d,
    enrich_steps,
)


# =============================================================================
# FIXTURES : DataFrames de test réutilisables
# =============================================================================

def _make_df_scenario(rows: list) -> pd.DataFrame:
    """
    Crée un DataFrame scénario minimal à partir d'une liste de tuples.
    Format : (project_id, scenario_id, run_id, run_date, run_status)
    """
    return pd.DataFrame(rows, columns=[
        "project_id", "scenario_id", "run_id", "run_date", "run_status"
    ])


def _make_df_step(rows: list) -> pd.DataFrame:
    """
    Crée un DataFrame step minimal à partir d'une liste de tuples.
    Format : (project_id, scenario_id, run_id, step_name, step_type, step_result, run_status)
    """
    return pd.DataFrame(rows, columns=[
        "project_id", "scenario_id", "run_id",
        "step_name", "step_type", "step_result", "run_status"
    ])


# =============================================================================
# 1. TESTS : normalize_statuses
# =============================================================================

class TestNormalizeStatuses:

    def test_aborted_becomes_failed_in_scenario(self):
        """ABORTED dans run_status du scénario → FAILED"""
        df = _make_df_scenario([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "2025-04-08", "ABORTED"),
            ("PROJ_A", "SCN_1", "2025-04-09-10-00-00-000", "2025-04-09", "SUCCESS"),
        ])
        df_step = _make_df_step([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "step1", "EXEC_SQL", "SUCCESS", "ABORTED"),
        ])
        df_out, _ = normalize_statuses(df, df_step)
        assert df_out["run_status"].tolist() == ["FAILED", "SUCCESS"]

    def test_warning_becomes_success_in_scenario(self):
        """WARNING dans run_status du scénario → SUCCESS"""
        df = _make_df_scenario([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "2025-04-08", "WARNING"),
        ])
        df_step = _make_df_step([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "step1", "EXEC_SQL", "WARNING", "WARNING"),
        ])
        df_out, df_step_out = normalize_statuses(df, df_step)
        assert df_out["run_status"].iloc[0] == "SUCCESS"
        assert df_step_out["run_status"].iloc[0] == "SUCCESS"
        assert df_step_out["step_result"].iloc[0] == "SUCCESS"

    def test_aborted_becomes_failed_in_step_result(self):
        """ABORTED dans step_result → FAILED"""
        df = _make_df_scenario([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "2025-04-08", "SUCCESS"),
        ])
        df_step = _make_df_step([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "step1", "EXEC_SQL", "ABORTED", "SUCCESS"),
        ])
        _, df_step_out = normalize_statuses(df, df_step)
        assert df_step_out["step_result"].iloc[0] == "FAILED"

    def test_success_unchanged(self):
        """SUCCESS reste SUCCESS (pas de remplacement parasite)"""
        df = _make_df_scenario([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "2025-04-08", "SUCCESS"),
        ])
        df_step = _make_df_step([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "step1", "EXEC_SQL", "SUCCESS", "SUCCESS"),
        ])
        df_out, df_step_out = normalize_statuses(df, df_step)
        assert df_out["run_status"].iloc[0] == "SUCCESS"
        assert df_step_out["step_result"].iloc[0] == "SUCCESS"

    def test_failed_unchanged(self):
        """FAILED reste FAILED"""
        df = _make_df_scenario([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "2025-04-08", "FAILED"),
        ])
        df_step = _make_df_step([
            ("PROJ_A", "SCN_1", "2025-04-08-10-00-00-000", "step1", "EXEC_SQL", "FAILED", "FAILED"),
        ])
        df_out, df_step_out = normalize_statuses(df, df_step)
        assert df_out["run_status"].iloc[0] == "FAILED"
        assert df_step_out["step_result"].iloc[0] == "FAILED"


# =============================================================================
# 2. TESTS : filter_by_window
# =============================================================================

class TestFilterByWindow:

    def _make_df(self, days_back: list, project_ids: list = None) -> pd.DataFrame:
        """Crée un DataFrame avec des dates relatives à aujourd'hui."""
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        if project_ids is None:
            project_ids = ["PROJ_A"] * len(days_back)
        rows = []
        for i, (d, p) in enumerate(zip(days_back, project_ids)):
            run_date = today - timedelta(days=d)
            rows.append((p, "SCN_1", f"run_{i}", run_date, "SUCCESS"))
        return _make_df_scenario(rows)

    def test_keeps_last_7_days(self):
        """Seuls les runs des 7 derniers jours sont conservés."""
        df = self._make_df([0, 3, 6, 7, 10])  # 0=aujourd'hui, 10=trop vieux
        result = filter_by_window(df, days=7)
        # run_date max = aujourd'hui → start = aujourd'hui - 6 jours
        # Donc days_back=7 et 10 sont exclus
        assert len(result) == 3

    def test_excludes_admin_project(self):
        """Le projet ADMIN est toujours exclu."""
        df = self._make_df([0, 1], project_ids=["ADMIN", "PROJ_A"])
        result = filter_by_window(df, days=7)
        assert "ADMIN" not in result["project_id"].values
        assert len(result) == 1

    def test_30_day_window(self):
        """La fenêtre 30 jours conserve plus de données."""
        df = self._make_df([0, 15, 29, 30])
        result = filter_by_window(df, days=30)
        # days_back=30 → start = max - 29 → 30 jours en arrière est exclu
        assert len(result) == 3

    def test_empty_result_raises_no_error(self):
        """Un DataFrame vide après filtrage ne lève pas d'erreur."""
        df = self._make_df([100, 200])  # Tous trop vieux
        result = filter_by_window(df, days=7)
        assert result.empty


# =============================================================================
# 3. TESTS : compute_kpis_7d
# =============================================================================

class TestComputeKpis7d:

    def _make_df_7d(self, statuses_by_project: dict) -> pd.DataFrame:
        """
        Crée un DataFrame 7j à partir d'un dict {project_id: [statuses]}.
        Chaque statut correspond à un run sur un jour différent.
        """
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        for proj, statuses in statuses_by_project.items():
            for i, status in enumerate(statuses):
                run_date = today - timedelta(days=i)
                run_id   = f"{proj}-run-{i}"
                rows.append((proj, "SCN_1", run_id, run_date, status))
        return _make_df_scenario(rows)

    def test_distinct_projects_count(self):
        """Le nombre de projets distincts est correct."""
        df = self._make_df_7d({"PROJ_A": ["SUCCESS"], "PROJ_B": ["SUCCESS"]})
        kpis = compute_kpis_7d(df)
        assert kpis["distinct_projects"] == 2

    def test_all_success_gives_100_pct(self):
        """100% de succès → avg_success_projects = 100.0"""
        df = self._make_df_7d({"PROJ_A": ["SUCCESS", "SUCCESS", "SUCCESS"]})
        kpis = compute_kpis_7d(df)
        assert kpis["avg_success_projects"] == pytest.approx(100.0)

    def test_all_failed_gives_0_pct(self):
        """100% d'échecs → avg_success_projects = 0.0"""
        df = self._make_df_7d({"PROJ_A": ["FAILED", "FAILED", "FAILED"]})
        kpis = compute_kpis_7d(df)
        assert kpis["avg_success_projects"] == pytest.approx(0.0)

    def test_failed_projects_24h(self):
        """Un projet en échec aujourd'hui est compté dans failed_projects_24h."""
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = [
            ("PROJ_A", "SCN_1", "run_1", today, "FAILED"),   # Aujourd'hui → compté
            ("PROJ_B", "SCN_1", "run_2", today, "SUCCESS"),  # Aujourd'hui → non compté
            ("PROJ_C", "SCN_1", "run_3", today - timedelta(days=1), "FAILED"),  # Hier → non compté
        ]
        df = _make_df_scenario(rows)
        kpis = compute_kpis_7d(df)
        assert kpis["failed_projects_24h"] == 1

    def test_chronic_project_detection(self):
        """Un projet avec ≥ 80% de runs FAILED est détecté comme 'chronic'."""
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        # PROJ_A : 4 FAILED sur 5 runs = 80% → chronic
        for i in range(4):
            rows.append(("PROJ_A", "SCN_1", f"run_fail_{i}", today - timedelta(days=i), "FAILED"))
        rows.append(("PROJ_A", "SCN_1", "run_ok", today - timedelta(days=4), "SUCCESS"))
        # PROJ_B : 1 FAILED sur 5 = 20% → pas chronic
        for i in range(4):
            rows.append(("PROJ_B", "SCN_1", f"run_ok_{i}", today - timedelta(days=i), "SUCCESS"))
        rows.append(("PROJ_B", "SCN_1", "run_fail", today - timedelta(days=4), "FAILED"))

        df = _make_df_scenario(rows)
        kpis = compute_kpis_7d(df)
        assert kpis["chronic_projects"] == 1

    def test_isolated_failure_detection(self):
        """Un projet avec exactement 1 run FAILED (et taux < 80%) est 'isolated'."""
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        # PROJ_A : 1 FAILED sur 5 = 20% → isolated
        rows.append(("PROJ_A", "SCN_1", "run_fail", today, "FAILED"))
        for i in range(1, 5):
            rows.append(("PROJ_A", "SCN_1", f"run_ok_{i}", today - timedelta(days=i), "SUCCESS"))

        df = _make_df_scenario(rows)
        kpis = compute_kpis_7d(df)
        assert kpis["isolated_failures"] == 1


# =============================================================================
# 4. TESTS : compute_trend_30d
# =============================================================================

class TestComputeTrend30d:

    def _make_df_30d(self, days_and_statuses: list) -> pd.DataFrame:
        """
        Crée un DataFrame 30j.
        days_and_statuses : liste de (days_back, project_id, status)
        """
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        rows = []
        for i, (d, proj, status) in enumerate(days_and_statuses):
            run_date = today - timedelta(days=d)
            rows.append((proj, "SCN_1", f"run_{i}", run_date, status))
        return _make_df_scenario(rows)

    def test_returns_30_rows(self):
        """Le résultat contient toujours exactement 30 lignes."""
        df = self._make_df_30d([(0, "PROJ_A", "SUCCESS"), (1, "PROJ_A", "SUCCESS")])
        result = compute_trend_30d(df)
        assert len(result) == 30

    def test_perfect_day_when_all_success(self):
        """Un jour où tous les projets sont SUCCESS → health_status = 'perfect'."""
        df = self._make_df_30d([
            (0, "PROJ_A", "SUCCESS"),
            (0, "PROJ_B", "SUCCESS"),
        ])
        result = compute_trend_30d(df)
        today_row = result.iloc[-1]  # Dernier jour = aujourd'hui
        assert today_row["health_status"] == "perfect"
        assert today_row["pct_success_projects"] == 100.0

    def test_critical_day_when_all_failed(self):
        """Un jour où tous les projets sont FAILED → health_status = 'critical'."""
        df = self._make_df_30d([
            (0, "PROJ_A", "FAILED"),
            (0, "PROJ_B", "FAILED"),
        ])
        result = compute_trend_30d(df)
        today_row = result.iloc[-1]
        assert today_row["health_status"] == "critical"

    def test_warning_day_between_thresholds(self):
        """Un jour avec 50% de projets OK (entre 0% et 100%) → 'warning' ou 'critical'."""
        df = self._make_df_30d([
            (0, "PROJ_A", "SUCCESS"),
            (0, "PROJ_B", "FAILED"),
        ])
        result = compute_trend_30d(df)
        today_row = result.iloc[-1]
        # 50% < 80% → critical (en dessous du seuil)
        assert today_row["health_status"] == "critical"
        assert today_row["pct_success_projects"] == 50.0

    def test_days_without_data_are_filled(self):
        """Les jours sans données sont comblés avec pct=0 et health_status='critical'."""
        # On ne fournit des données que pour aujourd'hui
        df = self._make_df_30d([(0, "PROJ_A", "SUCCESS")])
        result = compute_trend_30d(df)
        # Les 29 autres jours doivent avoir pct=0
        empty_days = result[result["pct_success_projects"] == 0]
        assert len(empty_days) == 29


# =============================================================================
# 5. TESTS : compute_heatmap_7d
# =============================================================================

class TestComputeHeatmap7d:

    def _make_df_with_run_exec(self, rows: list) -> pd.DataFrame:
        """
        Crée un DataFrame avec la colonne run_exec (YYYY-MM-DD).
        rows : liste de (project_id, scenario_id, run_exec, run_status)
        """
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        data = []
        for i, (proj, scen, days_back, status) in enumerate(rows):
            run_date = today - timedelta(days=days_back)
            run_exec = run_date.strftime("%Y-%m-%d")
            run_date_str = run_date.strftime("%Y-%m-%d %H:%M:%S")
            data.append((proj, scen, f"run_{i}", run_date_str, status, run_exec))
        return pd.DataFrame(data, columns=[
            "project_id", "scenario_id", "run_id", "run_date", "run_status", "run_exec"
        ])

    def test_returns_correct_keys(self):
        """Le dict retourné contient les clés 'dates', 'project', 'scenario'."""
        df = self._make_df_with_run_exec([("PROJ_A", "SCN_1", 0, "SUCCESS")])
        result = compute_heatmap_7d(df)
        assert "dates" in result
        assert "project" in result
        assert "scenario" in result

    def test_dates_has_7_entries(self):
        """La liste 'dates' contient exactement 7 entrées."""
        df = self._make_df_with_run_exec([("PROJ_A", "SCN_1", 0, "SUCCESS")])
        result = compute_heatmap_7d(df)
        assert len(result["dates"]) == 7

    def test_project_heatmap_failed_day(self):
        """Un jour avec au moins un FAILED → statut 'failed' dans la heatmap projet."""
        df = self._make_df_with_run_exec([
            ("PROJ_A", "SCN_1", 0, "FAILED"),
            ("PROJ_A", "SCN_2", 0, "SUCCESS"),
        ])
        result = compute_heatmap_7d(df)
        today_str = datetime.today().strftime("%Y-%m-%d")
        assert result["project"]["PROJ_A"][today_str] == "failed"

    def test_project_heatmap_success_day(self):
        """Un jour avec tous SUCCESS → statut 'success' dans la heatmap projet."""
        df = self._make_df_with_run_exec([
            ("PROJ_A", "SCN_1", 0, "SUCCESS"),
            ("PROJ_A", "SCN_2", 0, "SUCCESS"),
        ])
        result = compute_heatmap_7d(df)
        today_str = datetime.today().strftime("%Y-%m-%d")
        assert result["project"]["PROJ_A"][today_str] == "success"

    def test_missing_day_is_na(self):
        """Un jour sans run → statut 'NA' dans la heatmap."""
        df = self._make_df_with_run_exec([
            ("PROJ_A", "SCN_1", 0, "SUCCESS"),  # Seulement aujourd'hui
        ])
        result = compute_heatmap_7d(df)
        yesterday_str = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result["project"]["PROJ_A"][yesterday_str] == "NA"

    def test_scenario_heatmap_indexed_by_tuple(self):
        """La heatmap scénario est indexée par (project_id, scenario_id)."""
        df = self._make_df_with_run_exec([
            ("PROJ_A", "SCN_1", 0, "SUCCESS"),
            ("PROJ_A", "SCN_2", 0, "FAILED"),
        ])
        result = compute_heatmap_7d(df)
        assert ("PROJ_A", "SCN_1") in result["scenario"]
        assert ("PROJ_A", "SCN_2") in result["scenario"]
        today_str = datetime.today().strftime("%Y-%m-%d")
        assert result["scenario"][("PROJ_A", "SCN_2")][today_str] == "failed"


# =============================================================================
# POINT D'ENTRÉE (exécution directe)
# =============================================================================

if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
