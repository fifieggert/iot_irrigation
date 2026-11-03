"""Envio de e-mails de alerta via SMTP (R15).

Projetado para nao quebrar a aplicacao quando o SMTP nao esta configurado:
nesse caso apenas registra em log e segue. O envio roda em um executor para
nao bloquear o event loop / a thread do MQTT.
"""

import logging
import smtplib
from email.message import EmailMessage
from datetime import datetime

from config import settings

log = logging.getLogger("notifier")


def _smtp_configurado() -> bool:
    return bool(settings.SMTP_HOST and settings.ALERT_EMAIL_TO)


def _montar_email(assunto: str, corpo: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER or "no-reply@irrigacao-iot"
    msg["To"] = settings.ALERT_EMAIL_TO
    msg.set_content(corpo)
    return msg


def enviar_email(assunto: str, corpo: str) -> bool:
    """Envio sincrono (bloqueante). Use enviar_email_async fora disso."""
    if not _smtp_configurado():
        log.info("SMTP nao configurado; e-mail de alerta nao enviado: %s", assunto)
        return False

    msg = _montar_email(assunto, corpo)
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_TLS:
                smtp.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.send_message(msg)
        log.info("E-mail de alerta enviado: %s", assunto)
        return True
    except Exception:
        log.exception("Falha ao enviar e-mail de alerta: %s", assunto)
        return False


async def enviar_email_async(assunto: str, corpo: str) -> bool:
    """Roda o envio bloqueante em um executor para nao travar o event loop."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, enviar_email, assunto, corpo)


def alerta_falta_sol(dias: int, media: float, limiar: int) -> str:
    """Template do alerta de falta de sol (R15)."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"Alerta de falta de luz solar - {agora}\n\n"
        f"A planta ficou {dias} dia(s) consecutivo(s) com luminosidade media "
        f"abaixo do limiar configurado.\n"
        f"Luminosidade media recente: {media:.1f}% (limiar: {limiar}%).\n\n"
        f"Recomendacao: reposicione o vaso para um local com maior incidencia "
        f"de luz solar nas proximas horas."
    )


def alerta_generico(tipo: str, mensagem: str) -> str:
    """Template para alertas vindos do dispositivo (solo seco, seguranca...)."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return (
        f"Alerta do sistema de irrigacao - {agora}\n\n"
        f"Tipo: {tipo}\n"
        f"Mensagem: {mensagem}\n"
    )
