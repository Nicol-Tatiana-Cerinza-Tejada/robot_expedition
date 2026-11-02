#!/bin/sh
# Arranque de la API en el contenedor.
set -e
# La imagen no trae .git: DVC trabaja sin SCM.
dvc config --local core.no_scm true >/dev/null 2>&1 || true
# Credenciales del remoto DVC (secretos del Space; nunca en el repositorio).
if [ -n "$DVC_REMOTE_USER" ] && [ -n "$DVC_REMOTE_PASSWORD" ]; then
  dvc remote modify --local dagshub auth basic
  dvc remote modify --local dagshub user "$DVC_REMOTE_USER"
  dvc remote modify --local dagshub password "$DVC_REMOTE_PASSWORD"
fi
exec uvicorn api.main:app --host 0.0.0.0 --port "${PORT:-7860}"
