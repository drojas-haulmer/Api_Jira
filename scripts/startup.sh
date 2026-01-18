#!/bin/bash
set -e

LOG_FILE="/var/log/jira_etl.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "[BOOT] 🚀 Startup Jira ETL VM"

# -------------------------------
# Silenciar apt (CRÍTICO)
# -------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 \
  python3-venv \
  python3-pip \
  git \
  build-essential

echo "[BOOT] ✅ Dependencias SO instaladas"

# -------------------------------
# Código
# -------------------------------
cd /opt || exit 1

if [ ! -d Api_Jira ]; then
  echo "[BOOT] 📦 Clonando repo"
  git clone https://$GITHUB_TOKEN@github.com/drojas-haulmer/Api_Jira.git
fi

cd Api_Jira

python3 -m venv venv
source venv/bin/activate

pip install -q -r requirements.txt

echo "[BOOT] ▶️ Ejecutando ETL"
python main.py

echo "[BOOT] 🛑 Apagando VM"
shutdown -h now
