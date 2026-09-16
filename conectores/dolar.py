# -*- coding: utf-8 -*-
"""
Conector do dólar (USD/BRL).

Fonte primária: AwesomeAPI (gratuita, sem chave, quase em tempo real).
Fonte alternativa: open.er-api.com (gratuita, sem chave, atualização diária) —
usada apenas se a primária falhar mesmo após as tentativas de retry, para não
deixar o indicador "cego" em caso de instabilidade/rate limit da fonte principal.
"""
import time

import requests

from .base import Conector, Leitura

URL_DOLAR = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
URL_DOLAR_FALLBACK = "https://open.er-api.com/v6/latest/USD"
TIMEOUT = 30
TENTATIVAS = 3
ESPERA_INICIAL_SEGUNDOS = 3  # dobra a cada nova tentativa (3s, 6s, 12s)


def _fmt_brl(valor: float, casas: int = 4) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _consultar_awesomeapi():
    r = requests.get(URL_DOLAR, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()["USDBRL"]
    return Leitura(
        valor=float(d["bid"]),
        valor_formatado=f"R$ {_fmt_brl(float(d['bid']))}",
        variacao=float(d.get("pctChange") or 0),
        variacao_sufixo="% no dia",
        fonte="AwesomeAPI",
        detalhes=[("Referência", "Cotação de compra (bid)")],
    )


def _consultar_fallback():
    r = requests.get(URL_DOLAR_FALLBACK, timeout=TIMEOUT)
    r.raise_for_status()
    bid = float(r.json()["rates"]["BRL"])
    return Leitura(
        valor=bid,
        valor_formatado=f"R$ {_fmt_brl(bid)}",
        variacao=None,
        fonte="open.er-api.com (fonte alternativa — sem variação intradiária)",
        detalhes=[("Referência", "Taxa de câmbio de referência")],
    )


class DolarConector(Conector):
    def consultar(self, parametros: dict) -> Leitura:
        ultimo_erro = None
        espera = ESPERA_INICIAL_SEGUNDOS

        for tentativa in range(1, TENTATIVAS + 1):
            try:
                return _consultar_awesomeapi()
            except Exception as e:
                ultimo_erro = e
                if tentativa < TENTATIVAS:
                    time.sleep(espera)
                    espera *= 2

        # Fonte primária falhou em todas as tentativas: tenta a alternativa
        # antes de desistir e reportar erro.
        try:
            return _consultar_fallback()
        except Exception as e:
            raise RuntimeError(
                f"AwesomeAPI falhou após {TENTATIVAS} tentativas ({ultimo_erro}); "
                f"fonte alternativa também falhou ({e})"
            ) from e
