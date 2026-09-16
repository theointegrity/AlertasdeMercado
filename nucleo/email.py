# -*- coding: utf-8 -*-
"""
Geração do template de e-mail (identidade visual Integrity) e envio via
SMTP. Credenciais vêm sempre de variáveis de ambiente — nunca do código.
"""
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

GOLD = "#B8A46C"
DARK = "#2B2B2B"
GREY = "#8A8A8A"
VERDE = "#2E7D32"
VERMELHO = "#C62828"
SERIF = "'Playfair Display', Georgia, 'Times New Roman', serif"
SANS = "Montserrat, 'Segoe UI', Arial, sans-serif"

EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASS = os.environ.get("EMAIL_PASS")
EMAIL_NOME_EXIBICAO = os.environ.get("EMAIL_NOME_EXIBICAO", "Alertas de Mercado | Integrity WM")


def fmt_variacao(valor, sufixo: str) -> str:
    if valor is None:
        return f"<span style='color:{GREY};'>&mdash;</span>"
    if valor > 0:
        cor, seta, sinal = VERDE, "&#9650;", "+"
    elif valor < 0:
        cor, seta, sinal = VERMELHO, "&#9660;", "\u2212"
    else:
        cor, seta, sinal = GREY, "", ""
    num = f"{abs(valor):.2f}".replace(".", ",")
    return f"<span style='color:{cor};'>{seta} {sinal}{num}{sufixo}</span>"


def bloco_metrica(rotulo: str, gatilho_txt: str, leitura) -> str:
    """Monta o bloco de destaque de um indicador (padrão visual Integrity)."""
    detalhes = []
    if leitura.variacao is not None:
        detalhes.append(("Variação", fmt_variacao(leitura.variacao, leitura.variacao_sufixo)))
    detalhes.append(("Gatilho configurado", gatilho_txt))
    detalhes.extend(leitura.detalhes)
    if leitura.fonte:
        detalhes.append(("Fonte", leitura.fonte))

    linhas = "".join(
        f"""<tr>
          <td style="font-family:{SANS};font-size:12px;color:{GREY};padding:3px 0;white-space:nowrap;">{k}</td>
          <td style="font-family:{SANS};font-size:12px;color:{DARK};padding:3px 0 3px 18px;text-align:right;">{v}</td>
        </tr>"""
        for k, v in detalhes
    )
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 28px 0;">
      <tr><td style="border-left:3px solid {GOLD};padding:2px 0 2px 20px;">
        <div style="font-family:{SANS};font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:{GREY};padding-bottom:6px;">{rotulo}</div>
        <div style="font-family:{SERIF};font-size:30px;font-weight:600;color:{DARK};line-height:1.15;letter-spacing:0.5px;padding-bottom:10px;">{leitura.valor_formatado}</div>
        <table role="presentation" cellpadding="0" cellspacing="0">{linhas}</table>
      </td></tr>
    </table>"""


def corpo_email(blocos_html: str) -> str:
    agora = datetime.now()
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
              "agosto", "setembro", "outubro", "novembro", "dezembro"]
    data_ext = f"{agora.day} de {meses[agora.month - 1]} de {agora.year} · {agora:%H:%M}"
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<!--[if !mso]><!--><link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600&family=Montserrat:wght@400;500;600&display=swap" rel="stylesheet"><!--<![endif]-->
</head>
<body style="margin:0;padding:0;background:#F4F2EE;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F4F2EE;">
<tr><td align="center" style="padding:36px 16px;">
  <table role="presentation" width="600" cellpadding="0" cellspacing="0"
         style="max-width:600px;width:100%;background:#FFFFFF;">
    <tr><td style="height:5px;background:{GOLD};font-size:0;line-height:0;">&nbsp;</td></tr>
    <tr><td align="center" style="padding:40px 48px 0 48px;">
      <div style="font-family:{SERIF};font-size:24px;letter-spacing:6px;color:{DARK};text-transform:uppercase;">Integrity</div>
      <div style="font-family:{SANS};font-size:10px;letter-spacing:3.5px;color:{GREY};text-transform:uppercase;padding-top:4px;">Wealth Management</div>
    </td></tr>
    <tr><td style="padding:26px 48px 0 48px;">
      <div style="height:1px;background:{GOLD};font-size:0;line-height:0;">&nbsp;</div>
    </td></tr>
    <tr><td align="center" style="padding:30px 48px 8px 48px;">
      <div style="font-family:{SERIF};font-size:20px;letter-spacing:3px;color:{GOLD};text-transform:uppercase;">Alerta de Mercado</div>
      <div style="font-family:{SANS};font-size:12px;color:{GREY};padding-top:8px;">{data_ext}</div>
    </td></tr>
    <tr><td style="padding:18px 48px 6px 48px;">
      <p style="font-family:{SANS};font-size:13px;line-height:1.7;color:{DARK};margin:0 0 26px 0;text-align:justify;">
        Os níveis de mercado monitorados atingiram os parâmetros definidos.
        Seguem os dados observados no momento da verificação:</p>
    </td></tr>
    <tr><td style="padding:0 48px;">{blocos_html}</td></tr>
    <tr><td style="padding:0 48px 34px 48px;">
      <div style="height:1px;background:#E5E1D8;font-size:0;line-height:0;margin-bottom:16px;">&nbsp;</div>
      <p style="font-family:{SANS};font-size:10.5px;line-height:1.6;color:{GREY};margin:0;">
        Mensagem automática do sistema de monitoramento de mercado da Integrity.</p>
    </td></tr>
    <tr><td align="center" style="background:{GOLD};padding:14px 48px;">
      <span style="font-family:{SANS};font-size:11px;letter-spacing:2px;color:#FFFFFF;text-transform:lowercase;">integritywm.com.br</span>
    </td></tr>
  </table>
</td></tr></table>
</body></html>"""


def enviar_email(assunto: str, corpo_html: str, destinatarios: list) -> None:
    if not EMAIL_USER or not EMAIL_PASS:
        raise RuntimeError("variáveis EMAIL_USER/EMAIL_PASS não definidas")
    if not destinatarios:
        raise RuntimeError("nenhum destinatário ativo em config/destinatarios.yaml")

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((EMAIL_NOME_EXIBICAO, EMAIL_USER))
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = assunto
    msg.attach(MIMEText(corpo_html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, destinatarios, msg.as_string())
