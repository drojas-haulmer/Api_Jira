#!/bin/bash
set -e

echo "[INFO] 🚀 Iniciando Jira ETL"

export HOME=/root

# ================================
# ✅ RUNTIME CONFIG (JSON REAL)
# ================================
export RUNTIME_CONFIG_JSON='{
  "jira_project_key": "RTN",
  "bq_project_id": "haulmer-ucloud-production",
  "bq_dataset_id": "Jira"
}'

echo "[INFO] 📦 Instalando dependencias base"
apt-get update -y
apt-get install -y git python3 python3-pip python3-venv

echo "[INFO] 📁 Clonando repositorio"
cd /opt
git clone https://github.com/drojas-haulmer/Api_Jira.git
cd Api_Jira

echo "[INFO] 🐍 Creando entorno virtual"
python3 -m venv venv
source venv/bin/activate

echo "[INFO] 📦 Instalando requirements"
pip install --upgrade pip
pip install -r requirements.txt

echo "[INFO] 🚀 Ejecutando ETL"
python main.py

echo "[INFO] 🧹 Apagando VM"
shutdown -h now
