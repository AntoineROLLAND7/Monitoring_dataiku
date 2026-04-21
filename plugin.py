#!/usr/bin/env python
# coding: utf-8

# In[1475]:


# %config Completer.use_jedi = False
# from IPython.display import display, HTML
# display(HTML("<style>.container { width:90% !important; }</style>"))


# # package

# In[1476]:


import dataiku
from dataiku import pandasutils as pdu
import pandas as pd
import base64
import dataiku.insights
from datetime import datetime, timedelta
import numpy as np


# # import des données

# In[1477]:


monitoring_scenario = dataiku.Dataset("monitoring_scenario")
df = monitoring_scenario.get_dataframe()

monitoring_step_scenario = dataiku.Dataset("monitoring_step_scenario")
df_step = monitoring_step_scenario.get_dataframe()


# In[1478]:


df['run_status'] = np.where(df['run_status'] == 'ABORTED', 'FAILED', df['run_status'])
df_step['run_status'] = np.where(df_step['run_status'] == 'ABORTED', 'FAILED', df_step['run_status'])
df_step['step_result'] = np.where(df_step['step_result'] == 'ABORTED', 'FAILED', df_step['step_result'])

df['run_status'] = np.where(df['run_status'] == 'WARNING', 'SUCCESS', df['run_status'])
df_step['run_status'] = np.where(df_step['run_status'] == 'WARNING', 'SUCCESS', df_step['run_status'])
df_step['step_result'] = np.where(df_step['step_result'] == 'WARNING', 'SUCCESS', df_step['step_result'])


# # data prep

# In[1479]:


today = datetime.today()

resultat = today.strftime("%B %d, %Y")


# ## project level

# In[1480]:


# Conversion en datetime si ce n'est pas déjà fait
df['run_date'] = pd.to_datetime(df['run_date'])

# Définition de la période (7 derniers jours à partir de la date max ou d'aujourd'hui)
reference_date = df['run_date'].max() 
seven_days_ago = reference_date - timedelta(days=6)

# Filtrage du dataframe
df_last_7d = df[(df['run_date'] >= seven_days_ago) & (df['project_id'] != "ADMIN")].copy()

distinct_projects = df_last_7d['project_id'].nunique()


# In[1481]:


# Définition de la période (7 derniers jours à partir de la date max ou d'aujourd'hui)
thirty_days_ago = reference_date - timedelta(days=30)

# Filtrage du dataframe
df_last_30d = df[(df['run_date'] >= thirty_days_ago) & (df['project_id'] != "ADMIN")].copy()


# In[1482]:


# On crée une colonne booléenne pour simplifier la moyenne (le % de True donne le taux de succès)
df_last_7d['is_success'] = df_last_7d['run_status'].str.lower() == 'success'
df_last_7d['not_is_success'] = df_last_7d['run_status'].str.lower() != 'success'

# Groupement par jour
daily_stats = df_last_7d.groupby(df_last_7d['run_date'].dt.date).agg(
    pct_success_scenarios=('is_success', 'mean'),
    # Pour le succès par projet, on peut considérer qu'un projet est en succès 
    # si tous ses runs de la journée sont OK (ou au moins un, selon votre règle métier)
    pct_success_projects=('is_success', lambda x: df_last_7d.loc[x.index].groupby('project_id')['is_success'].all().mean()),
#     nb_fail_projects=('is_success', lambda x: df_last_7d.loc[x.index].groupby('project_id')['not_is_success'].all().sum()),
    nb_fail_projects=('is_success', lambda x: (df_last_7d.loc[x.index].groupby('project_id')['not_is_success'].max() == 1).sum())

).reset_index()

# Passage en pourcentage pour la lisibilité
daily_stats['pct_success_scenarios'] *= 100
daily_stats['pct_success_projects'] *= 100


# In[1483]:


# Calcul des moyennes globales sur les 7 derniers jours
avg_success_scenarios = daily_stats['pct_success_scenarios'].mean()
avg_success_projects = daily_stats['pct_success_projects'].mean()


# In[1484]:


# On crée une colonne booléenne pour simplifier la moyenne (le % de True donne le taux de succès)
df_last_30d['is_success'] = df_last_30d['run_status'].str.lower() == 'success'
df_last_30d['not_is_success'] = df_last_30d['run_status'].str.lower() != 'success'

