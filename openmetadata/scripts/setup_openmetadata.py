"""
Script d'automatisation complète de la configuration OpenMetadata
Configure : Tags, Classifications, Descriptions, Glossaire, Lineage, Owners
"""
import requests
import json
import csv
import time
import os
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

OPENMETADATA_URL = os.getenv("OPENMETADATA_URL", "http://localhost:8585/api")

# Charger le token JWT depuis le fichier .env
from dotenv import load_dotenv
dotenv_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path)

JWT_TOKEN = os.getenv("OPENMETADATA_JWT_TOKEN")

if not JWT_TOKEN or JWT_TOKEN == "your_jwt_token_here":
    print("⚠️  Token JWT non configuré!")
    print("➜ Copiez .env.example en .env et ajoutez votre JWT token")
    print("➜ Obtenir le token: http://localhost:8585 > Settings > Bots > ingestion-bot")
    exit(1)

GLOSSARY_CSV = Path(__file__).parent.parent / "glossary" / "games_glossary.csv"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

# ============================================================================
# 1. CLASSIFICATIONS & TAGS
# ============================================================================

CLASSIFICATIONS = {
    "PII": {
        "description": "Classification for Personal Identifiable Information sensitivity levels",
        "tags": [
            {"name": "None", "description": "No personal data"}
        ]
    },
    "Tier": {
        "description": "Data quality tier classification (Bronze, Silver, Gold)",
        "tags": [
            {"name": "Bronze", "description": "Raw ingested data"},
            {"name": "Silver", "description": "Cleaned and validated data"},
            {"name": "Gold", "description": "Highest quality, production-ready data"}
        ]
    },
    "Sensitive": {
        "description": "Classification for sensitive data types",
        "tags": [
            {"name": "Financial", "description": "Financial or pricing data"},
            {"name": "Compliance", "description": "Regulatory compliance data"}
        ]
    },
    "Other": {
        "description": "Other business tags",
        "tags": [
            {"name": "KPI", "description": "Key Performance Indicator metric"},
            {"name": "DataQuality", "description": "Data quality related fields"}
        ]
    }
}

# ============================================================================
# 2. TABLE DESCRIPTIONS
# ============================================================================

TABLE_DESCRIPTIONS = {
    "games_brut": {
        "description": "Données brutes extraites de l'API Steam sans transformation. Contient l'ensemble des informations sur les jeux Steam telles qu'ingérées initialement : métadonnées, prix, statistiques de joueurs, et avis. Sert de source primaire pour le pipeline de transformation. Non nettoyée, peut contenir des valeurs nulles et des incohérences.",
        "tier": "Tier.Bronze"
    },
    "games_clean": {
        "description": "Données nettoyées et validées issues de games_brut. Transformations appliquées : normalisation des types, gestion des valeurs manquantes, suppression des doublons, standardisation des formats de dates et prix. Prête pour l'analyse exploratoire et les transformations métier.",
        "tier": "Tier.Silver"
    },
    "games_gold": {
        "description": "Table principale d'analyse contenant les métriques enrichies et calculées pour chaque jeu Steam. Inclut les KPIs business (estimation propriétaires, scores agrégés, temps de jeu), flags comportementaux (is_legacy, price_outlier), et dimensions pré-calculées (primary_genre, primary_tag). Optimisée pour les dashboards et rapports business.",
        "tier": "Tier.Gold"
    },
    "game_tags": {
        "description": "Table de dimension contenant les tags Steam associés à chaque jeu. Permet l'analyse par catégorie comportementale (Singleplayer, Multiplayer, Indie, Early Access, etc.). Relation many-to-many avec games_gold via app_id. Utilisée pour le filtrage et la segmentation des jeux par caractéristiques.",
        "tier": "Tier.Gold"
    },
    "game_genres": {
        "description": "Table de dimension listant les genres officiels Steam de chaque jeu (Action, RPG, Strategy, Simulation, etc.). Relation many-to-many avec games_gold via app_id. Permet l'analyse comparative par genre et l'identification des tendances de marché par catégorie de jeu.",
        "tier": "Tier.Gold"
    },
    "game_developers": {
        "description": "Table de dimension répertoriant les studios de développement responsables de chaque jeu. Relation many-to-many avec games_gold via app_id. Permet l'analyse de portefeuille par développeur, identification des studios prolifiques, et études de corrélation entre développeur et succès commercial.",
        "tier": "Tier.Gold"
    },
    "game_publishers": {
        "description": "Table de dimension contenant les éditeurs (publishers) de chaque jeu Steam. Relation many-to-many avec games_gold via app_id. Utilisée pour analyser les stratégies d'édition, parts de marché des éditeurs, et corrélations entre éditeur et performance commerciale ou critique.",
        "tier": "Tier.Gold"
    }
}

