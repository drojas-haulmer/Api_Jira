#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# 🔧 Logs a STDOUT (Cloud Logging)
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
META_BASE="http://metadata.google.internal/computeMetadata/v1"
ATTR="${META_BASE}/instance/attributes"
HEADER="Metadata-Flavor: Google"

PROJECT_ID="$(curl -sf ${META_BASE}/project/project-id -H "${HEADER}")"
ZONE="$(curl -sf ${META_BASE}/instance/zone -H "${HEADER}" | awk -F/ '{print $NF}')"
INSTANCE_NAME="$(curl -sf ${META_BASE}/instance/name -H "${HEADER}")"

log "🧠 VM detectada → ${PROJECT_ID} / ${ZONE} / ${INSTANCE_NAME}"

# --------------------------------------------------
# Runtime config
# --------------------------------------------------
log "📥 Cargando RUNTIME_CONFIG_JSON"
export RUNTIME_CONFIG_JSON="$(curl -sf ${ATTR}/RUNTIME_CONFIG_JSON -H "${HEADER}")" \
  || fail "No se pudo obtener RUNTIME_CONFIG_JSON"

# --------------------------------------------------
# GitHub token
# --------------------------------------------------
log "🔐 Cargando token GitHub"
GITHUB_TOKEN="$(curl -sf ${ATTR}/GITHUB_TOKEN -H "${HEADER}")" \
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
  build-essential \
  curl >/dev/null

log "✅ Dependencias SO instaladas"

# --------------------------------------------------
# Clonar repo
# --------------------------------------------------
cd /opt

if [ ! -d "Api_Jira" ]; then
  log "📥 Clonando repo Api_Jira"
  git clone -q https://x-access-token:${GITHUB_TOKEN}@github.com/drojas-haulmer/Api_Jira.git
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
# 💣 AUTODESTRUCCIÓN DE LA VM
# --------------------------------------------------
log "💣 Eliminando VM desde dentro"

ACCESS_TOKEN="$(curl -sf ${META_BASE}/instance/service-accounts/default/token \
  -H "${HEADER}" | python3 -c 'import sys, json; print(json.load(sys.stdin)["access_token"])')"

DELETE_URL="https://compute.googleapis.com/compute/v1/projects/${PROJECT_ID}/zones/${ZONE}/instances/${INSTANCE_NAME}"

curl -sf -X DELETE \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${DELETE_URL}"

log "🧨 Solicitud de eliminación enviada. La VM desaparecerá ahora."
