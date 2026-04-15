# =============================================================================
# html_builder/calendar.py
# -----------------------------------------------------------------------------
# Génère la heatmap calendrier sur 30 jours affichée dans la 4e carte KPI.
#
# Rendu visuel :
#   - Grille CSS de 7 colonnes (lundi → dimanche)
#   - Chaque case = un jour, colorée selon health_status (perfect/warning/critical)
#   - Tooltip au survol : date, % de succès, liste des projets en échec
#   - Le dernier jour (aujourd'hui) est encadré en violet pour le repérer facilement
# =============================================================================

import pandas as pd


def build_calendar_html(final_df: pd.DataFrame, date_col: str = "date_column") -> str:
    """
    Convertit le DataFrame 30 jours en grille HTML calendrier (7 colonnes = jours de la semaine).

    La grille utilise la classe CSS "calendar-grid" définie dans styles.py, qui applique
    un display:grid à 7 colonnes. Les cases sont colorées via les classes "heat-{status}".

    Alignement :
      On calcule le décalage du premier jour (weekday() : 0=lundi, 6=dimanche)
      et on insère des cases vides au début pour que lundi tombe toujours en colonne 1.

    Args:
        final_df (pd.DataFrame) : DataFrame issu de compute_trend_30d(), contenant
                                   les colonnes : date_column, health_status,
                                   pct_success_projects, list_failed_projects
        date_col (str)          : Nom de la colonne datetime (par défaut "date_column")

    Returns:
        str : Bloc HTML <div class="calendar-grid">...</div> prêt à injecter dans la page.
    """
    df = final_df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(by=date_col)  # Tri chronologique obligatoire pour l'affichage en grille

    # --- Calcul du décalage initial ---
    # weekday() retourne 0 pour lundi, 6 pour dimanche
    # On insère autant de cases vides que nécessaire pour aligner le premier jour sur le bon jour
    premier_jour   = df[date_col].min()
    decalage_debut = premier_jour.weekday()  # Ex: si le premier jour est mercredi → 2 cases vides

    # Libellés des colonnes (une lettre par jour de la semaine, dans l'ordre lundi-dimanche)
    jours_labels = ["M", "T", "W", "T", "F", "S", "S"]

    html = '<div class="calendar-grid">\n'

    # --- En-tête : libellés des jours de la semaine ---
    for label in jours_labels:
        html += f'    <div class="calendar-label">{label}</div>\n'

    # --- Cases vides pour aligner le premier jour sur la bonne colonne ---
    for _ in range(decalage_debut):
        html += '    <div class="calendar-day empty"></div>\n'

    # --- Cases de données (une par jour du DataFrame) ---
    derniere_date = df[date_col].max()  # Utilisé pour identifier "aujourd'hui"

    for _, row in df.iterrows():
        current_date = row[date_col]

        # Le dernier jour reçoit un outline violet pour indiquer "aujourd'hui"
        style = ""
        if current_date == derniere_date:
            style = ' style="outline: 2px solid var(--primary); outline-offset: 2px;"'

        # Récupération des données de la ligne (avec valeurs par défaut si colonne absente)
        health_status = row.get("health_status", "empty")         # Classe CSS de couleur
        pct           = row.get("pct_success_projects", 0)         # Taux affiché dans le tooltip
        failed_list   = row.get("list_failed_projects", "")        # Liste projets KO (tooltip)

        # Chaque case est un <div> avec :
        #   - class "heat-{status}" → colorisation CSS (voir styles.py)
        #   - title → tooltip natif HTML au survol (&#10; = saut de ligne dans un attribut)
        #   - style → outline pour "aujourd'hui" uniquement
        html += (
            f'    <div class="calendar-day heat-{health_status}" '
            f'title="{current_date} : {pct} % &#10;Projets en échec: {failed_list}"'
            f'{style}></div>\n'
        )

    html += "</div>"
    return html
