import smtplib
from email.message import EmailMessage

from app.core.config import settings


class EmailService:
    def send_email(self, *, to_email: str, subject: str, body: str) -> None:
        if not settings.smtp_host:
            print(f"[email skipped] to={to_email} subject={subject}")
            return

        message = EmailMessage()
        message["From"] = settings.smtp_from_email
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
                if settings.smtp_use_tls:
                    smtp.starttls()
                if settings.smtp_username and settings.smtp_password:
                    smtp.login(settings.smtp_username, settings.smtp_password)
                smtp.send_message(message)
        except Exception as exc:
            print(f"[email failed] to={to_email} subject={subject} error={exc}")
