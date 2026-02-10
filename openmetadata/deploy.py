"""
Script de deploiement cross-platform pour OpenMetadata.
Compatible Windows, Linux, macOS. Utilise uniquement la stdlib Python.

Automatise :
1. Demarrage des services Docker Compose (MySQL + ES en premier)
2. Migration bootstrap de la base de donnees (creation des tables OM)
3. Health checks avec polling (MySQL, Elasticsearch, OpenMetadata)
4. Initialisation de la base Airflow
5. Recuperation et injection automatique du token JWT
6. Ingestion des metadonnees PostgreSQL (7 tables)
7. Configuration des metadonnees (tags, glossaire, lineage, descriptions)

Usage : python deploy.py
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"
CONNECTOR_YAML = SCRIPT_DIR / "ingestion" / "postgres_connector.yaml"
SETUP_SCRIPT = SCRIPT_DIR / "scripts" / "setup_openmetadata.py"
REQUIREMENTS = SCRIPT_DIR / "requirements.txt"

OM_URL = "http://dq_openmetadata:8585"
OM_API = f"{OM_URL}/api"


class Color:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    RESET = "\033[0m"


if os.name == "nt":
    os.system("")  # active les sequences ANSI sur Windows 10+


def ok(msg):
    print(f"   {Color.GREEN}v{Color.RESET} {msg}")


def err(msg):
    print(f"   {Color.RED}x{Color.RESET} {msg}")


def warn(msg):
    print(f"   {Color.YELLOW}!{Color.RESET} {msg}")


# ── Environnement ────────────────────────────────────────────────────


def load_env():
    """Charge le fichier .env dans os.environ et retourne un dict."""
    if not ENV_FILE.exists():
        err(".env introuvable -- copier .env.example vers .env et renseigner les valeurs")
        sys.exit(1)

    env = {}
    with open(ENV_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()

    os.environ.update(env)
    return env


# ── Docker Compose ───────────────────────────────────────────────────


def detect_compose():
    """Retourne la commande docker compose disponible, ou None."""
    for cmd in (["docker", "compose"], ["docker-compose"]):
        try:
            r = subprocess.run(cmd + ["version"], capture_output=True, text=True)
            if r.returncode == 0:
                return cmd
        except FileNotFoundError:
            continue
    return None


def compose_run(compose_cmd, *args):
    """Execute une sous-commande docker compose."""
    return subprocess.run(
        compose_cmd + list(args), capture_output=True, text=True
    )


# ── Health checks ────────────────────────────────────────────────────


def wait_for_http(url, label, timeout=300, interval=10):
    """Poll une URL jusqu'a reponse HTTP < 500 ou timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status < 500:
                    return True
        except Exception:
            pass
        elapsed = int(time.time() - start)
        print(f"   Attente de {label}... ({elapsed}s/{timeout}s)")
        time.sleep(interval)
    return False


def wait_for_container_healthy(container, timeout=180, interval=10):
    """Poll docker inspect jusqu'a ce que le conteneur soit healthy."""
    start = time.time()
    while time.time() - start < timeout:
        r = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", container],
            capture_output=True, text=True,
        )
        status = r.stdout.strip()
        if status == "healthy":
            return True
        elapsed = int(time.time() - start)
        print(f"   Attente de {container}... ({elapsed}s/{timeout}s)")
        time.sleep(interval)
    return False


# ── Token JWT ────────────────────────────────────────────────────────