# Groupement par jour
daily_stats_30 = df_last_30d.groupby(df_last_30d['run_date'].dt.date).agg(
    pct_success_projects=('is_success', lambda x: df_last_30d.loc[x.index].groupby('project_id')['is_success'].all().mean())

).reset_index()


# In[1485]:


def get_failed_list(x):
    # Récupère les IDs là où is_success est False pour ce groupe (ce jour)
    failed_ids = x.loc[x['is_success'] == False, 'project_id'].unique()
    return '&#10;•'+'&#10;•'.join(failed_ids)

daily_stats_30 = df_last_30d.groupby(df_last_30d['run_date'].dt.date).apply(
    lambda x: pd.Series({
        'pct_success_projects': x.groupby('project_id')['is_success'].all().mean(),
        'list_failed_projects': get_failed_list(x)
    })
).reset_index()


# In[1486]:


daily_stats_30['date_column'] = pd.to_datetime(daily_stats_30['run_date']).dt.normalize()

date_range = pd.date_range(end=pd.Timestamp.now().normalize(), periods=30, freq='D')
template_df = pd.DataFrame({'date_column': date_range})

# Convertir les deux colonnes en UTC
daily_stats_30['date_column'] = pd.to_datetime(daily_stats_30['date_column']).dt.tz_localize(None).dt.tz_localize('UTC')
template_df['date_column'] = pd.to_datetime(template_df['date_column']).dt.tz_localize(None).dt.tz_localize('UTC')

final_df = pd.merge(template_df, daily_stats_30, on='date_column', how='left')

# # 5. Remplacer les valeurs manquantes (NaN) par "NA"
final_df['pct_success_projects'] = round(final_df['pct_success_projects']*100,1).fillna(0)

final_df['health_status'] = np.where(final_df['pct_success_projects'] < 100, 'warning', 'perfect')
final_df['health_status'] = np.where(final_df['pct_success_projects'] < 80, 'critical', 'warning')
final_df['health_status'] = np.where(final_df['pct_success_projects'] == 100, 'perfect', final_df['health_status'])

final_df['week_of_day'] = [x.strftime("%A") for x in final_df.run_date]


# In[1487]:


import pandas as pd
from datetime import timedelta

def dataframe_to_grid_html(df, date_col='run_date'):
    # 1. Conversion de la colonne en datetime si ce n'est pas déjà fait
    df[date_col] = pd.to_datetime(df[date_col])
    
    # On trie par date pour être sûr de l'ordre
    df = df.sort_values(by=date_col)
    
    # 2. Calcul du décalage pour l'alignement (Lundi = 0)
    # On regarde quel jour de la semaine est le premier jour du DataFrame
    premier_jour = df[date_col].min()
    decalage_debut = premier_jour.weekday() 
    
    # 3. Construction du HTML
    jours_labels = ["M", "T", "W", "T", "F", "S", "S"]
    html = '<div class="calendar-grid">\n'
    
    # En-tête (Lettres)
    for label in jours_labels:
        html += f'    <div class="calendar-label">{label}</div>\n'
    
    # Cases vides pour l'alignement initial
    for _ in range(decalage_debut):
        html += '    <div class="calendar-day empty"></div>\n'
    
    # 4. Parcours du DataFrame pour créer les carrés
    # On récupère la date la plus récente pour mettre l'outline "Today"
    derniere_date = df[date_col].max()
    
    for _, row in df.iterrows():
        current_date = row[date_col]
        
        # Logique de classe (vous pouvez l'adapter selon vos données)
        # Ici on met "heat-perfect" par défaut
        classe = "heat-perfect"
        style = ""
        
        # Si c'est le dernier jour du DF (le plus récent)
        if current_date == derniere_date:
            style = ' style="outline: 2px solid var(--primary); outline-offset: 2px;"'
            
        health_status = row['health_status']
        pct_success_projects = row['pct_success_projects']
        list_failed_projects = row['list_failed_projects']
            
        titre = f"{current_date.strftime('%Y-%m-%d')}"
        html += f'    <div class="calendar-day heat-{health_status}" title="{current_date} : {pct_success_projects} % &#10;Projets en échec: {list_failed_projects}" {style}></div>\n'
        
    html += '</div>'
    return html

calendar = dataframe_to_grid_html(final_df)


# ## step level

# In[1488]:


