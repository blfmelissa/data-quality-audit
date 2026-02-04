#!/usr/bin/env python3
"""
tasks.py - Pipeline Data Quality amélioré
Usage:
    python tasks.py <task>
Tâches disponibles:
    docker      : Vérifier Docker et démarrer les services
    load        : Charger les données dans PostgreSQL
    notebooks   : Exécuter les notebooks d'analyse/nettoyage
    reports     : Générer les rapports Evidently/Sweetviz
    validate    : Lancer la validation Great Expectations
    all         : Tout exécuter (docker -> load -> notebooks -> reports -> validate)
    clean       : Nettoyer les fichiers générés et arrêter Docker
"""

import subprocess
import sys
import os
from datetime import datetime
import shutil
import time

# Couleurs terminal
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"

# Configuration du logging
LOG_FILE = "pipeline.log"

def log(message, level="INFO"):
    """Écrit dans le fichier de log et affiche à l'écran"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] [{level}] {message}"
    
    # Écriture dans le fichier
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_message + "\n")
    
    # Affichage 
    if level == "ERROR":
        print(f"{RED}{message}{NC}")
    elif level == "SUCCESS":
        print(f"{GREEN}{message}{NC}")
    elif level == "WARNING":
        print(f"{YELLOW}{message}{NC}")
    else:
        print(message)


# Création des dossiers nécessaires
for folder in ["data/Silver", "data/Gold", "reports"]:
    os.makedirs(folder, exist_ok=True)

# Fonction utilitaire
def run(cmd, check=True):
    """Execute une commande shell et affiche les erreurs si besoin"""
    log(f"⏳ Running: {cmd}", "INFO")
    start_time = datetime.now()
    
    result = subprocess.run(cmd, shell=True)
    
    duration = (datetime.now() - start_time).total_seconds()
    
    if check and result.returncode != 0:
        log(f"❌ Command failed: {cmd} (duration: {duration:.2f}s)", "ERROR")
        sys.exit(1)
    
    log(f"✅ Done (duration: {duration:.2f}s)", "SUCCESS")
    return result

# Étapes pipeline

def docker_up():
    """Vérifie Docker et Docker Compose, puis démarre les services"""
    log("🐳 Vérification de Docker...", "INFO")
    
    try:
        subprocess.run("docker ps", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log("✅ Docker est actif", "SUCCESS")
    except subprocess.CalledProcessError:
        log("❌ Docker n'est pas démarré !", "ERROR")
        log("Lancez Docker Desktop puis réessayez.", "WARNING")
        sys.exit(1)

    try:
        subprocess.run("docker-compose --version", shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log("✅ Docker Compose est installé", "SUCCESS")
    except subprocess.CalledProcessError:
        log("❌ Docker Compose non trouvé !", "ERROR")
        sys.exit(1)

    run("docker-compose up -d")
    log("✅ PostgreSQL démarre (healthcheck actif)", "SUCCESS")

def setup_superset():
    """Initialise Apache Superset avec réinstallation forcée de pip et du driver"""
    log("📊 Configuration de Superset (Mode Robuste)...", "INFO")
    
    log("📥 Installation forcée de pip...", "INFO")
    pip_install_cmd = (
        'docker exec -u root superset bash -c '
        '"apt-get update && apt-get install -y curl && '
        'curl -sS https://bootstrap.pypa.io/get-pip.py | python3"'
    )
    run(pip_install_cmd)
    
    log("🔌 Installation du driver psycopg2...", "INFO")
    run("docker exec -u root superset python3 -m pip install psycopg2-binary")
    
    log("⚙️ Initialisation de la base interne Superset...", "INFO")
    run("docker exec superset superset db upgrade")
    run("docker exec superset superset fab create-admin --username admin --firstname Admin --lastname User --email admin@superset.com --password admin", check=False)
    run("docker exec superset superset init")

    conn_cmd = (
        "docker exec superset superset set_database_uri "
        "--database_name DataQualitySteamDB "
        "--uri postgresql+psycopg2://postgres:postgres@postgres:5432/games_db"
    )
    run(conn_cmd)
    log("Superset est prêt et connecté sur http://localhost:8088", "SUCCESS")

def load_data():
    """Charge les données dans PostgreSQL via Docker"""
    log("📥 Chargement des données dans PostgreSQL...", "INFO")
    path = "scripts/load_data_docker.py"
    if not os.path.exists(path):
        log(f"❌ {path} non trouvé !", "ERROR")
        sys.exit(1)
    run(f"docker exec dq_jupyter python /home/jovyan/work/scripts/load_data_docker.py")

def run_notebooks():
    """Exécute les notebooks d'analyse et de nettoyage"""
    log("📓 Exécution des notebooks...", "INFO")
    notebooks = [
        "01_analyse_manuelle.ipynb",
        "02_nettoyage.ipynb",
        "03_validation.ipynb"
    ] 
    for nb in notebooks:
        local_path = f"notebooks/{nb}"
        docker_path = f"/home/jovyan/work/notebooks/{nb}"
        if os.path.exists(local_path):
            log(f"📓 Exécution {nb}", "INFO")
            run(f"docker exec dq_jupyter jupyter nbconvert --to notebook --execute {docker_path} --inplace")
        else:
            log(f"⚠️  Notebook {nb} non trouvé, étape ignorée", "WARNING")