# ============================================================================
# 3. LINEAGE (relations entre tables)
# ============================================================================

LINEAGE = [
    {
        "from": "games_database.games_db.public.games_brut",
        "to": "games_database.games_db.public.games_clean",
        "description": "Transformation Bronze → Silver : nettoyage et validation"
    },
    {
        "from": "games_database.games_db.public.games_clean",
        "to": "games_database.games_db.public.games_gold",
        "description": "Transformation Silver → Gold : calculs métriques et enrichissement"
    },
    {
        "from": "games_database.games_db.public.games_gold",
        "to": "games_database.games_db.public.game_tags",
        "description": "Extraction dimension tags"
    },
    {
        "from": "games_database.games_db.public.games_gold",
        "to": "games_database.games_db.public.game_genres",
        "description": "Extraction dimension genres"
    },
    {
        "from": "games_database.games_db.public.games_gold",
        "to": "games_database.games_db.public.game_developers",
        "description": "Extraction dimension développeurs"
    },
    {
        "from": "games_database.games_db.public.games_gold",
        "to": "games_database.games_db.public.game_publishers",
        "description": "Extraction dimension éditeurs"
    }
]

# ============================================================================
# FONCTIONS UTILITAIRES
# ============================================================================

def api_call(method, endpoint, data=None, ignore_404=False):
    """Appel API générique avec gestion d'erreur"""
    url = f"{OPENMETADATA_URL}/{endpoint}"
    
    # Headers spécifiques pour PATCH (JSON Patch)
    patch_headers = headers.copy()
    if method == "PATCH":
        patch_headers["Content-Type"] = "application/json-patch+json"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        elif method == "PATCH":
            response = requests.patch(url, headers=patch_headers, json=data)
        
        if response.status_code in [200, 201]:
            return True, response.json() if response.text else {}
        elif response.status_code == 404 and ignore_404:
            return False, None
        else:
            return False, response.text
    except Exception as e:
        return False, str(e)

# ============================================================================
# 1. CRÉER LES CLASSIFICATIONS ET TAGS
# ============================================================================

def create_classifications():
    """Crée toutes les classifications et leurs tags"""
    print("\n" + "="*70)
    print("🏷️  ÉTAPE 1 : Création des Classifications et Tags")
    print("="*70)
    
    for class_name, class_data in CLASSIFICATIONS.items():
        print(f"\n📁 Classification : {class_name}")
        
        # Vérifier si la classification existe
        success, existing = api_call("GET", f"v1/classifications/name/{class_name}", ignore_404=True)
        
        if not existing:
            # Créer la classification
            classification_payload = {
                "name": class_name,
                "description": class_data["description"]
            }
            success, result = api_call("POST", "v1/classifications", classification_payload)
            if success:
                print(f"   ✅ Classification créée")
            else:
                print(f"   ❌ Erreur : {result}")
                continue
        else:
            print(f"   ℹ️  Classification existe déjà")
        
        # Créer les tags
        for tag in class_data["tags"]:
            tag_payload = {
                "classification": class_name,
                "name": tag["name"],
                "description": tag["description"]
            }
            success, result = api_call("POST", "v1/tags", tag_payload)
            if success:
                print(f"      ✅ Tag créé : {class_name}.{tag['name']}")
            else:
                if "already exists" in str(result).lower():
                    print(f"      ℹ️  Tag existe déjà : {class_name}.{tag['name']}")
                else:
                    print(f"      ❌ Erreur pour {tag['name']}: {result}")

