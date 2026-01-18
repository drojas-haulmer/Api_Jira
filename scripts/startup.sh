#!/bin/bash
set -euo pipefail

echo "[BOOT] 🚀 Startup Jira ETL iniciado"

# --------------------------------------------------
# Helpers
# --------------------------------------------------
log() {
  echo "[BOOT] $1"
}

fail() {
  echo "[BOOT][ERROR] $1"
  shutdown -h now
  exit 1
}

# --------------------------------------------------
# Metadata helper
# --------------------------------------------------
META="http://metadata.google.internal/computeMetadata/v1/instance/attributes"
HEADER="Metadata-Flavor: Google"

# --------------------------------------------------
# Export runtime config
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
log "📦 Instalando dependencias del sistema"
apt-get update -y
apt-get install -y \
  git \
  python3 \
  python3-venv \
  python3-pip \
  build-essential

log "✅ Dependencias SO instaladas"

# --------------------------------------------------
# Clonar repo
# --------------------------------------------------
cd /opt

if [ ! -d "Api_Jira" ]; then
  log "📥 Clonando repo Api_Jira"
  git clone https://${GITHUB_TOKEN}@github.com/drojas-haulmer/Api_Jira.git
else
  log "📦 Repo ya existe, actualizando"
  cd Api_Jira
  git pull
  cd ..
fi

cd Api_Jira

# --------------------------------------------------
# Entorno virtual
# --------------------------------------------------
log "🐍 Creando entorno virtual"
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

log "✅ Dependencias Python instaladas"

# --------------------------------------------------
# Ejecutar ETL
# --------------------------------------------------
log "▶️ Ejecutando Jira ETL"
python main.py \
  && log "🏁 ETL finalizado correctamente" \
  || fail "ETL falló"

# --------------------------------------------------
# Apagar VM (esto dispara el delete del Workflow)
# --------------------------------------------------
log "🧹 Apagando VM"
shutdown -h now
