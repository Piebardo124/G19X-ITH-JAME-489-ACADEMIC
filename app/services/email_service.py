from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import smtplib

def send_alert_email(alert_id: int, reason: str, hr_email: str = "rh@plurione.com"):
    """Envía un correo de alerta crítica al área de Recursos Humanos."""
    sender_email = os.getenv("SMTP_EMAIL", "CorreoRandom@gmail.com")
    sender_password = os.getenv("SMTP_PASSWORD", "contraseña_random")

    if sender_email == "CorreoRandom@gmail.com":
        print(f"Simulación: se enviaría la alerta {alert_id} a {hr_email}. Motivo: {reason}")
        return

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
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        text = msg.as_string()
        server.sendmail(sender_email, hr_email, text)
        server.quit()
        print(f"Se envió la alerta {alert_id} a {hr_email}.")
    except Exception as e:
        print(f"No se pudo enviar la alerta {alert_id}: {e}")