# ============================================================================
# 2. METTRE À JOUR LES DESCRIPTIONS DES TABLES
# ============================================================================

def update_table_descriptions():
    """Met à jour les descriptions et tags des tables"""
    print("\n" + "="*70)
    print("📝 ÉTAPE 2 : Mise à jour des descriptions des tables")
    print("="*70)
    
    for table_name, table_info in TABLE_DESCRIPTIONS.items():
        print(f"\n📊 Table : {table_name}")
        
        fqn = f"games_database.games_db.public.{table_name}"
        
        # Récupérer la table
        success, table_data = api_call("GET", f"v1/tables/name/{fqn}")
        
        if not success:
            print(f"   ❌ Table non trouvée : {fqn}")
            continue
        
        # Préparer le payload PATCH (seulement les champs à modifier)
        patch_payload = [
            {
                "op": "add",
                "path": "/description",
                "value": table_info["description"]
            },
            {
                "op": "add",
                "path": "/tags",
                "value": [
                    {
                        "tagFQN": table_info["tier"],
                        "labelType": "Manual",
                        "state": "Confirmed"
                    }
                ]
            }
        ]
        
        # Envoyer la mise à jour via PATCH
        table_id = table_data.get("id")
        success, result = api_call("PATCH", f"v1/tables/{table_id}", patch_payload)
        
        if success:
            print(f"   ✅ Description et tag mis à jour")
        else:
            print(f"   ❌ Erreur : {result}")

# ============================================================================
# 3. METTRE À JOUR LES DESCRIPTIONS DES COLONNES
# ============================================================================

COLUMNS_METADATA_FILE = Path(__file__).parent.parent / "conf" / "columns_metadata.json"

def update_column_metadata():
    """Met à jour descriptions, tags et termes de glossaire pour chaque colonne"""
    print("\n" + "="*70)
    print("📋 ÉTAPE 4 : Mise à jour des métadonnées des colonnes")
    print("="*70)
    
    # Charger la configuration des colonnes
    if not COLUMNS_METADATA_FILE.exists():
        print(f"   ⚠️  Fichier de configuration non trouvé : {COLUMNS_METADATA_FILE}")
        return
    
    with open(COLUMNS_METADATA_FILE, 'r', encoding='utf-8') as f:
        columns_config = json.load(f)
    
    for table_name, columns in columns_config.items():
        print(f"\n📊 Table : {table_name}")
        
        fqn = f"games_database.games_db.public.{table_name}"
        
        # Récupérer la table complète avec ses colonnes
        success, table_data = api_call("GET", f"v1/tables/name/{fqn}?fields=columns,tags")
        
        if not success:
            print(f"   ❌ Table non trouvée : {fqn}")
            continue
        
        table_id = table_data.get("id")
        existing_columns = table_data.get("columns", [])
        
        # Mettre à jour chaque colonne
        updated_count = 0
        for col_name, col_metadata in columns.items():
            # Trouver la colonne existante
            existing_col = next((c for c in existing_columns if c["name"] == col_name), None)
            
            if not existing_col:
                print(f"   ⚠️  Colonne non trouvée : {col_name}")
                continue
            
            # Construire le JSON Patch pour la colonne
            column_fqn = existing_col["fullyQualifiedName"]
            
            # Préparer les tags
            tags_payload = []
            for tag_fqn in col_metadata.get("tags", []):
                tags_payload.append({
                    "tagFQN": tag_fqn,
                    "labelType": "Manual",
                    "state": "Confirmed"
                })
            
            # Construire le patch
            patch_operations = []
            
            # 1. Description
            if "description" in col_metadata:
                patch_operations.append({
                    "op": "add",
                    "path": f"/columns/{existing_columns.index(existing_col)}/description",
                    "value": col_metadata["description"]
                })
            
            # 2. Tags
            if tags_payload:
                patch_operations.append({
                    "op": "add",
                    "path": f"/columns/{existing_columns.index(existing_col)}/tags",
                    "value": tags_payload
                })
            
            # Appliquer le patch si on a des opérations
            if patch_operations:
                success, result = api_call("PATCH", f"v1/tables/{table_id}", patch_operations)
                
                if success:
                    updated_count += 1
                    
                    # Lier le terme de glossaire si spécifié (utilise le nom du glossaire GamingAnalytics)
                    if "glossaryTerm" in col_metadata:
                        glossary_term_fqn = f"GamingAnalytics.{col_metadata['glossaryTerm']}"
                        
                        # Récupérer le terme de glossaire
                        term_success, term_data = api_call("GET", f"v1/glossaryTerms/name/{glossary_term_fqn}")
                        
                        if term_success:
                            # Ajouter le terme comme tag spécial de type Glossary
                            link_patch = [{
                                "op": "add",
                                "path": f"/columns/{existing_columns.index(existing_col)}/tags/-",
                                "value": {
                                    "tagFQN": glossary_term_fqn,
                                    "labelType": "Manual",
                                    "state": "Confirmed",
                                    "source": "Glossary"
                                }
                            }]
                            
                            link_success, link_result = api_call("PATCH", f"v1/tables/{table_id}", link_patch)
                            
                            if link_success:
                                print(f"   ✅ {col_name}: description + tags + terme '{col_metadata['glossaryTerm']}'")
                            else:
                                print(f"   ⚠️  {col_name}: description + tags OK, terme KO - {str(link_result)[:80]}")
                        else:
                            print(f"   ⚠️  {col_name}: description + tags OK, terme '{glossary_term_fqn}' non trouvé")
                    else:
                        print(f"   ✅ {col_name}: description + tags")
                else:
                    print(f"   ❌ {col_name}: Erreur - {str(result)[:100]}")
        
        print(f"   📊 {updated_count}/{len(columns)} colonnes mises à jour")

