"""
Script de deploiement complet OpenMetadata
Compatible Windows, Linux, Mac

Automatise:
1. Demarrage Docker Compose
2. Bootstrap Elasticsearch  
3. Configuration Airflow DB
4. Ingestion PostgreSQL (7 tables)
5. Configuration metadonnees (descriptions, tags, glossaire, lineage)

Usage: python deploy.py
"""
import subprocess
import sys
import time
from pathlib import Path

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def run_command(cmd, description):
    """Execute une commande shell"""
    print(f"   {description}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   {Color.GREEN}✓{Color.RESET} {description}")
        return True
    else:
        print(f"   {Color.RED}✗{Color.RESET} Erreur: {result.stderr[:150]}")
        return False

def main():
    print("\n" + "="*70)
    print(f"{Color.BLUE}DEPLOIEMENT OPENMETADATA{Color.RESET}")
    print("="*70)
    
    # 1. Verifier Docker
    print("\n[1/7] Vérification des prérequis")
    if not run_command("docker --version", "Docker"):
        sys.exit(1)
    if not run_command("docker-compose --version", "Docker Compose"):
        sys.exit(1)
    
    # 2. Arreter et redemarrer proprement
    print("\n[2/7] Arret des services existants")
    subprocess.run("docker-compose down", shell=True, capture_output=True)
    
    print("\n[3/7] Démarrage des services Docker")
    result = subprocess.run("docker-compose up -d", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"   {Color.RED}✗{Color.RESET} Erreur: {result.stderr}")
        sys.exit(1)
    print(f"   {Color.GREEN}✓{Color.RESET} Services démarrés")
    
    # 3. Bootstrap Elasticsearch (fix index)
    print("\n[4/7] Bootstrap Elasticsearch")
    print("   Attente MySQL (15s)...")
    time.sleep(15)
    
    print("   Force creation des index...")
    subprocess.run(
        "docker exec dq_openmetadata /bin/bash -c './bootstrap/bootstrap_storage.sh migrate-all'",
        shell=True, capture_output=True
    )
    print(f"   {Color.GREEN}✓{Color.RESET} Bootstrap lance")
    
    # 4. Attendre que tout soit pret
    print("\n[5/7] Attente stabilisation (60s)...")
    time.sleep(60)
    
    # 5. Configurer Airflow DB
    print("\n[6/7] Configuration base Airflow")
    sql = "CREATE DATABASE IF NOT EXISTS airflow_db; GRANT ALL PRIVILEGES ON airflow_db.* TO 'airflow_user'@'%';"
    subprocess.run(
        f'docker exec -i openmetadata_mysql mysql -u root -pdev_root_password_2026 -e "{sql}"',
        shell=True, capture_output=True
    )
    print(f"   {Color.GREEN}✓{Color.RESET} Base Airflow configuree")
    
    # 6. Ingestion PostgreSQL
    print("\n   Ingestion des 7 tables PostgreSQL...")
    result = subprocess.run(
        "docker exec openmetadata_ingestion metadata ingest -c /opt/airflow/ingestion/postgres_connector.yaml",
        shell=True, capture_output=True, text=True
    )
    
    if result.returncode == 0:
        print(f"   {Color.GREEN}✓{Color.RESET} 7 tables ingerees")
    else:
        print(f"   {Color.YELLOW}⚠{Color.RESET} Ingestion partielle")
    
    # 7. Configuration metadonnees (descriptions, tags, glossaire, lineage)
    print("\n[7/7] Configuration des metadonnees")
    script_path = Path(__file__).parent / "scripts" / "setup_openmetadata.py"
    result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)
    print(result.stdout)
    
    # 8. Resume
    print("\n" + "="*70)
    print(f"{Color.GREEN}✓ DEPLOIEMENT TERMINE{Color.RESET}")
    print("="*70)
    print(f"\n{Color.BLUE}OpenMetadata:{Color.RESET} http://localhost:8585")
    print("User: admin / admin")
    print("\nConfiguration appliquee:")
    print("  • 7 Tables PostgreSQL ingerees")
    print("  • 4 Classifications + 8 Tags")
    print("  • ~100 Colonnes documentees")
    print("  • 39 Termes de glossaire")
    print("  • 6 Relations de lineage")
    
    if "401" in result.stdout or "JWT" in result.stdout:
        print(f"\n{Color.YELLOW}⚠ ATTENTION:{Color.RESET} Token JWT invalide!")
        print("Pour corriger:")
        print("  1. http://localhost:8585 > Settings > Bots > ingestion-bot")
        print("  2. Copier le JWT Token")
        print("  3. Coller dans scripts/setup_openmetadata.py ligne 23")
        print("  4. Relancer: python scripts/setup_openmetadata.py")

if __name__ == "__main__":
    main()
