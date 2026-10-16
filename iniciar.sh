#!/usr/bin/env bash
# ==============================================================================
# Script de inicio rápido para SIGE-UBE API (Arch Linux / Bash)
# Inicia el servicio de PostgreSQL si está inactivo y levanta el servidor Django.
# ==============================================================================

set -e

# Colores para la terminal
VERDE='\033[0;32m'
AZUL='\033[0;34m'
AMARILLO='\033[1;33m'
ROJO='\033[0;31m'
NC='\033[0m' # Sin color

# Directorio del script (raíz del proyecto)
DIR_PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR_PROYECTO"

echo -e "${AZUL}==> Verificando estado de PostgreSQL...${NC}"

if systemctl is-active --quiet postgresql; then
    echo -e "${VERDE}✔ PostgreSQL ya está activo.${NC}"
else
    echo -e "${AMARILLO}⚠ PostgreSQL está inactivo. Iniciando servicio con sudo...${NC}"
    sudo systemctl start postgresql
    if systemctl is-active --quiet postgresql; then
        echo -e "${VERDE}✔ PostgreSQL iniciado correctamente.${NC}"
    else
        echo -e "${ROJO}✖ Error: No se pudo iniciar el servicio de PostgreSQL.${NC}"
        exit 1
    fi
fi

# Verificar entorno virtual
PYTHON_BIN="$DIR_PROYECTO/venv/bin/python"
if [ ! -f "$PYTHON_BIN" ]; then
    echo -e "${ROJO}✖ No se encontró el entorno virtual en: $DIR_PROYECTO/venv${NC}"
    echo -e "Crea el entorno con: python3.11 -m venv venv && ./venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo -e "${VERDE}✔ Entorno virtual detectado.${NC}"
echo -e "${AZUL}==> Iniciando servidor Django en http://0.0.0.0:8000/ (Ctrl+C para salir)...${NC}"
echo ""

exec "$PYTHON_BIN" manage.py runserver 0.0.0.0:8000
