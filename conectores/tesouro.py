# -*- coding: utf-8 -*-
"""
Conector de títulos públicos do Tesouro Direto via CSV oficial do
Tesouro Transparente/Tesouro Nacional — gratuito, sem chave, atualização
diária (manhã do primeiro dia útil após o fechamento do mercado).

O CSV é baixado no máximo uma vez por execução (cache em memória do
processo), mesmo que vários títulos estejam configurados.
"""
import csv
import io
from datetime import datetime

import requests

from .base import Conector, Leitura

URL_TESOURO_CSV = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
TIMEOUT = 60

_CACHE = None  # lista de linhas do CSV, preenchida na primeira consulta da execução


def _br_float(s):
    """Converte número no formato brasileiro: '1.050,55' -> 1050.55"""
    if not s or not str(s).strip():
        return None
    try:
        return float(str(s).strip().replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _fmt_brl(valor: float, casas: int = 2) -> str:
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _baixar_csv():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    r = requests.get(URL_TESOURO_CSV, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    texto = r.content.decode("latin-1")
    _CACHE = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    return _CACHE


class TesouroConector(Conector):
    def consultar(self, parametros: dict):
        tipo_alvo = parametros["tipo"].strip().lower()
        ano = str(parametros["ano_venc"])
        taxa_ref_campo = parametros.get("taxa_ref", "compra")
        eh_ipca = parametros.get("unidade") == "ipca"

        try:
            linhas = _baixar_csv()
        except Exception as e:
            raise RuntimeError(f"erro ao baixar CSV oficial do Tesouro: {e}") from e

        candidatos = [
            row for row in linhas
            if (row.get("Tipo Titulo") or "").strip().lower() == tipo_alvo
            and (row.get("Data Vencimento") or "").strip().endswith(ano)
        ]
        if not candidatos:
            # fonte respondeu normalmente, título não encontrado -> None (não é erro)
            return None

        candidatos.sort(
            key=lambda x: datetime.strptime(x["Data Base"].strip(), "%d/%m/%Y"),
            reverse=True,
        )
        row = candidatos[0]

        taxa_compra = _br_float(row.get("Taxa Compra Manha")) or 0
        taxa_resgate = _br_float(row.get("Taxa Venda Manha")) or 0
        pu_compra = _br_float(row.get("PU Compra Manha")) or 0
        pu_resgate = _br_float(row.get("PU Venda Manha")) or 0

        taxa = taxa_compra if taxa_ref_campo == "compra" else taxa_resgate
        # título temporariamente fora de oferta de compra vem com taxa zerada;
        # usa a taxa de resgate para não silenciar o alerta nesse caso
        if taxa == 0 and taxa_resgate > 0:
            taxa = taxa_resgate

        var_pp = None
        if len(candidatos) > 1:
            taxa_ant = _br_float(candidatos[1].get("Taxa Compra Manha"))
            if taxa_ant is not None:
                var_pp = round(taxa_compra - taxa_ant, 2)

        prefixo = "IPCA + " if eh_ipca else ""
        valor_formatado = f"{prefixo}{taxa:.2f}%".replace(".", ",") + " a.a."

        return Leitura(
            valor=taxa,
            valor_formatado=valor_formatado,
            variacao=var_pp,
            variacao_sufixo=" p.p. vs. dia anterior",
            fonte=f"Tesouro Nacional (base {row['Data Base'].strip()})",
            data_base=row["Data Base"].strip(),
            detalhes=[
                ("Taxa de compra", f"{prefixo}{taxa_compra:.2f}%".replace(".", ",")
                    + f" · PU R$ {_fmt_brl(pu_compra)}"),
                ("Taxa de resgate", f"{prefixo}{taxa_resgate:.2f}%".replace(".", ",")
                    + f" · PU R$ {_fmt_brl(pu_resgate)}"),
            ],
        )