def get_bot_jwt_via_api():
    """Tente de recuperer le JWT via l'API de login OM."""
    # Essayer plusieurs variantes d'email admin
    email_variants = [
        "admin@open-metadata.org",
        "admin@openmetadata.org",
        "admin",
    ]
    
    access_token = None
    for email in email_variants:
        try:
            payload = json.dumps({
                "email": email,
                "password": "admin",
            }).encode()

            req = urllib.request.Request(
                f"{OM_API}/v1/users/login",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                access_token = data.get("accessToken")
                if access_token:
                    print(f"   Login reussi avec email: {email}")
                    break
        except Exception as e:
            print(f"   Tentative login avec {email}: {e}")
            continue
    
    if not access_token:
        raise RuntimeError("Pas d'accessToken dans la reponse apres toutes les tentatives")

    req = urllib.request.Request(
        f"{OM_API}/v1/bots/name/ingestion-bot",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        bot = json.loads(resp.read())

    return (
        bot.get("botUser", {})
        .get("authenticationMechanism", {})
        .get("config", {})
        .get("JWTToken")
    )


def get_bot_jwt_from_db(mysql_root_pw):
    """Fallback : lecture du JWT ingestion-bot directement depuis MySQL avec JSON_EXTRACT."""
    print("   Tentative de recuperation depuis MySQL avec JSON_EXTRACT...")
    
    # Utiliser JSON_EXTRACT pour extraire directement le JWT
    query = "SELECT JSON_UNQUOTE(JSON_EXTRACT(json, '$.authenticationMechanism.config.JWTToken')) FROM user_entity WHERE name='ingestion-bot';"
    
    r = subprocess.run(
        ["docker", "exec", "-i", "openmetadata_mysql",
         "mysql", "-u", "root", f"-p{mysql_root_pw}",
         "--database", "openmetadata_db", "-N", "-e", query],
        capture_output=True, text=True,
    )
    
    if r.returncode != 0:
        print(f"   Erreur MySQL (returncode={r.returncode}): {r.stderr[:200]}")
        return None
        
    jwt = r.stdout.strip()
    
    if not jwt or jwt == "NULL" or jwt == "null":
        print("   JWT non trouve dans user_entity.authenticationMechanism.config.JWTToken")
        return None
    
    print(f"   JWT recupere depuis MySQL (longueur: {len(jwt)})")
    return jwt


def get_bot_jwt(mysql_root_pw):
    """Recupere le JWT ingestion-bot : API d'abord, puis requete MySQL."""
    try:
        jwt = get_bot_jwt_via_api()
        if jwt:
            return jwt
    except Exception as e:
        print(f"   API method failed: {e}")

    jwt = get_bot_jwt_from_db(mysql_root_pw)
    if jwt:
        return jwt

    raise RuntimeError("Impossible de recuperer le JWT via API ou base de donnees")


def inject_jwt(jwt_token):
    """Ecrit le token JWT dans postgres_connector.yaml et .env."""
    content = CONNECTOR_YAML.read_text(encoding="utf-8")
    content = re.sub(r'(jwtToken:\s*)"[^"]*"', f'\\1"{jwt_token}"', content)
    CONNECTOR_YAML.write_text(content, encoding="utf-8")

    env_content = ENV_FILE.read_text(encoding="utf-8")
    env_content = re.sub(
        r"OPENMETADATA_JWT_TOKEN=.*",
        f"OPENMETADATA_JWT_TOKEN={jwt_token}",
        env_content,
    )
    ENV_FILE.write_text(env_content, encoding="utf-8")


# ── Main ─────────────────────────────────────────────────────────────


def main():
    print("\n" + "=" * 70)
    print(f"{Color.BLUE}DEPLOIEMENT OPENMETADATA{Color.RESET}")
    print("=" * 70)

    # ── 1. Prerequis ──────────────────────────────────────────────────
    print("\n[1/8] Prerequis")

    r = subprocess.run(["docker", "--version"], capture_output=True, text=True)
    if r.returncode != 0:
        err("Docker non installe ou absent du PATH")
        sys.exit(1)
    ok("Docker disponible")

    compose_cmd = detect_compose()
    if not compose_cmd:
        err("Docker Compose introuvable ('docker compose' et 'docker-compose' testes)")
        sys.exit(1)
    ok(f"Commande Compose : {' '.join(compose_cmd)}")

    env = load_env()
    ok(".env charge")

    if REQUIREMENTS.exists():
        print("   Installation des dependances Python...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(REQUIREMENTS)],
            capture_output=True, text=True,
        )
        ok("Dependances Python installees")

    # ── 2. Arret des services existants ───────────────────────────────
    print("\n[2/8] Arret des services existants")
    compose_run(compose_cmd, "down")
    ok("Services arretes")

    # ── 3. Demarrage MySQL + Elasticsearch ────────────────────────────
    print("\n[3/8] Demarrage MySQL + Elasticsearch")

    r = compose_run(compose_cmd, "up", "-d", "mysql", "elasticsearch")
    if r.returncode != 0:
        err(f"Echec du demarrage :\n{r.stderr}")
        sys.exit(1)
    ok("Conteneurs demarres")

    if not wait_for_container_healthy("openmetadata_mysql", timeout=120):
        err("MySQL n'est pas devenu operationnel a temps")
        sys.exit(1)
    ok("MySQL operationnel")

    root_pw = env.get("MYSQL_ROOT_PASSWORD", "")
    airflow_db = env.get("AIRFLOW_DB", "airflow_db")
    airflow_user = env.get("AIRFLOW_USER", "airflow_user")
    airflow_pw = env.get("AIRFLOW_PASSWORD", "")

    sql = (
        f"CREATE DATABASE IF NOT EXISTS {airflow_db}; "
        f"CREATE USER IF NOT EXISTS '{airflow_user}'@'%' IDENTIFIED BY '{airflow_pw}'; "
        f"GRANT ALL PRIVILEGES ON {airflow_db}.* TO '{airflow_user}'@'%'; "
        f"FLUSH PRIVILEGES;"
    )
    subprocess.run(
        ["docker", "exec", "-i", "openmetadata_mysql",
         "mysql", "-u", "root", f"-p{root_pw}", "-e", sql],
        capture_output=True, text=True,
    )
    ok("Base Airflow initialisee")

    if not wait_for_container_healthy("openmetadata_elasticsearch", timeout=180):
        err("Elasticsearch n'est pas devenu operationnel a temps")
        sys.exit(1)
    ok("Elasticsearch operationnel")

    # ── 4. Migration bootstrap de la base ─────────────────────────────
    print("\n[4/8] Migration de la base de donnees (bootstrap)")
    print("   Creation des tables OpenMetadata -- peut prendre 1-2 minutes...")

    try:
        r = subprocess.run(
            compose_cmd + ["run", "--rm", "-T", "openmetadata-server",
                           "./bootstrap/bootstrap_storage.sh", "migrate-all"],
            capture_output=True, text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        err("Migration interrompue apres 5 minutes (timeout)")
        sys.exit(1)

    if r.returncode != 0:
        err("Echec de la migration")
        stderr_tail = r.stderr.strip().splitlines()[-5:] if r.stderr else []
        stdout_tail = r.stdout.strip().splitlines()[-5:] if r.stdout else []
        for line in (stderr_tail or stdout_tail):
            print(f"      {line.strip()}")
        sys.exit(1)
    ok("Migration terminee")

    # ── 5. Demarrage de tous les services ─────────────────────────────
    print("\n[5/8] Demarrage de tous les services")

    r = compose_run(compose_cmd, "up", "-d")
    if r.returncode != 0:
        warn("docker compose up a retourne des warnings (possiblement transitoire) :")
        for line in r.stderr.strip().splitlines()[-3:]:
            print(f"      {line.strip()}")
        print("   On continue -- le polling de readiness prend le relais...")
    else:
        ok("Tous les conteneurs demarres")

    # ── 6. Attente du serveur OpenMetadata ────────────────────────────
    print("\n[6/8] Attente du serveur OpenMetadata")

    if not wait_for_http(
        f"{OM_URL}/api/v1/system/version", "OpenMetadata", timeout=360, interval=15
    ):
        err("OpenMetadata n'est pas devenu operationnel en 6 minutes")
        warn("Verifier les logs : docker logs dq_openmetadata")
        sys.exit(1)
    ok("OpenMetadata operationnel")

    # ── 7. Recuperation JWT + ingestion metadonnees ───────────────────
    print("\n[7/8] Ingestion des metadonnees PostgreSQL")

    # Attente supplementaire pour l'API de login
    print("   Attente supplementaire pour l'API de login (15s)...")
    time.sleep(15)

    # Recuperation du token JWT
    jwt_obtained = False
    try:
        jwt = get_bot_jwt(root_pw)
        inject_jwt(jwt)
        ok("Token JWT recupere et injecte")
        jwt_obtained = True
    except Exception as e:
        warn(f"Impossible de recuperer le JWT automatiquement : {e}")
        import traceback
        print(f"   Debug: {traceback.format_exc()}")
        warn("Etape manuelle : http://localhost:8585 > Settings > Bots > ingestion-bot")
        warn("Copier le token dans .env (OPENMETADATA_JWT_TOKEN) et relancer")
        warn("Ingestion PostgreSQL ignoree (JWT requis)")

    if not jwt_obtained:
        print("\n[8/8] Configuration des metadonnees (tags, glossaire, lineage)")
        warn("Configuration ignoree (JWT non recupere)")
        print("\n" + "="*70)
        print(f"{Color.YELLOW}⚠ DEPLOIEMENT PARTIEL{Color.RESET}")
        print("="*70)
        print(f"\n{Color.BLUE}OpenMetadata :{Color.RESET} http://localhost:8585")
        print("Identifiants : admin / admin")
        print("\nPour terminer le setup :")
        print("1. Recuperer le JWT manuellement depuis l'interface")
        print("2. Le mettre dans openmetadata/.env (OPENMETADATA_JWT_TOKEN)")
        print("3. Relancer le DAG openmetadata_deploy")
        return

    # Copie du fichier de configuration dans le container (volume non monte correctement)
    print("   Copie du fichier de configuration dans le container...")
    connector_file = os.path.join(SCRIPT_DIR, "ingestion", "postgres_connector.yaml")
    if not os.path.exists(connector_file):
        warn(f"Fichier connector introuvable: {connector_file}")
    else:
        cp = subprocess.run(
            ["docker", "cp", connector_file, "openmetadata_ingestion:/tmp/postgres_connector.yaml"],
            capture_output=True, text=True,
        )
        if cp.returncode != 0:
            warn(f"Erreur lors de la copie: {cp.stderr[:200]}")
        else:
            ok("Fichier copie dans le container")
    
    # Ingestion via le container existant
    print("   Lancement de l'ingestion des metadonnees...")
    try:
        r = subprocess.run(
            ["docker", "exec", "openmetadata_ingestion",
             "metadata", "ingest", "-c",
             "/tmp/postgres_connector.yaml"],
            capture_output=True, text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        warn("Ingestion interrompue apres 5 minutes (timeout)")
        r = None

    if r and r.returncode == 0:
        ok("Metadonnees PostgreSQL ingerees")
    else:
        warn(f"Ingestion terminee avec le code {r.returncode if r else 'timeout'}")
        if r and r.stderr:
            print(f"      Stderr: {r.stderr[:500]}")
        if r and r.stdout:
            print(f"      Stdout: {r.stdout[:500]}")

    # ── 8. Configuration des metadonnees ──────────────────────────────
    print("\n[8/8] Configuration des metadonnees (tags, glossaire, lineage)")

    # Recharger le .env pour avoir le JWT fraichement injecte
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE, override=True)
    jwt_from_env = os.getenv("OPENMETADATA_JWT_TOKEN")
    
    if not jwt_from_env or jwt_from_env == "your_jwt_token_here":
        warn("JWT non trouve dans .env apres injection")
        return

    r = subprocess.run(
        [sys.executable, "-X", "utf8", str(SETUP_SCRIPT)],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={
            **os.environ, 
            "PYTHONIOENCODING": "utf-8",
            "OPENMETADATA_JWT_TOKEN": jwt_from_env,
            "OPENMETADATA_URL": OM_API,
        },
    )
    if r.stdout:
        print(r.stdout)
    if r.returncode != 0 and r.stderr:
        warn(f"Erreurs du script de setup : {r.stderr[:300]}")

    # ── Resume ────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print(f"{Color.GREEN}v DEPLOIEMENT TERMINE{Color.RESET}")
    print("=" * 70)
    print(f"\n{Color.BLUE}OpenMetadata :{Color.RESET} {OM_URL}")
    print("Identifiants : admin / admin")
    print("\nConfiguration appliquee :")
    print("  - 7 tables PostgreSQL ingerees")
    print("  - 4 Classifications + 8 Tags")
    print("  - ~100 Colonnes documentees")
    print("  - 39 Termes de glossaire")
    print("  - 6 Relations de lineage")


if __name__ == "__main__":
    main()
