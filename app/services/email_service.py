from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import smtplib
import logging
from email.utils import parseaddr

logger = logging.getLogger(__name__)

def send_alert_email(alert_id: int, reason: str, hr_email: str | None = None):
    """Envía un correo de alerta crítica al área de Recursos Humanos."""
    hr_email = (hr_email or os.getenv("SMTP_ALERT_RECIPIENT", "rh@plurione.com")).strip()
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
    if parseaddr(sender_email)[1] != sender_email or parseaddr(hr_email)[1] != hr_email:
        logger.error("No se envió la alerta %s: dirección de correo inválida.", alert_id)
        return False

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = hr_email
    msg['Subject'] = f"ALERTA CRÍTICA DE CLIMA LABORAL: Incidencia #{alert_id}"

    body =f"""
    Equipo de Capital Humano,
    
    El Sistema de Análisis de Sentimiento ha detectado una bandera roja de atención prioritaria.
    
    ID de Alerta: {alert_id}
    Motivo detectado por la IA: {reason}
    
    Por favor, ingresen al Dashboard para revisar y gestionar esta incidencia.
    
    Atentamente,
    Motor de IA - PluriOne S.A. de C.V.
    """
    msg.attach(MIMEText(body, 'plain'))

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
