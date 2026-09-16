# -*- coding: utf-8 -*-
"""Conector do dólar (USD/BRL) via AwesomeAPI — gratuita, sem chave, tempo real."""
import requests

from .base import Conector, Leitura

URL_DOLAR = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
TIMEOUT = 30


def _fmt_brl(valor: float, casas: int = 4) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


class DolarConector(Conector):
    def consultar(self, parametros: dict) -> Leitura:
        try:
            r = requests.get(URL_DOLAR, timeout=TIMEOUT)
            r.raise_for_status()
            d = r.json()["USDBRL"]
        except Exception as e:
            raise RuntimeError(f"erro ao consultar AwesomeAPI: {e}") from e

        bid = float(d["bid"])
        pct = float(d.get("pctChange") or 0)

        return Leitura(
            valor=bid,
            valor_formatado=f"R$ {_fmt_brl(bid)}",
            variacao=pct,
            variacao_sufixo="% no dia",
            fonte="AwesomeAPI",
            detalhes=[("Referência", "Cotação de compra (bid)")],
        )
