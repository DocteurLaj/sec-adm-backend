import logging
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

LOGGER = logging.getLogger("sec_adm.email")


def send_email(to_email: str, subject: str, body: str) -> None:
    settings = get_settings()
    if not settings.smtp_host:
        LOGGER.info("Email dev mode to=%s subject=%s body=%s", to_email, subject, body)
        print(f"\n--- SEC EMAIL DEV ---\nTo: {to_email}\nSubject: {subject}\n{body}\n--- END EMAIL ---\n")
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    send_email(
        to_email,
        "Reinitialisation du mot de passe SEC",
        (
            "Vous avez demande la reinitialisation de votre mot de passe SEC.\n\n"
            f"Ouvrez ce lien pour choisir un nouveau mot de passe :\n{reset_url}\n\n"
            "Si vous n'etes pas a l'origine de cette demande, ignorez ce message."
        ),
    )


def send_email_verification(to_email: str, verification_url: str) -> None:
    send_email(
        to_email,
        "Verification de votre email SEC",
        (
            "Bienvenue sur SEC.\n\n"
            f"Confirmez votre adresse email avec ce lien :\n{verification_url}\n\n"
            "Si vous n'avez pas cree de compte SEC, ignorez ce message."
        ),
    )
