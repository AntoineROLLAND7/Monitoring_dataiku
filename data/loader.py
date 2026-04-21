# =============================================================================
# data_loader.py
# -----------------------------------------------------------------------------
# Responsabilité unique : se connecter aux datasets Dataiku et retourner
# les données brutes sous forme de DataFrames pandas.
#
# Ce fichier ne fait AUCUNE transformation. Il est volontairement minimal
# pour que le chargement soit facilement remplaçable (ex : lecture CSV locale
# pour les tests unitaires) sans impacter le reste du projet.
# =============================================================================

import dataiku          # SDK Dataiku pour accéder aux datasets du projet
import pandas as pd     # Manipulation des données tabulaires
from config import DATASET_SCENARIO, DATASET_STEP_SCENARIO  # Noms des datasets (centralisés)
from typing import Tuple


# Colonnes minimales attendues dans chaque dataset.
# Utilisées pour valider que le schéma est correct après chargement.
_REQUIRED_COLS_SCENARIO = {"project_id", "scenario_id", "run_id", "run_date", "run_status"}
_REQUIRED_COLS_STEP     = {"project_id", "scenario_id", "run_id", "step_name", "step_type", "step_result"}


def load_raw_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Charge les deux datasets Dataiku bruts sans aucune transformation.

    Connexion au projet Dataiku courant (contexte d'exécution du notebook/recipe).
    Les données sont retournées telles quelles depuis le stockage Dataiku.

    Returns:
        df      (pd.DataFrame) : Runs au niveau scénario.
                                 Colonnes attendues : project_id, scenario_id,
                                 run_id, run_date, run_status, scenario_link, ...

        df_step (pd.DataFrame) : Runs au niveau step (étape individuelle).
                                 Colonnes attendues : project_id, scenario_id,
                                 run_id, step_name, step_type, step_result,
                                 step_order, monitoring_timestamp, ...

    Raises:
        RuntimeError : Si un dataset est introuvable dans Dataiku, vide,
                       ou s'il manque des colonnes obligatoires.
    """

    # --- Chargement du dataset scénario ---
    df = _load_dataset(DATASET_SCENARIO, _REQUIRED_COLS_SCENARIO)

    # --- Chargement du dataset step ---
    df_step = _load_dataset(DATASET_STEP_SCENARIO, _REQUIRED_COLS_STEP)

    return df, df_step


def _load_dataset(name: str, required_cols: set) -> pd.DataFrame:
    """
    Charge un dataset Dataiku par son nom, avec validation du schéma et du contenu.

    Args:
        name          : Nom exact du dataset dans le projet Dataiku.
        required_cols : Ensemble des colonnes minimales attendues.

    Returns:
        pd.DataFrame chargé et validé.

    Raises:
        RuntimeError : Si le dataset est introuvable, vide, ou incomplet.
    """
    # --- Connexion au dataset ---
    try:
        dataset = dataiku.Dataset(name)
        df = dataset.get_dataframe()
    except Exception as e:
        raise RuntimeError(
            f"[loader] Impossible de charger le dataset '{name}' depuis Dataiku.\n"
            f"  → Vérifiez que le dataset existe dans le projet courant.\n"
            f"  → Détail de l'erreur : {e}"
        ) from e

    # --- Vérification que le DataFrame n'est pas vide ---
    if df.empty:
        raise RuntimeError(
            f"[loader] Le dataset '{name}' est vide (0 lignes).\n"
            f"  → Vérifiez que le pipeline d'ingestion a bien tourné."
        )

    # --- Vérification des colonnes obligatoires ---
    missing = required_cols - set(df.columns)
    if missing:
        raise RuntimeError(
            f"[loader] Le dataset '{name}' est incomplet.\n"
            f"  → Colonnes manquantes : {sorted(missing)}\n"
            f"  → Colonnes présentes  : {sorted(df.columns.tolist())}"
        )

    print(f"[loader] ✅ '{name}' chargé — {len(df):,} lignes, {len(df.columns)} colonnes.")
    return df
