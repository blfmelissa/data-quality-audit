from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


default_args = {
    "owner": "data_quality_team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 0,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "openmetadata_deploy",
    default_args=default_args,
    description="Deploy OpenMetadata stack via deploy.py",
    schedule_interval=None,
    start_date=datetime(2026, 2, 6),
    catchup=False,
    tags=["openmetadata", "deploy"],
) as dag:
    deploy_openmetadata = BashOperator(
        task_id="deploy_openmetadata",
        bash_command="""
        set -e
        cd /opt/airflow/project/openmetadata
        python deploy.py
        """,
    )
