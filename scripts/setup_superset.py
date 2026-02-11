#!/usr/bin/env python3
"""
Script d'automatisation de la configuration Superset.
Crée les datasets SQL virtuels et importe les dashboards exportés.
"""

import os
import sys
import time
import subprocess
import zipfile
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent

SUPERSET_CONTAINER = "superset"
DB_PASSWORD = "postgres"

DASHBOARD_EXPORT = "superset/dashboards/dashboard_export.zip"

DATASET_EXPORTS = [
    "superset/datasets/dataset_1.zip",
    "superset/datasets/dataset_2.zip",
    "superset/datasets/dataset_3.zip",
    "superset/datasets/dataset_4.zip",
    "superset/datasets/dataset_5.zip",
    "superset/datasets/dataset_6.zip",
]

SQL_DATASETS = {
    "DQ_METRICS_TOTAL": """
        SELECT 
            (
                (COUNT("app_id") + COUNT("name") + COUNT("release_date") + COUNT("estimated_owners") + 
                 COUNT("peak_ccu") + COUNT("required_age") + COUNT("price") + COUNT("discount") + 
                 COUNT("dlc_count") + COUNT("about_the_game") + COUNT("supported_languages") + 
                 COUNT("full_audio_languages") + COUNT("reviews") + COUNT("header_image") + 
                 COUNT("website") + COUNT("support_url") + COUNT("support_email") + COUNT("windows") + 
                 COUNT("mac") + COUNT("linux") + COUNT("metacritic_score") + COUNT("metacritic_url") + 
                 COUNT("user_score") + COUNT("positive") + COUNT("negative") + COUNT("score_rank") + 
                 COUNT("achievements") + COUNT("recommendations") + COUNT("notes") + 
                 COUNT("average_playtime_forever") + COUNT("average_playtime_two_weeks") + 
                 COUNT("median_playtime_forever") + COUNT("median_playtime_two_weeks") + 
                 COUNT("developers") + COUNT("publishers") + COUNT("categories") + COUNT("genres") + 
                 COUNT("tags") + COUNT("screenshots") + COUNT("movies"))::FLOAT 
                / (40 * COUNT(*)) * 100
            ) as score_completude,
            (COUNT(DISTINCT "name")::FLOAT / COUNT(*)::FLOAT) * 100 as score_unicite,
            100 - (
                COUNT(*) FILTER (WHERE "support_email" IS NOT NULL AND "support_email" !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')::FLOAT 
                / NULLIF(COUNT("support_email"), 0) * 100
            ) as score_exactitude,
            100 - (
                COUNT(*) FILTER (WHERE "price" < 0 OR "average_playtime_forever" < 0)::FLOAT
                / COUNT(*)::FLOAT * 100
            ) as score_validite,
            100 - (
                COUNT(*) FILTER (WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0)::FLOAT 
                / COUNT(*)::FLOAT * 100
            ) as score_coherence,
            100 as score_actualite
        FROM games_brut
    """,
    
    "DQ_TRENDS_HISTORY": """
        SELECT 
            DATE_TRUNC('year', release_date) as annee_sortie,
            COUNT(*) as volume_jeux,
            (
                (COUNT("app_id") + COUNT("name") + COUNT("release_date") + COUNT("estimated_owners") + 
                 COUNT("peak_ccu") + COUNT("required_age") + COUNT("price") + COUNT("discount") + 
                 COUNT("dlc_count") + COUNT("about_the_game") + COUNT("supported_languages") + 
                 COUNT("full_audio_languages") + COUNT("reviews") + COUNT("header_image") + 
                 COUNT("website") + COUNT("support_url") + COUNT("support_email") + COUNT("windows") + 
                 COUNT("mac") + COUNT("linux") + COUNT("metacritic_score") + COUNT("metacritic_url") + 
                 COUNT("user_score") + COUNT("positive") + COUNT("negative") + COUNT("score_rank") + 
                 COUNT("achievements") + COUNT("recommendations") + COUNT("notes") + 
                 COUNT("average_playtime_forever") + COUNT("average_playtime_two_weeks") + 
                 COUNT("median_playtime_forever") + COUNT("median_playtime_two_weeks") + 
                 COUNT("developers") + COUNT("publishers") + COUNT("categories") + COUNT("genres") + 
                 COUNT("tags") + COUNT("screenshots") + COUNT("movies"))::FLOAT 
                / (40 * NULLIF(COUNT(*), 0)) * 100
            ) as score_completude,
            (COUNT(DISTINCT "name")::FLOAT / NULLIF(COUNT(*), 0)::FLOAT) * 100 as score_unicite,
            COALESCE(
                100 - (
                    COUNT(*) FILTER (WHERE "support_email" IS NOT NULL AND "support_email" !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')::FLOAT 
                    / NULLIF(COUNT("support_email"), 0) * 100
                ), 100
            ) as score_exactitude,
            100 - (
                COUNT(*) FILTER (WHERE "price" < 0 OR "average_playtime_forever" < 0)::FLOAT
                / NULLIF(COUNT(*), 0)::FLOAT * 100
            ) as score_validite,
            100 - (
                COUNT(*) FILTER (WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0)::FLOAT 
                / NULLIF(COUNT(*), 0)::FLOAT * 100
            ) as score_coherence,
            100 as score_actualite,
            AVG("price") as prix_moyen,
            MAX("price") as prix_max
        FROM games_brut
        WHERE release_date IS NOT NULL 
          AND release_date BETWEEN '2000-01-01' AND '2026-01-01'
        GROUP BY 1
        ORDER BY 1
    """,
    
    "DQ_ERROR_LIST": """
        SELECT 
            app_id, name, 'Cohérence' as pilier, 'F2P avec Prix' as type_erreur, 
            CONCAT('Prix: ', price, '$ alors que le tag est Free to Play') as details, release_date
        FROM games_brut 
        WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0
        UNION ALL
        SELECT 
            app_id, name, 'Exactitude' as pilier, 'Email Invalide' as type_erreur, 
            CONCAT('Email: ', support_email) as details, release_date
        FROM games_brut 
        WHERE "support_email" IS NOT NULL 
          AND "support_email" !~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'
        UNION ALL
        SELECT 
            app_id, name, 'Validité' as pilier, 'Prix Aberrant' as type_erreur, 
            CONCAT('Prix: ', price, '$ (> 200$)') as details, release_date
        FROM games_brut 
        WHERE "price" > 200
        UNION ALL
        SELECT 
            app_id, name, 'Complétude' as pilier, 'Manque Info Critique' as type_erreur,
            'Tags manquants' as details, release_date
        FROM games_brut
        WHERE "tags" IS NULL
    """,
    
    "DQ_SANKEY_FLOW": """
        SELECT 'Total Dataset' as source, 'Validité Structurelle (Noms Uniques)' as target, 
               COUNT(DISTINCT name) as value 
        FROM games_brut
        UNION ALL
        SELECT 'Validité Structurelle (Noms Uniques)' as source, 'Cohérence Métier (Prix F2P OK)' as target, 
               COUNT(*) as value
        FROM games_brut 
        WHERE ("tags" NOT ILIKE '%Free to Play%' OR "price" = 0)
        UNION ALL
        SELECT 'Cohérence Métier (Prix F2P OK)' as source, 'Exactitude (Emails Valides)' as target, 
               COUNT(*) as value
        FROM games_brut 
        WHERE ("tags" NOT ILIKE '%Free to Play%' OR "price" = 0)
          AND ("support_email" IS NULL OR "support_email" ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')
        UNION ALL
        SELECT 'Total Dataset', 'Doublons/Erreurs ID', (COUNT(*) - COUNT(DISTINCT name)) FROM games_brut
        UNION ALL
        SELECT 'Validité Structurelle (Noms Uniques)', 'Erreurs Cohérence (F2P Payant)', 
               COUNT(*) FROM games_brut WHERE "tags" ILIKE '%Free to Play%' AND "price" > 0
    """,
    
    "DQ_ZOOM_COMPLETENESS": """
        SELECT 'movies' AS colonne, 100 - (COUNT(movies)::FLOAT / COUNT(*) * 100) AS pourcent_vide FROM games_brut
        UNION ALL SELECT 'score_rank', 100 - (COUNT(score_rank)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'metacritic_url', 100 - (COUNT(metacritic_url)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'metacritic_score', 100 - (COUNT(metacritic_score)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'user_score', 100 - (COUNT(user_score)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'website', 100 - (COUNT(website)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'support_url', 100 - (COUNT(support_url)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'support_email', 100 - (COUNT(support_email)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'about_the_game', 100 - (COUNT(about_the_game)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'notes', 100 - (COUNT(notes)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'reviews', 100 - (COUNT(reviews)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'header_image', 100 - (COUNT(header_image)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'screenshots', 100 - (COUNT(screenshots)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'tags', 100 - (COUNT(tags)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'genres', 100 - (COUNT(genres)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'categories', 100 - (COUNT(categories)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'developers', 100 - (COUNT(developers)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'publishers', 100 - (COUNT(publishers)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'supported_languages', 100 - (COUNT(supported_languages)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'full_audio_languages', 100 - (COUNT(full_audio_languages)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'achievements', 100 - (COUNT(achievements)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'recommendations', 100 - (COUNT(recommendations)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'average_playtime_forever', 100 - (COUNT(average_playtime_forever)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'average_playtime_two_weeks', 100 - (COUNT(average_playtime_two_weeks)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'median_playtime_forever', 100 - (COUNT(median_playtime_forever)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'median_playtime_two_weeks', 100 - (COUNT(median_playtime_two_weeks)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'price', 100 - (COUNT(price)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'discount', 100 - (COUNT(discount)::FLOAT / COUNT(*) * 100) FROM games_brut
        UNION ALL SELECT 'dlc_count', 100 - (COUNT(dlc_count)::FLOAT / COUNT(*) * 100) FROM games_brut
        ORDER BY pourcent_vide DESC
    """,
    
    "DQ_BOXPLOT": """
        SELECT 
            name, app_id, price,
            CAST(EXTRACT(YEAR FROM release_date) AS INTEGER) as annee_sortie
        FROM games_brut
        WHERE price >= 0 
          AND release_date BETWEEN '2000-01-01' AND '2026-01-01'
        ORDER BY annee_sortie DESC
    """,
}


