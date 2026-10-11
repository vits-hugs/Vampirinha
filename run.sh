#!/usr/bin/env bash
# Cria um venv local (na primeira vez), instala o pygame e abre o jogo.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --quiet -r requirements.txt
fi
exec .venv/bin/python main.py "$@"
