import asyncio
import smtplib
from email.message import EmailMessage
from app.core.config import settings


async def send_approved_email(payload, message_id):
    config = settings()
    if not config.smtp_host:
        raise RuntimeError('SMTP_HOST is not configured; approved email has not been sent')
    if not config.smtp_sandbox and not config.smtp_starttls:
        raise RuntimeError('Production SMTP requires STARTTLS')
    message = EmailMessage()
    message['From'] = config.smtp_from_email
    message['To'] = payload['recipient']
    message['Subject'] = payload['subject']
    message['Message-ID'] = message_id
    message.set_content(payload['body'])

    def send():
        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=20) as smtp:
            if config.smtp_starttls:
                smtp.starttls()
            if config.smtp_username:
                smtp.login(config.smtp_username, config.smtp_password)
            refused = smtp.send_message(message)
            if refused:
                raise RuntimeError('SMTP refused recipient')
    await asyncio.to_thread(send)
    return 'sandbox_accepted' if config.smtp_sandbox else 'smtp_accepted'
