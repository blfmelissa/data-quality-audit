from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'data_quality_team',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'data_quality_pipeline',
    default_args=default_args,
    description='Pipeline complet de Data Quality pour Steam Games',
    schedule_interval='@daily',
    start_date=datetime(2026, 2, 6),
    catchup=False,
    tags=['data_quality', 'steam_games', 'profiling'],
) as dag:

    check_docker = BashOperator(
        task_id='check_docker',
        bash_command='echo "Vérification des containers..." && docker ps && echo "✅ Docker est actif et accessible"',
    )

    setup_superset = BashOperator(
        task_id='setup_superset',
        bash_command='''
        echo " Configuration de Superset..."
        
        echo " Installation pip et psycopg2..."
        docker exec -u root superset bash -c \
            "apt-get update && apt-get install -y curl && \
            curl -sS https://bootstrap.pypa.io/get-pip.py | python3"
        
        docker exec -u root superset python3 -m pip install psycopg2-binary
        
        echo "Initialisation Superset..."
        docker exec superset superset db upgrade
        docker exec superset superset fab create-admin \
            --username admin \
            --firstname Admin \
            --lastname User \
            --email admin@superset.com \
            --password admin || true
        docker exec superset superset init
        
        echo " Connexion à PostgreSQL..."
        docker exec superset superset set_database_uri \
            --database_name DataQualitySteamDB \
            --uri postgresql+psycopg2://postgres:postgres@postgres:5432/games_db
        
        echo "✅ Superset configuré sur http://localhost:8088"
        ''',
    )

    load_data = BashOperator(
        task_id='load_data',
        bash_command='''
        echo " Chargement des données dans PostgreSQL..."
        docker exec dq_jupyter python /home/jovyan/work/scripts/load_data_docker.py
        ''',
    )

    run_notebook_01 = BashOperator(
        task_id='run_notebook_01_analyse_manuelle',
        bash_command='''
        echo " Exécution notebook 01_analyse_manuelle.ipynb"
        docker exec dq_jupyter jupyter nbconvert \
            --to notebook \
            --execute /home/jovyan/work/notebooks/01_analyse_manuelle.ipynb \
            --inplace
        ''',
    )

    run_notebook_02 = BashOperator(
        task_id='run_notebook_02_nettoyage',
        bash_command='''
        echo " Exécution notebook 02_nettoyage.ipynb"
        docker exec dq_jupyter jupyter nbconvert \
            --to notebook \
            --execute /home/jovyan/work/notebooks/02_nettoyage.ipynb \
            --inplace
        ''',
    )

    run_notebook_03 = BashOperator(
        task_id='run_notebook_03_validation',
        bash_command='''
        echo " Exécution notebook 03_validation.ipynb"
        docker exec dq_jupyter jupyter nbconvert \
            --to notebook \
            --execute /home/jovyan/work/notebooks/03_validation.ipynb \
            --inplace
        ''',
    )

    generate_reports = BashOperator(
        task_id='generate_reports',
        bash_command='''
        echo " Génération des rapports Evidently + SweetViz..."
        docker exec dq_jupyter python /home/jovyan/work/scripts/generate_reports.py
        ''',
    )

    run_validation = BashOperator(
        task_id='run_validation',
        bash_command='''
        echo "Validation Great Expectations..."
        docker exec dq_jupyter python /home/jovyan/work/scripts/run_validation.py
        ''',
    )

    check_docker >> setup_superset >> load_data >> run_notebook_01 >> run_notebook_02 >> run_notebook_03 >> generate_reports >> run_validation
