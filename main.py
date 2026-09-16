# -*- coding: utf-8 -*-
"""Ponto de entrada do sistema de Alertas de Mercado da Integrity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nucleo.motor import executar  # noqa: E402

if __name__ == "__main__":
    executar()
