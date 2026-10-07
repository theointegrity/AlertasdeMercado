# -*- coding: utf-8 -*-
"""
Relógio único do sistema, sempre no horário de Brasília.

O GitHub Actions roda em UTC (3h à frente de Brasília). Todo o código
deve usar agora() daqui, nunca datetime.now() direto, para que logs,
e-mails e o controle de estado usem o mesmo fuso.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

FUSO = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    return datetime.now(FUSO)


def de_timestamp(segundos: float) -> datetime:
    """Converte um timestamp Unix (como as APIs informam) para horário de Brasília."""
    return datetime.fromtimestamp(segundos, FUSO)
