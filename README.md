# Steam Games Data Quality Project

A comprehensive data quality audit and improvement project on the Steam Games dataset.

## Project Overview

This project implements a complete data quality assessment and enhancement approach based on the **Medallion Architecture** (Bronze → Silver → Gold) covering the 6 pillars of data quality:

| Pillar | Description |
|--------|-------------|
| **Completeness** | Missing values detection and handling |
| **Uniqueness** | Duplicate records identification |
| **Accuracy** | Format validation (emails, URLs, dates) |
| **Validity** | Value range and domain constraints |
| **Consistency** | Cross-column logical rules |
| **Timeliness** | Date freshness and future date detection |

## Dataset

- **Source**: Steam Games Dataset (Kaggle)
- **Size**: ~122,000 games
- **Columns**: 40 attributes (name, price, reviews, genres, tags, etc.)

### Download

The file `games_brut.xlsx` (~150MB) is not included in the repo.

**Download:** [Google Drive](https://drive.google.com/drive/folders/1r-sUaKFj4h9zV5IN3HnjrfFSoZVdMmF1?usp=drive_link)

Place the file in `data/Bronze/`.

## Quick Start

### Prérequis

- Docker & Docker Compose installés
- 8 Go RAM minimum recommandés
- Ports disponibles : 5432, 8080, 8081, 8088, 8585, 8888

### Étapes d'installation

#### 1. Télécharger les données brutes

Téléchargez `games_brut.xlsx` depuis le [Google Drive](https://drive.google.com/drive/folders/1r-sUaKFj4h9zV5IN3HnjrfFSoZVdMmF1?usp=drive_link) et placez-le dans `data/Bronze/`.

#### 2. Configurer les variables d'environnement (racine du projet)

Créez un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
```

Le fichier `.env.example` contient déjà des valeurs par défaut valides. Vous pouvez les garder telles quelles pour un environnement de développement.

**Contenu de `.env` :**
```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=postgres
DB_HOST=postgres
DB_PORT=5432
SUPERSET_SECRET_KEY=your_secret_key_change_in_production
```

#### 3. Configurer OpenMetadata (optionnel)

Si vous souhaitez déployer OpenMetadata pour le Data Catalog :

```bash
cp openmetadata/.env.example openmetadata/.env
```

Le fichier `.env.example` contient déjà des valeurs par défaut valides (mots de passe, clé Fernet, etc.). Vous pouvez les conserver pour un environnement de développement.

#### 4. Lancer les containers Docker

```bash
# Démarrer tous les services
docker-compose up -d

# Vérifier les logs (optionnel)
docker-compose logs -f airflow_standalone
```

**Premier démarrage** : Airflow prend ~2-3 minutes pour s'initialiser complètement.

#### 5. Accéder aux interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow** | http://localhost:8081 | admin / admin |
| **Jupyter Lab** | http://localhost:8888 | (pas de token requis) |
| **Superset** | http://localhost:8088 | admin / admin (après setup) |
| **Great Expectations** | http://localhost:8080 | (pas d'auth) |
| **OpenMetadata** (optionnel) | http://localhost:8585 | admin / admin |

### Lancer le pipeline Data Quality

1. Ouvrir Airflow : http://localhost:8081
2. Se connecter : `admin` / `admin`
3. Activer le DAG `data_quality_pipeline`
4. Cliquer sur "Trigger DAG" (▶️)

Le pipeline exécute :
- Chargement des données brutes dans PostgreSQL
- Analyse exploratoire (notebook 01)
- Nettoyage et transformation (notebook 02)
- Validation Great Expectations (notebook 03)
- Génération des rapports Evidently + SweetViz

### Notebooks Jupyter

Les notebooks sont disponibles dans `notebooks/` :

- `01_analyse_manuelle.ipynb` - Analyse exploratoire et profiling
- `02_nettoyage.ipynb` - Transformation Bronze → Silver → Gold
- `03_validation.ipynb` - Validation avec Great Expectations

Pour les exécuter manuellement :
1. Ouvrir Jupyter Lab : http://localhost:8888
2. Naviguer vers `work/notebooks/`

### Arrêter les services

```bash
# Arrêter les containers (garde les données)
docker-compose down

# Arrêter et supprimer les volumes (reset complet)
docker-compose down -v
```

## Troubleshooting

### Airflow ne démarre pas

Si vous voyez l'erreur "You need to initialize the database" :

```bash
docker-compose down -v
docker-compose up -d
```

Le flag `-v` supprime les volumes et force une réinitialisation propre.

### Port déjà utilisé

Si un port est déjà occupé, modifiez les ports dans `docker-compose.yml` :

```yaml
ports:
  - "8082:8080"  # Utiliser 8082 au lieu de 8081
```