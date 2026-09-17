# -*- coding: utf-8 -*-
"""
Controle de estado e anti-spam.

Regra: no máximo 1 alerta por indicador por dia civil. Se o indicador
atingir o gatilho várias vezes no mesmo dia (ou continuar disparando em
todas as consultas), só a primeira gera e-mail. No dia seguinte, o
contador reinicia — se ainda estiver disparando, pode alertar de novo.
"""
import json
from datetime import date
from pathlib import Path


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

        hoje = date.today().isoformat()
        if info.get("ultimo_alerta_data") == hoje:
            return False

        info["ultimo_alerta_data"] = hoje
        self.estado[indicador_id] = info
        return True

    def frequencia_diaria_ja_consultada_hoje(self, indicador_id: str) -> bool:
        chave = f"_consultado_diario_{indicador_id}"
        return self.estado.get(chave) == date.today().isoformat()

    def marcar_consulta_diaria(self, indicador_id: str) -> None:
        chave = f"_consultado_diario_{indicador_id}"
        self.estado[chave] = date.today().isoformat()
