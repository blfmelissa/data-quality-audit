#!/usr/bin/env python
"""Script standalone pour exécuter la validation Great Expectations et stocker les résultats."""

import pandas as pd
import great_expectations as gx
from sqlalchemy import create_engine
from datetime import datetime
import os
import sys
from dotenv import load_dotenv

# Charger la configuration depuis .env
load_dotenv()

DB_HOST = os.getenv('DB_HOST', 'host.docker.internal')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('POSTGRES_DB', 'games_db')
DB_USER = os.getenv('POSTGRES_USER', 'postgres')
DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def run_validation():
    print("Loading data from PostgreSQL...")
    
    try:
        engine = create_engine(CONNECTION_STRING)
        df = pd.read_sql("SELECT * FROM games_gold", engine)
        print(f"Loaded {len(df):,} rows from PostgreSQL")
    except Exception as e:
        print(f"PostgreSQL error: {e}")
        print("Fallback to CSV file...")
        df = pd.read_csv('data/Gold/games_gold.csv')
        print(f"Loaded {len(df):,} rows from CSV")

    # Déterminer le bon répertoire racine (support Docker et local)
    project_root = "/home/jovyan/work" if os.path.exists("/home/jovyan/work/gx") else "."
    context = gx.get_context(mode="file", project_root_dir=project_root)

    try:
        checkpoint = context.checkpoints.get("games_checkpoint")
    except Exception as e:
        print(f"Checkpoint not found: {e}")
        print("Run the validation notebook first to create the checkpoint")
        return False

    print("Running validation...")
    result = checkpoint.run(batch_parameters={"dataframe": df})

    run_results = list(result.run_results.values())[0]
    stats = run_results.statistics

    print(f"\nResults:")
    print(f"  Success: {result.success}")
    print(f"  Evaluated: {stats['evaluated_expectations']}")
    print(f"  Successful: {stats['successful_expectations']}")
    print(f"  Failed: {stats['unsuccessful_expectations']}")

    try:
        engine = create_engine(CONNECTION_STRING)
        result_df = pd.DataFrame([{
            'run_id': datetime.now().isoformat(),
            'expectation_suite': 'games_quality_suite',
            'success': result.success,
            'evaluated_expectations': stats['evaluated_expectations'],
            'successful_expectations': stats['successful_expectations'],
            'unsuccessful_expectations': stats['unsuccessful_expectations']
        }])
        result_df.to_sql('validation_results', engine, if_exists='append', index=False)
        print("Results stored in PostgreSQL table 'validation_results'")
    except Exception as e:
        print(f"Could not store in DB: {e}")

    context.build_data_docs()
    print("Data Docs updated at gx/uncommitted/data_docs/local_site/index.html")

    return result.success

if __name__ == '__main__':
    success = run_validation()
    sys.exit(0 if success else 1)
