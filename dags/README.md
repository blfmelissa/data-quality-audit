# DAGs Airflow - Pipeline Data Quality

## Structure

- `data_quality_pipeline.py`: DAG principal qui orchestre toutes les étapes du pipeline

## DAG: data_quality_pipeline

Pipeline complet de Data Quality pour Steam Games (exécuté quotidiennement).

### Tâches

1. **check_docker**: Vérifie que Docker est actif
2. **set_superset**: Configure Superset et connecte à PostgreSQL
2. **load_data**: Charge les données brutes dans PostgreSQL (Bronze layer)
3. **run_notebook_01_analyse_manuelle**: Profiling avec SweetViz
4. **run_notebook_02_nettoyage**: Nettoyage des données (Silver layer)
5. **run_notebook_03_validation**: Enrichissement et dimensions (Gold layer)
6. **generate_reports**: Génère les rapports Evidently + SweetViz
7. **run_validation**: Validation Great Expectations

### Accès

- Interface Web: http://localhost:8081
- Login: `admin` / `admin`

### Démarrage

```bash
# Démarrer tous les services (incluant Airflow)
docker-compose up -d

# Vérifier le statut d'Airflow
docker logs airflow_standalone

# Le DAG apparaîtra automatiquement dans l'interface web (il faut attendre quelques minutes)
```

### Notes

- Le DAG utilise `docker exec` pour appeler les scripts dans le container `dq_jupyter`
- Les containers doivent être démarrés via `docker-compose` avant de lancer les DAGs
- Le scheduler est configuré pour `@daily` mais peut être déclenché manuellement
