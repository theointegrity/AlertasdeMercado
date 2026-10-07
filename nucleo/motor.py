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
import os
from pathlib import Path

import yaml

from conectores.dolar import DolarConector
from conectores.tesouro import TesouroConector
from nucleo.estado import GerenciadorEstado
from nucleo.email import bloco_metrica, corpo_email, corpo_saude, enviar_email
from nucleo.relogio import agora

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
DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def _configurar_log() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    # horário do log em Brasília (o servidor do GitHub roda em UTC)
    logging.Formatter.converter = lambda *_: agora().timetuple()
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
    if agora().hour < cfg.get("hora_corte", 0):
        return True
    return gerente.frequencia_diaria_ja_consultada_hoje(cfg["id"])


def _dentro_do_horario_comercial(horario: dict) -> bool:
    """Confere dia da semana e hora (Brasília) contra config/geral.yaml."""
    momento = agora()
    dias = horario.get("dias", DIAS_SEMANA[:5])
    return (
        DIAS_SEMANA[momento.weekday()] in dias
        and horario.get("inicio", 9) <= momento.hour < horario.get("fim", 18)
    )


def _idade_horas(leitura):
    """Há quantas horas a fonte gerou o dado (None se a fonte não informa)."""
    if leitura.data_hora is None:
        return None
    return (agora() - leitura.data_hora).total_seconds() / 3600


def _salvar(gerente: GerenciadorEstado, modo_teste: bool) -> None:
    if modo_teste:
        logging.info("Modo teste: estado NÃO salvo (o anti-spam da equipe não é afetado).")
        return
    gerente.salvar()


def executar() -> None:
    _configurar_log()
    geral = _carregar_yaml("geral.yaml") or {}
    email_admin = geral.get("email_administrador")
    limite_falhas = geral.get("falhas_seguidas_para_aviso", 3)

    # Execução manual com "ignorar horário" ligado (ver monitor.yml): roda a
    # qualquer hora, mas e-mail só para o administrador e sem salvar estado.
    modo_teste = os.environ.get("IGNORAR_HORARIO", "").lower() == "true"

    if modo_teste:
        logging.info("MODO TESTE (ignorar horário): e-mails só para %s.", email_admin)
    elif not _dentro_do_horario_comercial(geral.get("horario_comercial", {})):
        logging.info(
            "Fora do horário comercial (%s, %s) — nada consultado, nenhum e-mail "
            "enviado, estado não alterado.",
            DIAS_SEMANA[agora().weekday()], f"{agora():%d/%m/%Y %H:%M}",
        )
        return

    indicadores = _carregar_yaml("indicadores.yaml") or []
    if modo_teste:
        destinatarios = [email_admin]
    else:
        destinatarios_cfg = _carregar_yaml("destinatarios.yaml") or {}
        destinatarios = [e.strip() for e in destinatarios_cfg.get("destinatarios", []) if e and e.strip()]

    gerente = GerenciadorEstado(ESTADO_PATH)
    blocos = []
    rotulos_disparados = []
    problemas_saude = []

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
            falhas = gerente.registrar_saude_fonte(indicador_id, principal_ok=False)
            if falhas >= limite_falhas:
                problemas_saude.append(
                    f"<b>{cfg['rotulo']}</b>: {falhas} rodadas seguidas sem resposta "
                    f"de nenhuma fonte. Último erro: {e}"
                )
            continue

        principal_ok = leitura is None or not leitura.fonte_alternativa
        falhas = gerente.registrar_saude_fonte(indicador_id, principal_ok)
        if falhas >= limite_falhas:
            problemas_saude.append(
                f"<b>{cfg['rotulo']}</b>: fonte principal falhou em {falhas} rodadas "
                f"seguidas; usando a fonte alternativa ({leitura.fonte})."
            )

        if cfg.get("frequencia") == "diario":
            gerente.marcar_consulta_diaria(indicador_id)

        if leitura is None:
            logging.warning("%s | fonte respondeu, mas o dado não foi encontrado", indicador_id)
            continue

        disparou = _avaliar(leitura.valor, cfg["operador"], cfg["gatilho"])
        idade = _idade_horas(leitura)
        logging.info(
            "%s | %s | fonte: %s | dado: %s | gatilho %s %s | %s",
            indicador_id, leitura.valor_formatado, leitura.fonte,
            f"{leitura.data_hora:%d/%m %H:%M} ({idade:.1f}h atrás)" if idade is not None else "horário não informado",
            cfg["operador"], cfg["gatilho"],
            "DENTRO DO GATILHO" if disparou else "fora do gatilho",
        )

        # Dado velho demais não dispara alerta, e também não "gasta" o
        # anti-spam: o alerta sai na próxima rodada com dado atualizado.
        idade_maxima = cfg.get("idade_maxima_horas")
        if disparou and idade_maxima is not None and (idade is None or idade >= idade_maxima):
            logging.warning(
                "%s | dado defasado (limite %sh) — alerta NÃO disparado nesta rodada",
                indicador_id, idade_maxima,
            )
            continue

        if gerente.deve_alertar(indicador_id, disparou):
            logging.info("%s | ALERTA DISPARADO", indicador_id)
            gatilho_txt = f"{SIMBOLO_OPERADOR[cfg['operador']]} {cfg['gatilho']}"
            blocos.append(bloco_metrica(cfg["rotulo"], gatilho_txt, leitura))
            rotulos_disparados.append(cfg["rotulo"])

    if problemas_saude and not gerente.aviso_saude_ja_enviado_hoje():
        try:
            enviar_email("[SAÚDE DO SISTEMA] Fonte de dados falhando",
                         corpo_saude(problemas_saude), [email_admin])
            gerente.marcar_aviso_saude_enviado()
            logging.info("E-mail de saúde do sistema enviado para %s", email_admin)
        except Exception as e:
            logging.error("ERRO ao enviar e-mail de saúde do sistema: %s", e)

    if not blocos:
        logging.info("Nenhum novo alerta nesta rodada.")
        _salvar(gerente, modo_teste)
        return

    if len(blocos) > 1:
        assunto = f"[ALERTA DE MERCADO] {len(blocos)} indicadores atingiram os níveis monitorados"
    else:
        assunto = f"[ALERTA DE MERCADO] {rotulos_disparados[0]}"
    if modo_teste:
        assunto = "[TESTE] " + assunto

    try:
        enviar_email(assunto, corpo_email("".join(blocos)), destinatarios)
        logging.info("E-mail enviado para %s destinatário(s): %s", len(destinatarios), assunto)
        _salvar(gerente, modo_teste)
    except Exception as e:
        logging.error("ERRO ao enviar e-mail: %s", e)
        # Não salva o estado como "alertado" se o envio falhou, para tentar
        # de novo na próxima execução em vez de perder o alerta.
