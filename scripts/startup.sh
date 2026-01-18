#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# 🔧 Logs a STDOUT (Cloud Logging = INFO)
# --------------------------------------------------
exec > >(tee /var/log/startup.log) 2>&1

log() {
  echo "[BOOT] $1"
}

fail() {
  echo "[BOOT][ERROR] $1"
  exit 1
}

log "🚀 Startup Jira ETL iniciado"

# --------------------------------------------------
# Metadata
# --------------------------------------------------
META="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
HEADER="Metadata-Flavor: Google"

# --------------------------------------------------
# Runtime config
# --------------------------------------------------
log "📥 Cargando RUNTIME_CONFIG_JSON"
export RUNTIME_CONFIG_JSON="$(curl -sf ${META}/RUNTIME_CONFIG_JSON -H "${HEADER}")" \
  || fail "No se pudo obtener RUNTIME_CONFIG_JSON"

# --------------------------------------------------
# GitHub token
# --------------------------------------------------
log "🔐 Cargando token GitHub"
GITHUB_TOKEN="$(curl -sf ${META}/GITHUB_TOKEN -H "${HEADER}")" \
  || fail "No se pudo obtener GITHUB_TOKEN"

# --------------------------------------------------
# Dependencias SO
# --------------------------------------------------
log "📦 Instalando dependencias SO"
apt-get update -y >/dev/null
apt-get install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  build-essential >/dev/null

log "✅ Dependencias SO instaladas"

# --------------------------------------------------
# Clonar repo
# --------------------------------------------------
cd /opt

if [ ! -d "Api_Jira" ]; then
  log "📥 Clonando repo Api_Jira"
  git clone -q https://${GITHUB_TOKEN}@github.com/drojas-haulmer/Api_Jira.git
else
  log "📦 Repo existente, actualizando"
  cd Api_Jira
  git pull -q
  cd ..
fi

cd Api_Jira

# --------------------------------------------------
# Python venv
# --------------------------------------------------
log "🐍 Creando entorno virtual"
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q

log "✅ Dependencias Python instaladas"

# --------------------------------------------------
# Ejecutar ETL
# --------------------------------------------------
log "▶️ Ejecutando Jira ETL"
python main.py || fail "ETL falló"

log "🏁 ETL finalizado correctamente"

# --------------------------------------------------
# ⏸ Suspender VM (Workflow decide borrado)
# --------------------------------------------------
log "⏸ Suspendiendo VM (Workflow se encarga del borrado)"
systemctl suspend