def run_cmd(cmd, description):
    print(f"\n[*] {description}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Erreur: {result.stderr}")
        return False
    if result.stdout:
        print(result.stdout)
    return True


def fix_zip_password(zip_path):
    """
    Extrait le ZIP, remplace XXXXXXXXXX par le vrai mot de passe dans les YAMLs,
    puis recrée le ZIP.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir_path)
        
        for yaml_file in tmpdir_path.rglob("databases/*.yaml"):
            content = yaml_file.read_text()
            if "XXXXXXXXXX" in content:
                content = content.replace("XXXXXXXXXX", DB_PASSWORD)
                yaml_file.write_text(content)
        
        fixed_zip = zip_path.parent / f"fixed_{zip_path.name}"
        with zipfile.ZipFile(fixed_zip, 'w', zipfile.ZIP_DEFLATED) as zip_out:
            for file_path in tmpdir_path.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(tmpdir_path)
                    zip_out.write(file_path, arcname)
        
        shutil.move(str(fixed_zip), str(zip_path))
        return True


def import_datasets():
    print("\n" + "=" * 70)
    print("IMPORT DES DATASETS")
    print("=" * 70)
    
    for dataset_path in DATASET_EXPORTS:
        dataset_file = ROOT / dataset_path
        
        if not dataset_file.exists():
            print(f"⚠️  Fichier {dataset_path} introuvable, skip")
            continue
        
        print(f"\n[*] Correction du mot de passe dans {dataset_file.name}")
        fix_zip_password(dataset_file)
        
        print(f"[*] Import de {dataset_file.name}")
        
        cmd = (
            f"docker cp {dataset_file} {SUPERSET_CONTAINER}:/tmp/{dataset_file.name} && "
            f"docker exec {SUPERSET_CONTAINER} superset import-datasources "
            f"-p /tmp/{dataset_file.name}"
        )
        
        if run_cmd(cmd, f"Import {dataset_file.name}"):
            print(f"✅ Dataset {dataset_file.name} importé")
        else:
            print(f"⚠️  Échec import {dataset_file.name}")
    
    print("\n✅ Import des datasets terminé")


def save_sql_reference():
    print("\n" + "=" * 70)
    print("SAUVEGARDE DES REQUÊTES SQL (RÉFÉRENCE)")
    print("=" * 70)
    
    for dataset_name, sql_query in SQL_DATASETS.items():
        print(f"\n[{dataset_name}] Sauvegarde SQL de référence...")
        
        sql_file = ROOT / "superset" / "datasets" / "sql_reference" / f"{dataset_name}.sql"
        sql_file.parent.mkdir(parents=True, exist_ok=True)
        sql_file.write_text(sql_query.strip())
        
        print(f"✅ {dataset_name}.sql sauvegardé")
    
    print("\n✅ Toutes les requêtes SQL sauvegardées (référence)")


def import_dashboard():
    print("\n" + "=" * 70)
    print("IMPORT DU DASHBOARD")
    print("=" * 70)
    
    dashboard_file = ROOT / DASHBOARD_EXPORT
    
    if not dashboard_file.exists():
        print(f"⚠️  Fichier {DASHBOARD_EXPORT} introuvable")
        print(f"   Placez le fichier dans: {dashboard_file}")
        return False
    
    print(f"\n[*] Correction du mot de passe dans {dashboard_file.name}")
    fix_zip_password(dashboard_file)
    
    print(f"[*] Import de {dashboard_file.name}")
    
    cmd = (
        f"docker cp {dashboard_file} {SUPERSET_CONTAINER}:/tmp/{dashboard_file.name} && "
        f"docker exec {SUPERSET_CONTAINER} superset import-dashboards "
        f"-p /tmp/{dashboard_file.name} --username admin"
    )
    
    if run_cmd(cmd, f"Import {dashboard_file.name}"):
        print(f"✅ Dashboard importé avec succès")
        return True
    else:
        print(f"⚠️  Échec import du dashboard")
        return False


def main():
    print("=" * 70)
    print("CONFIGURATION AUTOMATIQUE SUPERSET")
    print("=" * 70)
    
    print("\n[*] Vérification du container Superset...")
    result = subprocess.run(
        f"docker ps --filter name={SUPERSET_CONTAINER} --format '{{{{.Names}}}}'",
        shell=True, capture_output=True, text=True
    )
    
    if SUPERSET_CONTAINER not in result.stdout:
        print(f"❌ Container {SUPERSET_CONTAINER} non trouvé ou non actif")
        print("   Lancez d'abord: docker-compose up -d superset")
        sys.exit(1)
    
    print(f"✅ Container {SUPERSET_CONTAINER} actif")
    
    save_sql_reference()
    import_datasets()
    dashboard_ok = import_dashboard()
    
    print("\n" + "=" * 70)
    print("✅ CONFIGURATION SUPERSET TERMINÉE")
    print("=" * 70)
    print(f"\nAccès Superset: http://localhost:8088")
    print("Credentials: admin / admin")
    
    datasets_count = len([f for f in DATASET_EXPORTS if (ROOT / f).exists()])
    print(f"\n✅ {datasets_count} datasets importés")
    print(f"✅ {'1 dashboard importé' if dashboard_ok else 'Dashboard non importé'}")
    
    if not dashboard_ok:
        print("\n⚠️  Note: Si certains imports ont échoué, vous pouvez les importer manuellement via l'UI Superset")


if __name__ == "__main__":
    main()
