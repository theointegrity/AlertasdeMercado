# -*- coding: utf-8 -*-
"""
Controle de estado e anti-spam.

Regra principal (histerese): um indicador só dispara um NOVO alerta quando
CRUZA para dentro da região do gatilho (estava fora, passou a estar dentro).
Enquanto permanece dentro, não repete. Se sair e voltar a entrar, dispara
de novo.

Cooldown: dentro do momento em que o indicador CRUZA para dentro do
gatilho, um cooldown mínimo (cooldown_horas) evita que oscilações de
ruído bem em cima da linha do gatilho (ex.: 5,099 / 5,101 / 5,099 a cada
consulta) gerem alertas repetidos em sequência.
"""
import json
from datetime import datetime, timedelta
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

    def deve_alertar(self, indicador_id: str, disparou: bool, cooldown_horas: float = 2.0) -> bool:
        info = self.estado.get(indicador_id, {"dentro": False, "ultimo_alerta": None})
        estava_dentro = info.get("dentro", False)

        if not disparou:
            info["dentro"] = False
            self.estado[indicador_id] = info
            return False

        cruzou_agora = not estava_dentro
        alertar = False

        if cruzou_agora:
            ultimo = info.get("ultimo_alerta")
            dentro_cooldown = False
            if ultimo:
                dentro_cooldown = (
                    datetime.now() - datetime.fromisoformat(ultimo)
                ) < timedelta(hours=cooldown_horas)
            alertar = not dentro_cooldown

        info["dentro"] = True
        if alertar:
            info["ultimo_alerta"] = datetime.now().isoformat()
        self.estado[indicador_id] = info
        return alertar

    def frequencia_diaria_ja_consultada_hoje(self, indicador_id: str) -> bool:
        from datetime import date
        chave = f"_consultado_diario_{indicador_id}"
        return self.estado.get(chave) == date.today().isoformat()

    def marcar_consulta_diaria(self, indicador_id: str) -> None:
        from datetime import date
        chave = f"_consultado_diario_{indicador_id}"
        self.estado[chave] = date.today().isoformat()
