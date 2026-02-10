#!/usr/bin/env python3
"""
generate_reports.py
Génère automatiquement les rapports de qualité des données avec :
- Evidently : Rapport de qualité détaillé avec métriques avancées
- Sweetviz : Analyse exploratoire visuelle interactive
Les rapports sont sauvegardés dans le dossier 'reports/' avec timestamp.
"""

import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
import os
from evidently.legacy.report import Report
from evidently.legacy.metric_preset import DataQualityPreset
import sweetviz as sv
from datetime import datetime

# Déterminer le répertoire de base (parent du dossier scripts)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

# Création du dossier reports (si nécessaire)
os.makedirs(REPORTS_DIR, exist_ok=True)
print(f"Répertoire des rapports : {REPORTS_DIR}")

# Charger la configuration depuis .env
load_dotenv(os.path.join(BASE_DIR, ".env"))  

DB_HOST = os.getenv('DB_HOST', 'host.docker.internal')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'games_db')
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
print(f"Connexion à PostgreSQL : {DB_HOST}:{DB_PORT}/{DB_NAME} avec utilisateur {DB_USER}")

# Charger les données
try:
    engine = create_engine(CONNECTION_STRING)
    df = pd.read_sql("SELECT * FROM games_brut", engine)
    print(f"Données chargées : {df.shape[0]} lignes, {df.shape[1]} colonnes")
except Exception as e:
    print(f"Erreur lors du chargement des données : {e}")
    df = None

# Génération du rapport Evidently
if df is not None:
    try:
        print("Génération du rapport Evidently...")
        report = Report(metrics=[DataQualityPreset()])
        report.run(current_data=df, reference_data=None)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        evidently_file = os.path.join(REPORTS_DIR, f"evidently_data_quality_report_{timestamp}.html")
        report.save_html(evidently_file)
        print(f"✅ Rapport Evidently sauvegardé : {evidently_file}")
    except Exception as e:
        print(f"Erreur Evidently : {e}")
else:
    print("Pas de données à analyser pour Evidently")

# Génération du rapport Sweetviz
if df is not None:
    try:
        print("Génération du rapport Sweetviz...")
        sv_report = sv.analyze(df)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sweetviz_file = os.path.join(REPORTS_DIR, f"sweetviz_report_{timestamp}.html")
        sv_report.show_html(sweetviz_file, open_browser=False)
        print(f"✅ Rapport Sweetviz sauvegardé : {sweetviz_file}")
    except Exception as e:
        print(f"Erreur Sweetviz : {e}")
else:
    print("Pas de données à analyser pour Sweetviz")
