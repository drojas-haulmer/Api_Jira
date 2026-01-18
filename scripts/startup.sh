#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] 🚀 Iniciando Jira ETL en VM $(hostname)"

export HOME=/root
export JIRA_PROJECT_KEY=RTN
export TARGET_TABLE=RTN_project_raw
export RUNTIME_CONFIG_JSON=1

echo "[INFO] 📦 Instalando dependencias del sistema"
apt-get update -y
apt-get install -y git python3 python3-pip python3-venv

echo "[INFO] 🔐 Obteniendo GitHub token"
TOKEN=$(curl -s \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/GITHUB_TOKEN \
  -H "Metadata-Flavor: Google")
export GITHUB_TOKEN="$(echo "$TOKEN" | base64 --decode)"

echo "[INFO] 📁 Clonando repositorio"
cd /opt
git clone https://x-access-token:${GITHUB_TOKEN}@github.com/drojas-haulmer/Api_Jira.git
cd Api_Jira

echo "[INFO] 🐍 Creando entorno virtual"
python3 -m venv venv
source venv/bin/activate

echo "[INFO] 📦 Instalando dependencias Python"
pip install --upgrade pip
pip install -r requirements.txt

echo "[INFO] 🚀 Ejecutando ETL"
python main.py

echo "[INFO] 🧹 Apagando VM"
shutdown -h now