# Conversion en datetime si ce n'est pas déjà fait
df_step['run_date'] = pd.to_datetime(df_step['run_id'], format='%Y-%m-%d-%H-%M-%S-%f')
# Définition de la période (7 derniers jours à partir de la date max ou d'aujourd'hui)
reference_date = df_step['run_date'].max() 
seven_days_ago = reference_date - timedelta(days=6)

# Filtrage du dataframe
df_step_last_7d = df_step[(df_step['run_date'] >= seven_days_ago) & (df_step['project_id'] != "ADMIN")].copy()


# In[1489]:


df_step_last_7d['heure_exec'] = [x[11:16].replace('-',':') for x in df_step_last_7d.run_id]
df_step_last_7d['run_exec'] = [x[0:10] for x in df_step_last_7d.run_id]
df_step_last_7d.step_type = [x.replace('_',' ').upper().replace('FLOWITEM','') for x in df_step_last_7d.step_type]
df_step_last_7d['step_name_complete'] = df_step_last_7d.step_type + ' ' +df_step_last_7d.step_name 

df_step_last_7d['step_id_short'] = [x[0:30] for x in df_step_last_7d.step_name_complete]

df_step_last_7d.loc[(df_step_last_7d['step_type'] == 'COMPUTE METRICS') & (df_step_last_7d['step_result'] == 'FAILED'), 'error_category'] = 'Compute Metrics Error'
df_step_last_7d.loc[(df_step_last_7d['step_type'] == 'CHECK DATASET') & (df_step_last_7d['step_result'] == 'FAILED'), 'error_category'] = 'Dataset Metrics Error'
df_step_last_7d.loc[(df_step_last_7d['step_type'] == 'EXEC SQL') & (df_step_last_7d['step_result'] == 'FAILED'), 'error_category'] = 'BigQuery Error'
df_step_last_7d.loc[(df_step_last_7d['step_type'] == 'CUSTOM PYTHON') & (df_step_last_7d['step_result'] == 'FAILED'), 'error_category'] = 'Python Error'


# In[1490]:


df= df_step_last_7d#.head(10)


# # CSS style

# In[1491]:


