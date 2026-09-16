# -*- coding: utf-8 -*-
"""
Motor principal: lê a configuração, consulta cada indicador ativo,
avalia os gatilhos com histerese, consolida em um único e-mail e envia.

Este arquivo NÃO conhece detalhes de nenhum indicador específico — cada
um é um "conector" plugável (ver conectores/). Para adicionar um novo
indicador no futuro, normalmente não é preciso tocar neste arquivo (só
registrar a classe do conector no dicionário CONECTORES, se for um tipo
de fonte novo).
"""
import logging
from datetime import datetime
from pathlib import Path

import yaml

from conectores.dolar import DolarConector
from conectores.tesouro import TesouroConector
from nucleo.estado import GerenciadorEstado
from nucleo.email import bloco_metrica, corpo_email, enviar_email

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
LOGS_DIR = BASE_DIR / "logs"
ESTADO_PATH = LOGS_DIR / "estado.json"
LOG_PATH = LOGS_DIR / "alerta_mercado.log"

# Registro de conectores disponíveis. Para adicionar um indicador que usa
# uma fonte totalmente nova (ex.: BCB SGS para Selic/CDI), crie o conector
# em conectores/ e registre-o aqui com uma chave nova.
CONECTORES = {
    "dolar": DolarConector(),
    "tesouro": TesouroConector(),
}

SIMBOLO_OPERADOR = {">=": "&ge;", "<=": "&le;", ">": "&gt;", "<": "&lt;"}


def _configurar_log() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(message)s",
        datefmt="%d/%m/%Y %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _carregar_yaml(nome: str):
    with open(CONFIG_DIR / nome, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _avaliar(valor: float, operador: str, gatilho: float) -> bool:
    if operador == ">=":
        return valor >= gatilho
    if operador == "<=":
        return valor <= gatilho
    if operador == ">":
        return valor > gatilho
    if operador == "<":
        return valor < gatilho
    raise ValueError(f"operador inválido: {operador}")


def _deve_pular_por_frequencia(cfg: dict, gerente: GerenciadorEstado) -> bool:
    """Para indicadores 'diario': só consulta 1x/dia, após a hora de corte."""
    if cfg.get("frequencia") != "diario":
        return False
    if datetime.now().hour < cfg.get("hora_corte", 0):
        return True
    return gerente.frequencia_diaria_ja_consultada_hoje(cfg["id"])


def executar() -> None:
    _configurar_log()
    indicadores = _carregar_yaml("indicadores.yaml") or []
    destinatarios_cfg = _carregar_yaml("destinatarios.yaml") or {}
    destinatarios = [e.strip() for e in destinatarios_cfg.get("destinatarios", []) if e and e.strip()]

    gerente = GerenciadorEstado(ESTADO_PATH)
    blocos = []
    rotulos_disparados = []

    for cfg in indicadores:
        indicador_id = cfg["id"]

        if not cfg.get("ativo", True):
            continue

        if _deve_pular_por_frequencia(cfg, gerente):
            logging.info("%s | pulado (frequência diária: fora do horário ou já consultado hoje)", indicador_id)
            continue

        conector = CONECTORES.get(cfg["conector"])
        if conector is None:
            logging.error("%s | conector '%s' não registrado em CONECTORES", indicador_id, cfg["conector"])
            continue

        try:
            leitura = conector.consultar(cfg.get("parametros", {}))
        except Exception as e:
            # Falha na fonte NUNCA é interpretada como gatilho atingido.
            # Uma fonte com problema não impede a consulta das demais.
            logging.error("%s | ERRO na consulta: %s", indicador_id, e)
            continue

        if cfg.get("frequencia") == "diario":
            gerente.marcar_consulta_diaria(indicador_id)

        if leitura is None:
            logging.warning("%s | fonte respondeu, mas o dado não foi encontrado", indicador_id)
            continue

        disparou = _avaliar(leitura.valor, cfg["operador"], cfg["gatilho"])
        logging.info(
            "%s | %s | gatilho %s %s | %s",
            indicador_id, leitura.valor_formatado, cfg["operador"], cfg["gatilho"],
            "DENTRO DO GATILHO" if disparou else "fora do gatilho",
        )

        if gerente.deve_alertar(indicador_id, disparou, cfg.get("cooldown_horas", 2)):
            logging.info("%s | ALERTA DISPARADO", indicador_id)
            gatilho_txt = f"{SIMBOLO_OPERADOR[cfg['operador']]} {cfg['gatilho']}"
            blocos.append(bloco_metrica(cfg["rotulo"], gatilho_txt, leitura))
            rotulos_disparados.append(cfg["rotulo"])

    if not blocos:
        logging.info("Nenhum novo alerta nesta rodada.")
        gerente.salvar()
        return

    if len(blocos) > 1:
        assunto = f"[ALERTA DE MERCADO] {len(blocos)} indicadores atingiram os níveis monitorados"
    else:
        assunto = f"[ALERTA DE MERCADO] {rotulos_disparados[0]}"

    try:
        enviar_email(assunto, corpo_email("".join(blocos)), destinatarios)
        logging.info("E-mail enviado para %s destinatário(s): %s", len(destinatarios), assunto)
        gerente.salvar()
    except Exception as e:
        logging.error("ERRO ao enviar e-mail: %s", e)
        # Não salva o estado como "alertado" se o envio falhou, para tentar
        # de novo na próxima execução em vez de perder o alerta.
