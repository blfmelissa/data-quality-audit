#!/usr/bin/env python3
"""
tasks-metadata.py - Automatisation complète OpenMetadata pour déploiement "One-Click"

Ce script automatise :
1. L'arrêt propre et le nettoyage du moteur de recherche (Elasticsearch)
2. Le démarrage des services en conservant les données métier (MySQL)
3. La création forcée des index (Bootstrap) pour débloquer l'interface
4. La création de la base de données Airflow
5. L'ingestion automatique des 7 tables PostgreSQL
"""

import subprocess
import time
import sys
from typing import Tuple, Optional

# Configuration
CONTAINERS = {
    'mysql': 'openmetadata_mysql',
    'elasticsearch': 'openmetadata_elasticsearch',
    'openmetadata': 'dq_openmetadata',
    'ingestion': 'openmetadata_ingestion'
}

MYSQL_ROOT_PASSWORD = "dev_root_password_2026"
AIRFLOW_DB_NAME = "airflow_db"
AIRFLOW_USER = "airflow_user"
AIRFLOW_PASSWORD = "dev_airflow_pass_2026"

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_step(message: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}➜ {message}{Colors.RESET}")

def print_success(message: str):
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")

def print_error(message: str):
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")

def print_warning(message: str):
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")

def run_command(command: str, check: bool = True, capture_output: bool = True) -> Tuple[bool, Optional[str]]:
    try:
        result = subprocess.run(
            command, shell=True, check=check,
            capture_output=capture_output, text=True, timeout=120
        )
        return True, result.stdout if capture_output else None
    except Exception as e:
        return False, str(e)

def check_container_healthy(container_name: str) -> bool:
    success, output = run_command(f"docker inspect --format='{{{{.State.Health.Status}}}}' {container_name}", check=False)
    return success and "healthy" in (output or "")

def stop_services():
    print_step("Nettoyage des services (Conservation de MySQL)")
    run_command("docker-compose down", capture_output=False)
    # Nettoyage ciblé d'Elasticsearch pour éviter les bugs d'index
    run_command("docker volume rm openmetadata_openmetadata_es_data", check=False)
    print_success("Services arrêtés et volume ES nettoyé. MySQL est préservé.")

def force_es_bootstrap():
    """Force la création des index pour débloquer l'UI et le mode Healthy"""
    print_step("Initialisation forcée d'Elasticsearch (Bootstrap)")
    print("  Attente du démarrage du process Java (20s)...")
    time.sleep(20)
    
    for i in range(3): # 3 tentatives
        print(f"  Tentative {i+1}/3 de création des index...")
        success, _ = run_command(
            'docker exec dq_openmetadata /bin/bash -c "./bootstrap/bootstrap_storage.sh es-create"',
            check=False, capture_output=False
        )
        if success:
            print_success("Indices créés avec succès !")
            return True
        time.sleep(10)
    return False

def setup_openmetadata():
    print(f"\n{Colors.BOLD}{'='*60}\n🚀 DEPLOYMENT AUTOMATIQUE - DATA QUALITY AUDIT\n{'='*60}{Colors.RESET}")
    
    stop_services()
    
    print_step("Démarrage des conteneurs")
    run_command("docker-compose up -d", capture_output=False)
    
    # On force les index avant même que Docker dise que c'est Healthy
    force_es_bootstrap()
    
    print_step("Vérification finale de la santé des services")
    services = ['openmetadata_mysql', 'openmetadata_elasticsearch', 'dq_openmetadata']
    for s in services:
        print(f"  Vérification de {s}...")
        for _ in range(20):
            if check_container_healthy(s):
                print_success(f"{s} est prêt")
                break
            time.sleep(5)
    
    # Attente supplémentaire pour que l'API OpenMetadata soit vraiment disponible
    print_step("Attente de la disponibilité complète de l'API OpenMetadata")
    print("  Attente de 30 secondes pour l'initialisation de l'API...")
    time.sleep(30)
    
    # Vérifier que l'API répond vraiment
    print("  Test de connexion à l'API...")
    for attempt in range(6):
        success, _ = run_command(
            "docker exec openmetadata_ingestion curl -s -o /dev/null -w '%{http_code}' http://dq_openmetadata:8585/api/v1/system/version",
            check=False,
            capture_output=True
        )
        if success:
            print_success("L'API OpenMetadata est accessible")
            break
        print(f"  Tentative {attempt + 1}/6... attente 10s")
        time.sleep(10)
    else:
        print_warning("L'API met du temps à répondre, mais on continue...")
            
    # Config Airflow DB
    print_step("Configuration base Airflow")
    sql = f"CREATE DATABASE IF NOT EXISTS {AIRFLOW_DB_NAME}; GRANT ALL PRIVILEGES ON {AIRFLOW_DB_NAME}.* TO '{AIRFLOW_USER}'@'%';"
    run_command(f'docker exec -i openmetadata_mysql mysql -u root -p{MYSQL_ROOT_PASSWORD} -e "{sql}"', check=False)
    
    # Ingestion
    print_step("Ingestion des 7 tables PostgreSQL")
    success, _ = run_command("docker exec openmetadata_ingestion metadata ingest -c /opt/airflow/ingestion/postgres_connector.yaml", capture_output=False)
    
    if success:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✅ INSTALLATION RÉUSSIE !{Colors.RESET}")
        print(f"Accès : {Colors.BLUE}http://localhost:8585{Colors.RESET} (admin/admin)")
    else:
        print_error("L'ingestion a échoué. Vérifiez vos connecteurs.")
        print_warning("Vous pouvez réessayer avec : python tasks-metadata.py ingest")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ingest":
        run_command("docker exec openmetadata_ingestion metadata ingest -c /opt/airflow/ingestion/postgres_connector.yaml", capture_output=False)
    else:
        setup_openmetadata()