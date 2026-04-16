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


def load_raw_data() -> tuple[pd.DataFrame, pd.DataFrame]:
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
    """

    # --- Chargement du dataset scénario ---
    # Contient une ligne par run de scénario (niveau agrégé projet/scénario)
    monitoring_scenario = dataiku.Dataset(DATASET_SCENARIO)
    df = monitoring_scenario.get_dataframe()

    # --- Chargement du dataset step ---
    # Contient une ligne par étape (step) de chaque run de scénario
    # Granularité plus fine que df : plusieurs lignes par run_id
    monitoring_step_scenario = dataiku.Dataset(DATASET_STEP_SCENARIO)
    df_step = monitoring_step_scenario.get_dataframe()

    return df, df_step
