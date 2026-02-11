#!/bin/bash
set -e

echo 'Installation Docker CLI officiel et PostgreSQL client...'
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release postgresql-client
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bullseye stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce-cli
echo '✅ Docker CLI installé'
docker version --format 'API version: {{.Client.APIVersion}}'

echo '⏳ Attente base airflow_db...'
until PGPASSWORD=postgres psql -h postgres -U postgres -tAc "select 1 from pg_database where datname='airflow_db'" | grep -q 1; do
  echo 'airflow_db pas encore prête...'
  sleep 2
done
echo '✅ Base airflow_db prête'

echo 'Initialisation Airflow...'
gosu airflow airflow db migrate

echo 'Création utilisateur admin...'
gosu airflow airflow users create \
  --username admin \
  --password admin \
  --firstname Admin \
  --lastname User \
  --role Admin \
  --email admin@example.com || true

echo 'Démarrage Airflow webserver et scheduler...'
gosu airflow airflow webserver &
gosu airflow airflow scheduler
