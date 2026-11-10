"""Sends email over SMTP (Gmail app password, Brevo, Mailgun... any provider). Without SMTP settings it only logs."""
import logging
import smtplib
from email.message import EmailMessage

from .config import settings

log = logging.getLogger("dealradar.mailer")


def send_email(to: str, subject: str, body: str) -> bool:
    """True only if the message was really handed to the mail server."""
    if not (settings.smtp_host and settings.mail_from):
        log.info("[mail not configured] would send to %s: %s", to, subject)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
    msg.set_content(body)
    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, 465, timeout=20)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
            server.starttls()
        with server:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        return True
    except Exception as e:
        log.warning("email to %s failed: %s", to, e)
        return False
