#!/usr/bin/env bash
# Comando de build en Render (Build Command: bash build.sh).
# Instala dependencias, prepara estáticos del admin, aplica migraciones y crea los usuarios iniciales.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py crear_usuarios_iniciales

# Opcional: con la variable POS_CARGAR_DEMO=True se carga un catálogo de ejemplo
# (no duplica registros si ya existen).
if [ "${POS_CARGAR_DEMO:-False}" = "True" ]; then
  python manage.py cargar_datos_demo
fi
