# -*- coding: utf-8 -*-
"""
Conector do dólar (USD/BRL).

Fonte primária: AwesomeAPI (gratuita, sem chave, quase em tempo real).
Fonte alternativa: open.er-api.com (gratuita, sem chave, atualização diária) —
usada apenas se a primária falhar mesmo após as tentativas de retry, para não
deixar o indicador "cego" em caso de instabilidade/rate limit da fonte principal.

As duas fontes informam quando o dado foi gerado (data_hora); o motor usa
isso para não disparar alerta com cotação defasada.
"""
import logging
import time

import requests

from nucleo.relogio import de_timestamp

from .base import Conector, Leitura

URL_DOLAR = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
URL_DOLAR_FALLBACK = "https://open.er-api.com/v6/latest/USD"
# Algumas APIs recusam o identificador padrão do Python ("python-requests");
# nos apresentamos como navegador, como já é feito no conector do Tesouro.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
TIMEOUT = 30
TENTATIVAS = 3
ESPERA_INICIAL_SEGUNDOS = 3  # dobra a cada nova tentativa (3s, 6s, 12s)


def _fmt_brl(valor: float, casas: int = 4) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _descrever_erro(e: Exception) -> str:
    """Texto curto do erro, com status HTTP e início da resposta quando houver."""
    resposta = getattr(e, "response", None)
    if resposta is not None:
        trecho = " ".join(resposta.text[:200].split())
        return f"HTTP {resposta.status_code} — {trecho}"
    return f"{type(e).__name__}: {e}"


def _consultar_awesomeapi():
    r = requests.get(URL_DOLAR, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()["USDBRL"]
    data_hora = de_timestamp(int(d["timestamp"]))
    return Leitura(
        valor=float(d["bid"]),
        valor_formatado=f"R$ {_fmt_brl(float(d['bid']))}",
        variacao=float(d.get("pctChange") or 0),
        variacao_sufixo="% no dia",
        fonte="AwesomeAPI",
        detalhes=[
            ("Referência", "Cotação de compra (bid)"),
            ("Horário da cotação", f"{data_hora:%d/%m %H:%M}"),
        ],
        data_hora=data_hora,
    )


def _consultar_fallback():
    r = requests.get(URL_DOLAR_FALLBACK, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    bid = float(d["rates"]["BRL"])
    data_hora = de_timestamp(int(d["time_last_update_unix"]))
    return Leitura(
        valor=bid,
        valor_formatado=f"R$ {_fmt_brl(bid)}",
        variacao=None,
        fonte="open.er-api.com (fonte alternativa — sem variação intradiária)",
        detalhes=[
            ("Referência", "Taxa de câmbio de referência"),
            ("Horário da cotação", f"{data_hora:%d/%m %H:%M}"),
        ],
        data_hora=data_hora,
        fonte_alternativa=True,
    )


class DolarConector(Conector):
    def consultar(self, parametros: dict) -> Leitura:
        ultimo_erro = None
        espera = ESPERA_INICIAL_SEGUNDOS

        for tentativa in range(1, TENTATIVAS + 1):
            try:
                return _consultar_awesomeapi()
            except Exception as e:
                ultimo_erro = _descrever_erro(e)
                logging.warning("dolar | AwesomeAPI falhou (tentativa %s/%s): %s",
                                tentativa, TENTATIVAS, ultimo_erro)
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
                f"fonte alternativa também falhou ({_descrever_erro(e)})"
            ) from e
