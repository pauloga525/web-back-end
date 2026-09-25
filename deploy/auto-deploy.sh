#!/usr/bin/env bash
# Revisa si hay commits nuevos en la rama y, si los hay, actualiza el código
# y reinicia el servicio. Lo ejecuta web-back-end-deploy.timer cada minuto.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/oracle/Escritorio/WEB-UETS/web-back-end}"
BRANCH="${BRANCH:-main}"
SERVICE="${SERVICE:-web-back-end}"

cd "$APP_DIR"

git fetch --quiet origin "$BRANCH"
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse "origin/$BRANCH")

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

echo "Nuevo commit en $BRANCH: ${LOCAL:0:7} -> ${REMOTE:0:7}"

OLD_REQ=$(git rev-parse HEAD:requirements.txt)
# --ff-only: si alguien editó archivos a mano en el servidor, falla en vez de
# pisar esos cambios. El .env y uploads/ están en .gitignore y no se tocan.
git merge --ff-only "origin/$BRANCH"

if [ "$OLD_REQ" != "$(git rev-parse HEAD:requirements.txt)" ]; then
  echo "requirements.txt cambió, instalando dependencias"
  .venv/bin/pip install -r requirements.txt
fi

sudo /usr/bin/systemctl restart "$SERVICE"
echo "Servicio $SERVICE reiniciado en ${REMOTE:0:7}"
