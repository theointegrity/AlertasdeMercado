# -*- coding: utf-8 -*-
"""
Controle de estado e anti-spam.

Regra: no máximo 1 alerta por indicador por dia civil. Se o indicador
atingir o gatilho várias vezes no mesmo dia (ou continuar disparando em
todas as consultas), só a primeira gera e-mail. No dia seguinte, o
contador reinicia — se ainda estiver disparando, pode alertar de novo.
O "dia" é sempre o de Brasília (ver nucleo/relogio.py).
"""
import json
from pathlib import Path

from nucleo.relogio import agora


def _hoje() -> str:
    return agora().date().isoformat()


class GerenciadorEstado:
    def __init__(self, caminho: Path):
        self.caminho = caminho
        self.estado = self._carregar()

    def _carregar(self) -> dict:
        if self.caminho.exists():
            try:
                return json.loads(self.caminho.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.caminho.write_text(
            json.dumps(self.estado, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def deve_alertar(self, indicador_id: str, disparou: bool) -> bool:
        info = self.estado.get(indicador_id, {})

        if not disparou:
            self.estado[indicador_id] = info
            return False

        hoje = _hoje()
        if info.get("ultimo_alerta_data") == hoje:
            return False

        info["ultimo_alerta_data"] = hoje
        self.estado[indicador_id] = info
        return True

    def frequencia_diaria_ja_consultada_hoje(self, indicador_id: str) -> bool:
        chave = f"_consultado_diario_{indicador_id}"
        return self.estado.get(chave) == _hoje()

    def marcar_consulta_diaria(self, indicador_id: str) -> None:
        chave = f"_consultado_diario_{indicador_id}"
        self.estado[chave] = _hoje()

    def registrar_saude_fonte(self, indicador_id: str, principal_ok: bool) -> int:
        """Conta rodadas seguidas com a fonte principal falhando. Devolve o total atual."""
        chave = f"_falhas_seguidas_{indicador_id}"
        self.estado[chave] = 0 if principal_ok else self.estado.get(chave, 0) + 1
        return self.estado[chave]

    def aviso_saude_ja_enviado_hoje(self) -> bool:
        return self.estado.get("_aviso_saude_data") == _hoje()

    def marcar_aviso_saude_enviado(self) -> None:
        self.estado["_aviso_saude_data"] = _hoje()
