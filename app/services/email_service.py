from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import smtplib
import logging
from email.utils import parseaddr

logger = logging.getLogger(__name__)

def send_alert_email(alert_id: int, reason: str, hr_email: str | None = None):
    """Envía a Recursos Humanos una notificación asociada a la alerta."""
    hr_email = (hr_email or os.getenv("SMTP_ALERT_RECIPIENT", "")).strip()
    sender_email = os.getenv("SMTP_EMAIL", "").strip()
    sender_password = os.getenv("SMTP_PASSWORD", "")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    try:
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        timeout = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))
    except ValueError:
        logger.error("Configuración SMTP inválida: SMTP_PORT y SMTP_TIMEOUT_SECONDS deben ser numéricos.")
        return False

    if not sender_email or not sender_password:
        logger.warning("No se envió la alerta %s: faltan las credenciales SMTP.", alert_id)
        return False
    if not hr_email:
        logger.error("No se envió la alerta %s: falta SMTP_ALERT_RECIPIENT.", alert_id)
        return False
    if parseaddr(sender_email)[1] != sender_email or parseaddr(hr_email)[1] != hr_email:
        logger.error("No se envió la alerta %s: dirección de correo inválida.", alert_id)
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = hr_email
    msg['Subject'] = f"PluriOne: requiere atención la alerta #{alert_id}"

    body = f"""Hola, equipo de Capital Humano:

El sistema registró una alerta que requiere revisión.

Alerta: #{alert_id}
Motivo: {reason}

Pueden consultar el detalle y actualizar su estado desde el panel de PluriOne.

Saludos,
Equipo PluriOne
"""
    # MIMEText usa ASCII por defecto; motivos de alerta en español pueden
    # incluir acentos y provocar UnicodeEncodeError al enviar por SMTP.
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        logger.info("Se envió la alerta %s por correo.", alert_id)
        return True
    except Exception as e:
        logger.error("No se pudo enviar la alerta %s (tipo=%s).", alert_id, type(e).__name__)
        return False