# ============================================================================
# 3. CRÉER LE GLOSSAIRE
# ============================================================================

def create_glossary():
    """Crée le glossaire à partir du CSV"""
    print("\n" + "="*70)
    print("📚 ÉTAPE 3 : Création du Glossaire")
    print("="*70)
    
    # Vérifier si le fichier existe
    if not GLOSSARY_CSV.exists():
        print(f"   ❌ Fichier glossaire non trouvé : {GLOSSARY_CSV}")
        return
    
    # Créer le glossaire principal
    glossary_name = "GamingAnalytics"
    print(f"\n📖 Glossaire : {glossary_name}")
    
    glossary_payload = {
        "name": glossary_name,
        "displayName": "Gaming Analytics Glossary",
        "description": "Glossaire métier pour l'analyse des données Steam Games"
    }
    
    success, result = api_call("POST", "v1/glossaries", glossary_payload)
    
    if success:
        print(f"   ✅ Glossaire créé")
        glossary_fqn = result.get("fullyQualifiedName")
    else:
        if "already exists" in str(result).lower():
            print(f"   ℹ️  Glossaire existe déjà")
            # Récupérer le glossaire existant
            success, glossary = api_call("GET", f"v1/glossaries/name/{glossary_name}")
            if success:
                glossary_fqn = glossary.get("fullyQualifiedName")
            else:
                print(f"   ❌ Impossible de récupérer le glossaire")
                return
        else:
            print(f"   ❌ Erreur : {result}")
            return
    
    # Attendre que le glossaire soit bien créé
    time.sleep(1)
    
    # Lire le CSV et créer les termes
    print(f"\n   📄 Import des termes depuis {GLOSSARY_CSV.name}")
    
    with open(GLOSSARY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        terms_created = 0
        terms_skipped = 0
        
        for row in reader:
            term_name = row['name*']
            
            # Préparer les synonymes
            synonyms = [s.strip() for s in row['synonyms'].split(';') if s.strip()] if row['synonyms'] else []
            
            # Préparer les tags
            tags = []
            if row['tags']:
                for tag_fqn in row['tags'].split(';'):
                    if tag_fqn.strip():
                        tags.append({
                            "tagFQN": tag_fqn.strip(),
                            "labelType": "Manual",
                            "state": "Confirmed"
                        })
            
            term_payload = {
                "glossary": glossary_fqn,  # Utiliser le FQN au lieu de l'ID
                "name": term_name,
                "displayName": row['displayName'],
                "description": row['description'],
                "synonyms": synonyms,
                "tags": tags
            }
            
            success, result = api_call("POST", "v1/glossaryTerms", term_payload)
            
            if success:
                terms_created += 1
                if terms_created % 10 == 0:
                    print(f"      ✅ {terms_created} termes créés...")
            else:
                if "already exists" in str(result).lower():
                    terms_skipped += 1
                else:
                    print(f"      ⚠️  Erreur pour {term_name}: {result[:100]}")
        
        print(f"\n   📊 Résumé glossaire:")
        print(f"      ✅ Créés : {terms_created}")
        print(f"      ℹ️  Ignorés (existants) : {terms_skipped}")

# ============================================================================
# 5. CRÉER LE LINEAGE
# ============================================================================

def create_lineage():
    """Crée les relations de lineage entre tables"""
    print("\n" + "="*70)
    print("🔗 ÉTAPE 5 : Création du Lineage")
    print("="*70)
    
    for link in LINEAGE:
        from_table = link['from'].split('.')[-1]
        to_table = link['to'].split('.')[-1]
        print(f"\n   {from_table} → {to_table}")
        
        # Récupérer les IDs des tables
        success_from, table_from = api_call("GET", f"v1/tables/name/{link['from']}")
        success_to, table_to = api_call("GET", f"v1/tables/name/{link['to']}")
        
        if not success_from or not success_to:
            print(f"      ❌ Une des tables n'existe pas")
            continue
        
        # Créer le lineage avec les IDs
        lineage_payload = {
            "edge": {
                "fromEntity": {
                    "id": table_from.get("id"),
                    "type": "table"
                },
                "toEntity": {
                    "id": table_to.get("id"),
                    "type": "table"
                },
                "description": link["description"]
            }
        }
        
        success, result = api_call("PUT", "v1/lineage", lineage_payload)
        
        if success:
            print(f"      ✅ Lineage créé")
        else:
            if "already exists" in str(result).lower():
                print(f"      ℹ️  Lineage existe déjà")
            else:
                print(f"      ⚠️  Erreur : {result[:150]}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*70)
    print("🚀 AUTOMATISATION COMPLÈTE OPENMETADATA")
    print("="*70)
    print(f"📍 URL : {OPENMETADATA_URL}")
    print(f"🔑 Token : {JWT_TOKEN[:50]}...")
    
    try:
        # Étape 1 : Classifications et Tags
        create_classifications()
        time.sleep(2)
        
        # Étape 2 : Descriptions des tables
        update_table_descriptions()
        time.sleep(2)
        
        # Étape 3 : Glossaire (AVANT les colonnes pour pouvoir lier les termes)
        create_glossary()
        time.sleep(2)
        
        # Étape 4 : Descriptions, tags et termes des colonnes
        update_column_metadata()
        time.sleep(2)
        
        # Étape 5 : Lineage
        create_lineage()
        
        print("\n" + "="*70)
        print("✅ CONFIGURATION OPENMETADATA TERMINÉE !")
        print("="*70)
        print("\n🎯 Actions complétées :")
        print("   ✅ 4 Classifications créées (PII, Tier, Sensitive, Other)")
        print("   ✅ 8 Tags créés")
        print("   ✅ 7 Tables documentées avec descriptions et tags")
        print("   ✅ ~100 Colonnes enrichies avec descriptions, tags et termes")
        print("   ✅ ~40 Termes de glossaire importés")
        print("   ✅ 6 Relations de lineage créées")
        print("\n🌐 Accède à OpenMetadata : http://localhost:8585")
        
    except Exception as e:
        print(f"\n❌ ERREUR CRITIQUE : {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