html_content = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QA Analytics Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;500;700&display=swap" rel="stylesheet">
    <style>
    /* --- VARIABLES & BASE --- */
    :root {
        --primary: #4f46e5;
        --primary-light: #818cf8;
        --success: #10b981;
        --failed: #f43f5e;
        --warning: #f59e0b;
        /* Background Zinc (Gris chaud moderne) */
        --bg: #f4f4f5; 
        --card-bg: rgba(255, 255, 255, 0.8);
        --text: #09090b;
        --text-dim: #71717a;
        --border: rgba(228, 228, 231, 0.8);
        --shadow: 0 1px 3px rgba(0,0,0,0.02), 0 1px 2px rgba(0,0,0,0.04);
    }

    body {
        font-family: 'Inter', sans-serif;
        background-color: var(--bg);
        /* Gradient discret très actuel */
        background-image: 
            radial-gradient(at 0% 0%, rgba(79, 70, 229, 0.05) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.05) 0px, transparent 50%);
        color: var(--text);
        margin: 0;
        display: flex;
        min-height: 100vh;
        -webkit-font-smoothing: antialiased;
    }

    /* --- LAYOUT --- */
    main {
        flex: 1;
        padding: 10px 40px 40px;
        margin-left: 0;
    }

    .container {
        max-width: 95%;
        margin: 0 auto;
    }

    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        border-bottom: 1px solid var(--border);
        padding-bottom: 10px;
    }

    /* --- TYPOGRAPHY --- */
    h1 {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -1.5px;
        color: var(--text);
    }

    h1 span {
        color: var(--primary);
        font-weight: 300;
        text-transform: uppercase;
        font-size: 1.8rem;
        letter-spacing: 1px;
    }

    .subtitle {
        margin: 8px 0 0 0;
        color: var(--text-dim);
        font-size: 0.95rem;
        font-weight: 300;
    }

    /* --- COMPONENTS: CARDS & KPI --- */
    /* --- BENTO GRID CARDS --- */
    .kpi-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 16px;
        margin-bottom: 30px;
    }

    .card {
        background: var(--card-bg);
        backdrop-filter: blur(10px); /* Effet verre moderne */
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 24px;
        box-shadow: var(--shadow);
        display: flex;
        flex-direction: column;
        
        transition: all 0.2s ease;
    }

    .card:hover {
        transform: translateY(-2px);
        border-color: var(--primary-light);
        box-shadow: 0 10px 20px rgba(0,0,0,0.03);
    }

    .chart-card, .global-trend-card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 10px;
        position: relative;
        padding: 20px;
        box-shadow: var(--shadow);
    }

    .icon-box {
        position: absolute;
        top: 12px;
        right: 12px;
        background: rgba(0, 0, 0, 0.05);
        border-radius: 8px;
        width: 32px;
        height: 32px;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* --- FILTERS --- */
    .filter-bar {
        margin-bottom: 10px;
        display: flex;
        gap: 15px;
        align-items: center;
    }

    .row-filter, .search-input, .status-select {
        background: white !important;
        border: 1px solid var(--border);
        color: var(--text);
        padding: 10px 15px;
        border-radius: 12px;
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        outline: none;
        transition: all 0.2s;
    }
    
    .search-input, .status-select {
        background: var(--card-bg) !important;
        border: 1px solid var(--border);
        color: var(--text);
        padding: 10px 16px;
        border-radius: 10px;
        font-size: 0.9rem;
        outline: none;
        transition: all 0.2s;
    }

    .row-filter:focus, .search-input:focus, .status-select:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.1);
    }

    .status-select {
        cursor: pointer;
        min-width: 220px;

        -webkit-appearance: none;
        /* Flèche en Indigo foncé pour contraste */
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2318181b' stroke-width='2.5'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' d='M19.5 8.25l-7.5 7.5-7.5-7.5' /%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 12px center;
        background-size: 14px;
        padding-right: 40px;
    }

    .status-select:focus {
        border-color: var(--primary);
        background-color: #fff !important;
    }

    /* --- TABLE HIERARCHY --- */
    table { width: 100%; border-collapse: collapse; }
    th { text-align: left; color: var(--text-dim); font-size: 0.75rem; padding: 12px; border-bottom: 1px solid var(--border); }

    tr[class^="row-l"] { transition: background 0.2s; color: var(--text); }

    .row-l1 { cursor: pointer; background: white; border-top: 15px solid var(--bg) !important; }
    .row-l1:first-child { border-top: none !important; }
    .row-l1:hover { background: #f1f5f9 !important;}
    .row-l1 td { padding: 15px; font-weight: bold; border-bottom: 1px solid var(--border); }

    .row-l2 { border-left: 5px solid var(--secondary); display: none; background: #fafafa; }
    .row-l2 td { padding: 12px 15px 12px 40px; font-size: 0.95rem; }

    .row-l2bis { border-left: 5px solid var(--primary); display: none; }
    .row-l2bis td { padding: 10px 15px 10px 80px; font-size: 0.9rem; }

    .row-l3, .row-l4 { display: none; border-left: 5px solid #cbd5e1; background: #fcfcfc; }
    .row-l3 td { padding: 8px 15px 8px 120px; font-size: 0.85rem; color: var(--text-dim); }
    .row-l4 td { padding: 8px 15px 8px 160px; font-size: 0.85rem; color: var(--text-dim); }

    /* Status & Badges */
    .status { padding: 4px 10px; border-radius: 10px; font-size: 0.7rem; font-weight: bold; text-transform: uppercase; }
    .status.success, .SUCCESS { color: var(--success); background: #ecfdf5; border: 1px solid #a7f3d0; }
    .status.failed, .FAILED { color: var(--failed); background: #fef2f2; border: 1px solid #fecaca; }
    
    .status-critical { color: var(--failed) !important; font-weight: 700; }

    /* --- CHARTS & VISUALS --- */
    .chart-container { position: relative; width: 100%; height: 120px; margin-top: 15px; overflow: visible; }
    .chart-container svg { width: 100%; height: 100%; overflow: visible; display: block; }
    
    .polyline { 
        fill: none; stroke: var(--primary); stroke-width: 3; stroke-linecap: round; stroke-linejoin: round;
        stroke-dasharray: 1000; stroke-dashoffset: 1000; animation: draw 2s forwards ease-out;
        filter: drop-shadow(0px 4px 6px rgba(79, 70, 229, 0.2));
    }
    @keyframes draw { to { stroke-dashoffset: 0; } }

    .dot { fill: var(--primary); stroke: white; stroke-width: 2; cursor: pointer; transition: all 0.2s; }
    .dot:hover { r: 6; fill: var(--secondary); }

    .axis-label { font-size: 10px; fill: var(--text-dim); text-anchor: middle; }

    /* Heatmaps */
    .heatmap-container { display: flex; gap: 4px; align-items: center; }
    .heat-square { width: 80%; height: 12px; border-radius: 2px; cursor: help; transition: transform 0.1s; border: 1px solid rgba(0,0,0,0.05); }
    .heat-square:hover { transform: scale(1.3); }
    .heat-square:last-of-type { outline: 1.5px solid var(--primary); outline-offset: 1px; }

    .heatmap-30d { display: grid; grid-template-columns: repeat(30, 1fr); gap: 4px; width: 100%; margin-top: 10px; }
    .heat-square.large { width: 100%; height: 14px; }

    .heat-success, .heat-perfect { background-color: var(--success); }
    .heat-failed, .heat-critical { background-color: var(--failed); }
    .heat-warning { background-color: var(--warning); }
    .heat-NA, .heat-empty { background-color: #e2e8f0; }

    /* Calendar Specifics */
    .calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 6px; width: fit-content; margin: 5px auto; place-items: center; }
    .calendar-day { width: 18px; height: 18px; border-radius: 3px; transition: transform 0.2s; cursor: pointer; }
    .calendar-day:hover { transform: scale(1.3); z-index: 10; }

    /* UI Elements */
    .data-badge {
        background: white; border: 1px solid var(--border);
        padding: 8px 16px; border-radius: 50px; font-size: 0.8rem; color: var(--primary);
        display: flex; align-items: center; gap: 10px; box-shadow: var(--shadow);
    }

    .pulse-dot {
        width: 8px; height: 8px; background-color: var(--success); border-radius: 50%;
        animation: pulse 2s infinite;
    }
    @keyframes pulse { 
        0% { box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(5, 150, 105, 0); }
        100% { box-shadow: 0 0 0 0 rgba(5, 150, 105, 0); }
    }

    .toggle-icon { display: inline-block; width: 12px; transition: transform 0.3s; color: var(--primary); margin-right: 8px; font-size: 0.7rem; }
    .expanded .toggle-icon { transform: rotate(90deg); }
    .hidden { display: none !important; }

    #chart-tooltip {
        position: fixed; background: white; color: var(--text); padding: 8px 12px; border-radius: 8px;
        font-size: 0.75rem; pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 1000;
        border: 1px solid var(--border); box-shadow: 0 10px 15px rgba(0,0,0,0.1);
    }
    
    .stat-label {
        font-size: 0.8rem;
        font-weight: 600;
        color: var(--text-dim);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 8px;
    }
    .stat-label2 {
        font-size: 0.6rem;
        font-weight: 600;
        color: var(--text-dim);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 28px;
    }
    </style>
</head>"""


# # HTML

# ## Header + 30 d trend

# In[1492]:


html_content += """
<body>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" />
    <main>
    <div class="header-container">
        <div class="title-group">
            <h1>Project Quality Execution <span>Control Center</span></h1>
        </div>
        <div class="data-badge">
            <span class="pulse-dot"></span>
            Date: <span id="current-timestamp">{}</span>
        </div>
    </div>
    
        <div class="container">
            
            <div class="kpi-grid">
                
                <div class="card">
                    <div class="icon-box"><span class="material-symbols-outlined">folder_open</span></div>
                    <div class="stat-label" style="margin-right: 10px;"># Projects</div>
                    <div class="stat-label2" style="margin-right: 10px;">(last 7 days)</div>
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;"><span id="project-rate">{}</span></div>
                </div>
                <div class="card">
                    <div class="icon-box">
                        <span class="material-symbols-outlined">verified</span>
                    </div>
                    <div class="stat-label" style="margin-right: 10px;">Project Success Rate</div>
                    <div class="stat-label2" style="margin-right: 10px;">(last 7 days)</div>
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;"><span id="project-rate">{}%</span></div>
                </div>
                <div class="card">
                    <div class="icon-box">
                        <span class="material-symbols-outlined">query_stats</span>
                    </div>
                    <div class="stat-label" style="margin-right: 10px;">Scenario Success Rate</div>
                    <div class="stat-label2" style="margin-right: 10px;">(last 7 days)</div>
                    <div class="stat-value" style="font-size: 2.2rem; font-weight: bold;"><span id="scenario-rate">{}%</span></div>
                </div>

                <div class="card">
                    <div class="icon-box">
                        <span class="material-symbols-outlined">insights</span>
                    </div>
                    <span><i class="stats-icon" style="margin-right: 10px;"></i>Last 30 days trend</span>
                        {} 
                    </div>
                </div>
            </div>
            <div class="container">

    """.format(resultat,distinct_projects,round(avg_success_projects,1),round(avg_success_scenarios,1),calendar)


# ## drill down  data prep

# In[1493]:


html_rows = []

# --- NIVEAU 1 : PROJET (Agrégé) ---
for project_id, project_df in df.groupby('project_id', sort=False):
    total_runs = project_df['run_id'].nunique()
    failed_runs = project_df[project_df['run_status'] == 'FAILED']['run_id'].nunique()
    proj_status = "failed" if failed_runs > 0 else "success"

    
    # 1. Paramétrage des dates (7 derniers jours incluant aujourd'hui)
    today = pd.Timestamp.now().normalize()
    date_range = pd.date_range(end=today, periods=7, freq='D')

    # 2. On s'assure que la colonne de date du DataFrame est propre
    project_df['date_column'] = pd.to_datetime(project_df['run_exec']).dt.normalize()

    # 3. Agrégation avec ta logique (en groupant par DATE cette fois)
    # Si tu groupais par 'run_exec' (un ID), il est préférable de grouper par date 
    # pour voir les jours vides.
    summary_df = project_df.groupby('date_column')['run_status'].agg(
        lambda x: 'failed' if (x == 'FAILED').any() else 'success'
    ).reset_index()

    # 4. Création du référentiel vide et Fusion (Merge)
    template_df = pd.DataFrame({'date_column': date_range})
    final_df = pd.merge(template_df, summary_df, on='date_column', how='left')

    # 5. Remplacer les valeurs manquantes (NaN) par "NA"
    final_df['run_status'] = final_df['run_status'].fillna('NA')
    
    html_rows.append(f"""
    <tr class="row-l1" data-status="{proj_status}" onclick="toggleRow(this, 'row-l2')">
        <td><span class="toggle-icon">▶</span> <strong>{project_id}</strong></td>
        <td>---</td>
        <td><span class="status {proj_status}">{proj_status.capitalize()}</span></td>
        <td>
        <div class="heatmap-container">
        <span style="font-size: 0.7rem; margin-right: 5px; color: #94a3b8;">7d trend:</span>""")
      
    for row,value in final_df.iterrows():
         html_rows.append(f"""<div class="heat-square heat-{value.run_status}" title="{value.date_column.date()}: {value.run_status}"></div>""")
        

    html_rows.append(f"""      
        <span style="font-size: 0.6rem; color: var(--primary); margin-left: 2px;">Today</span> </div>
    </td>
    </tr>""")

    # --- NIVEAU 2 : SCÉNARIO ---
    for scenario_id, scenario_df in project_df.groupby('scenario_id', sort=False):
        # On calcule si le scénario a échoué sur l'une de ses dates
        scen_has_failed = (scenario_df['run_status'] == 'FAILED').any()
        scen_status = "failed" if scen_has_failed else "success"
        
        html_rows.append(f"""
        <tr class="row-l2" data-status="{scen_status}" onclick="toggleRow(this, 'row-l2bis')">
            <td style="padding-left: 40px;"><span class="toggle-icon">▶</span> {scenario_id}</td>
            <td>---</td>
            <td><span class="status {scen_status}">{scen_status.capitalize()}</span></td>
            <td>
                <div class="heatmap-container">
                <span style="font-size: 0.7rem; margin-right: 5px; color: #94a3b8;">7d trend:</span>""")
        
        summary_df = scenario_df.groupby('date_column')['run_status'].agg(
            lambda x: 'failed' if (x == 'FAILED').any() else 'success'
        ).reset_index()

        # 4. Création du référentiel vide et Fusion (Merge)
        template_df = pd.DataFrame({'date_column': date_range})
        final_df = pd.merge(template_df, summary_df, on='date_column', how='left')

        # 5. Remplacer les valeurs manquantes (NaN) par "NA"
        final_df['run_status'] = final_df['run_status'].fillna('NA')
        
        for row,value in final_df.iterrows():
            html_rows.append(f"""<div class="heat-square heat-{value.run_status}" title="{value.date_column.date()}: {value.run_status}"></div>""")

            
        html_rows.append("""<span style="font-size: 0.6rem; color: var(--primary); margin-left: 2px;">Today</span>
                </div>
            </td>
        </tr>""")
    
        scenario_df = scenario_df.sort_values('run_exec',ascending=False)
        # --- NIVEAU 1bis : DATE DU RUN ---
        for run_id, run_df in scenario_df.groupby('run_exec', sort=False):
            run_date_display = run_df['run_exec'].iloc[0]
            run_status = run_df['run_status'].min().lower()
            log_link = run_df['scenario_link'].iloc[0].replace('settings','runs/list')

            html_rows.append(f"""
            <tr class="row-l2bis" data-status="{run_status}" onclick="toggleRow(this, 'row-l3')" ">
                <td style="padding-left: 80px;"><span class="toggle-icon">▶</span> {run_date_display}</td>
                <td>-</td>
                <td><span class="status {run_status}">{run_status.capitalize()}</span></td>
                <td><a href="{log_link}" target="_blank" style="color:var(--primary)">🔗 Logs (right click + Open)</a></td>
            </tr>""")

            run_df = run_df.sort_values('heure_exec',ascending=True)

            # --- NIVEAU 2bis : DATE D EXEC ---
            for run_id, run_df in run_df.groupby('heure_exec', sort=False):
                run_date_display = run_df['heure_exec'].iloc[0]
                run_status = run_df['run_status'].min().lower()
                log_link = run_df['scenario_link'].iloc[0].replace('settings','runs/list')

                html_rows.append(f"""
                <tr class="row-l3" data-status="{run_status}" onclick="toggleRow(this, 'row-l4')" ">
                    <td style="padding-left: 120px;"><span class="toggle-icon">▶</span> Execution of {run_date_display}</td>
                    <td>{run_df['heure_exec'].iloc[0]}</td>
                    <td><span class="status {run_status}">{run_status.capitalize()}</span></td>
                    <td><a href="{log_link}" target="_blank" style="color:var(--primary)"> Logs (right click + Open)</a></td>
                </tr>""")

                run_df = run_df.sort_values('step_order',ascending=True)

                # --- NIVEAU 3 : STEPS ---
                for _, step in run_df.iterrows():
                    step_res = "success" if step['step_result'].upper() == 'SUCCESS' else "failed"
                    step_class = step_res.lower()
                    step_time = step['monitoring_timestamp'].strftime('%H:%M:%S')
                    error_detail = step['error_category'] if pd.notna(step['error_category']) else ""

                    html_rows.append(f"""
                    <tr class="row-l4">
                        <td style="padding-left: 160px; font-size: 0.9em; ">└ {step['step_id_short']}</td>
                        <td>-</td>
                        <td><span class="status {step_class}">{step_res}</span></td>
                        <td>{error_detail}</td>
                    </tr>""")


# ## drill down HTML + JS

# In[1494]:


html_content += """
            

            <div class="filter-bar">
                <input type="text" id="projSearch" class="search-input" placeholder="Search project..." onkeyup="filterData()">
                <select id="statusFilter" class="status-select" onchange="filterData()">
                    <option value="all">All status</option>
                    <option value="success">Success</option>
                    <option value="failed">Failed</option>
                    <option value="critical-trend">⚠️ Today's & yesterday's failures </option>
                </select>
            </div>

            <div class="card" style="padding:0">
                <table id="masterTable">
                    <thead>
                        <tr>
                            <th>Projet / Scénario / Step</th>
                            <th>Date</th>
                            <th>Status</th>
                            <th>Info / Error</th>
                        </tr>
                    </thead>
                    <tbody> """

html_content += "\n".join(html_rows)

html_content +="""
                </table>
            </div>
        </div>
        </div>
    </main>

    <script>
        // FONCTION DE FILTRAGE NOM + STATUS
        function filterData() {
            const searchTerm = document.getElementById('projSearch').value.toLowerCase();
            const statusFilter = document.getElementById('statusFilter').value;
            const rows = document.querySelectorAll('#masterTable tbody .row-l1');

            rows.forEach(row => {
                const projectName = row.querySelector('td').textContent.toLowerCase();
                const projectStatus = row.getAttribute('data-status');

                // Extraction des statuts des 2 derniers jours depuis la heatmap
                const heatSquares = row.querySelectorAll('.heat-square');
                const lastIndex = heatSquares.length - 1;

                // On vérifie Today (dernier) et Yesterday (avant-dernier)
                const failedToday = heatSquares[lastIndex]?.classList.contains('heat-failed');
                const failedYesterday = heatSquares[lastIndex - 1]?.classList.contains('heat-failed');

                // Logique de filtrage
                let matchesSearch = projectName.includes(searchTerm);
                let matchesStatus = false;

                if (statusFilter === 'all') {
                    matchesStatus = true;
                } else if (statusFilter === 'critical-trend') {
                    // Filtre spécifique : échec hier ET aujourd'hui
                    matchesStatus = failedToday || failedYesterday;
                } else {
                    matchesStatus = (projectStatus === statusFilter);
                }

                // Affichage ou masquage
                if (matchesSearch && matchesStatus) {
                    row.style.display = "";
                } else {
                    row.style.display = "none";
                    // Fermer les détails (L2, L3) si le parent est masqué
                    const nextRows = getNextRows(row);
                    nextRows.forEach(r => r.style.display = "none");
                    row.classList.remove('expanded');
                }
            });
        }

        // Fonction utilitaire pour masquer les sous-lignes
        function getNextRows(row) {
            let nextRows = [];
            let next = row.nextElementSibling;
            while (next && !next.classList.contains('row-l1')) {
                nextRows.push(next);
                next = next.nextElementSibling;
            }
            return nextRows;
        }

        // GESTION DE L'ACCORDEON IMBRIQUÉ
        function toggleRow(row, targetClass) {
            row.classList.toggle('expanded');
            let next = row.nextElementSibling;
            const currentLevel = row.classList[0];

            while (next) {
                // Condition d'arrêt : on s'arrête si on tombe sur un voisin du même niveau 
                // ou un parent d'un niveau supérieur.
                if (isSameOrHigherLevel(currentLevel, next)) break;

                if (next.classList.contains(targetClass)) {
                    if (row.classList.contains('expanded')) {
                        next.style.display = 'table-row';
                    } else {
                        next.style.display = 'none';
                        next.classList.remove('expanded');
                        closeChildren(next); // Récursivité pour fermer les sous-niveaux
                    }
                }
                next = next.nextElementSibling;
            }
        }

        function closeChildren(row) {
            let next = row.nextElementSibling;
            const currentLevel = row.classList[0];

            while (next) {
                // On s'arrête dès qu'on sort de la section du parent actuel
                if (isSameOrHigherLevel(currentLevel, next)) break;

                next.style.display = 'none';
                next.classList.remove('expanded');
                next = next.nextElementSibling;
            }
        }

        // Fonction utilitaire pour comparer les niveaux de hiérarchie
        function isSameOrHigherLevel(currentLevel, nextRow) {
            const levels = ['row-l1', 'row-l2', 'row-l2bis', 'row-l3', 'row-l4'];
            const currentIndex = levels.indexOf(currentLevel);

            // On vérifie si la ligne suivante a une classe de niveau supérieur ou égal
            return levels.some((level, index) => {
                return index <= currentIndex && nextRow.classList.contains(level);
            });
        }
        
        document.getElementById('toggleChartBtn').addEventListener('click', function() {
            const chartCard = document.querySelector('.chart-card');
            const btnText = document.getElementById('btnText');
            const btnIcon = document.getElementById('btnIcon');

            // Bascule de la classe hidden
            chartCard.classList.toggle('hidden');

            // Mise à jour du texte et de l'icône
            if (chartCard.classList.contains('hidden')) {
                btnText.textContent = "Show Analytics";
                btnIcon.textContent = "📊";
            } else {
                btnText.textContent = "Hide Analytics";
                btnIcon.textContent = "👁️‍🗨️";
            }
        })
        
        function checkSuccessRates() {
            const ids = ['project-rate', 'scenario-rate'];

            ids.forEach(id => {
                const element = document.getElementById(id);
                if (element) {
                    const value = parseInt(element.textContent);
                    if (value < 100) {
                        element.classList.add('status-critical');
                    } else {
                        element.classList.remove('status-critical');
                    }
                }
            });
        }

        // Appeler la fonction au chargement
        checkSuccessRates()
    </script>
</body>
</html>""" 


# # export

# In[1495]:


chart_prices_insight = base64.b64encode(html_content.encode("utf-8"))
dataiku.insights.save_data("Monitoring_view", payload=chart_prices_insight, content_type= 'text/html' , label=None, encoding='base64')


# In[1496]:


# print(html_content)