def generate_reports():
    """Exécute le script Python pour les rapports Evidently + Sweetviz"""
    log("📊 Génération des rapports...", "INFO")
    script_path = "scripts/generate_reports.py"
    if os.path.exists(script_path):
        run(f"docker exec dq_jupyter python /home/jovyan/work/scripts/generate_reports.py")
    else:
        log(f"⚠️  Script de génération des rapports non trouvé, étape ignorée", "WARNING")

def validate():
    """Exécute la validation Great Expectations"""
    log("✅ Validation Great Expectations...", "INFO")
    path = "scripts/run_validation.py"
    if os.path.exists(path):
        run(f"docker exec dq_jupyter python /home/jovyan/work/scripts/run_validation.py")
    else:
        log(f"⚠️  Script run_validation.py non trouvé, étape ignorée", "WARNING")

def clean():
    """Nettoie les dossiers de données, supprime les rapports et arrête Docker."""
    log("🧹 Nettoyage des fichiers générés...", "INFO")

    # Dossiers à nettoyer
    folders = ["data/Silver", "data/Gold", "reports"]
    
    # Supprimer les dossiers et leur contenu
    for folder in folders:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                log(f"✅ Dossier supprimé: {folder}", "SUCCESS")
                # Recréer le dossier vide
                os.makedirs(folder, exist_ok=True)
            except Exception as e:
                log(f"❌ Erreur suppression {folder}: {e}", "ERROR")
    
    # Supprimer le fichier de log (sauf celui en cours)
    if os.path.exists(LOG_FILE):
        try:
            # Renommer le log actuel avant de le supprimer
            backup_log = f"pipeline_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            shutil.copy(LOG_FILE, backup_log)
            log(f"📋 Log sauvegardé dans {backup_log}", "INFO")
        except Exception as e:
            log(f"⚠️  Impossible de sauvegarder le log: {e}", "WARNING")

    log("🛑 Arrêt des services Docker...", "INFO")
    run("docker-compose down")
    
    log("🧹 Nettoyage complet terminé !", "SUCCESS")

def all_tasks():
    """Exécute toutes les tâches du pipeline dans l'ordre"""
    start_time = datetime.now()
    log("=" * 60, "INFO")
    log("🚀 DÉMARRAGE DU PIPELINE COMPLET", "INFO")
    log("=" * 60, "INFO")
    
    try:
        docker_up()
        setup_superset()
        load_data()
        run_notebooks()
        generate_reports()
        validate()
        
        duration = (datetime.now() - start_time).total_seconds()
        log("=" * 60, "INFO")
        log(f"🎉 PIPELINE TERMINÉ AVEC SUCCÈS (durée totale: {duration:.2f}s)", "SUCCESS")
        log("=" * 60, "INFO")
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        log("=" * 60, "INFO")
        log(f"❌ PIPELINE ÉCHOUÉ (durée: {duration:.2f}s)", "ERROR")
        log(f"Erreur: {e}", "ERROR")
        log("=" * 60, "INFO")
        sys.exit(1)


# -------------------------
# Mapping des tâches
# -------------------------
tasks = {
    "docker": docker_up,
    "superset": setup_superset,
    "load": load_data,
    "notebooks": run_notebooks,
    "reports": generate_reports,
    "validate": validate,
    "clean": clean,
    "all": all_tasks,
}

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    if len(sys.argv) < 2:
        log(f"Usage: python tasks.py <task>", "ERROR")
        print(f"Tâches disponibles: {', '.join(tasks.keys())}")
        sys.exit(1)

    task_name = sys.argv[1].lower()
    if task_name not in tasks:
        log(f"❌ Tâche inconnue: {task_name}", "ERROR")
        print(f"Tâches disponibles: {', '.join(tasks.keys())}")
        sys.exit(1)

    # Mesure du temps d'exécution de la tâche
    task_start = datetime.now()
    log(f"\n{'='*60}", "INFO")
    log(f"🚀 Démarrage de la tâche: {task_name}", "INFO")
    log(f"{'='*60}\n", "INFO")
    
    tasks[task_name]()
    
    task_duration = (datetime.now() - task_start).total_seconds()
    log(f"\n{'='*60}", "INFO")
    log(f"✅ Tâche '{task_name}' terminée en {task_duration:.2f}s", "SUCCESS")
    log(f"{'='*60}\n", "INFO")
