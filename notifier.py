"""Notificações por e-mail (Resend free tier ou SMTP)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

from config import skyscanner_link
from models import FlightOffer

logger = logging.getLogger(__name__)


def _format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "N/D"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h{mins:02d}"


def build_email_body(
    offer: FlightOffer,
    *,
    reason: str,
    reference_price: float,
    target_price: float,
    sources_summary: str,
) -> tuple[str, str, str]:
    subject = (
        f"✈️ Alerta SAO→PAR: R$ {offer.price_brl:,.0f} "
        f"({offer.departure_date}) — {offer.airline}"
    )
    gf = offer.link
    sky = skyscanner_link(offer.departure_date)

    text = f"""Alerta de passagem — São Paulo → França (só ida)

Motivo: {reason}
Preço encontrado: R$ {offer.price_brl:,.2f}
Referência de mercado: R$ {reference_price:,.2f}
Preço-alvo (~{((reference_price - target_price) / reference_price * 100) if reference_price else 35:.0f}% abaixo da ref.): R$ {target_price:,.2f}

Voo:
  Data ida: {offer.departure_date}
  Companhia: {offer.airline}
  Nº voo: {offer.flight_number or 'N/D'}
  Duração: {_format_duration(offer.duration_min)}
  Escalas: {offer.stops}
  Origem/Destino: {offer.origin_airport or 'SAO'} → {offer.destination_airport or 'PAR'}
  Fonte: {offer.source}

Links:
  Google Flights / principal: {gf}
  Skyscanner: {sky}

Resumo das fontes nesta execução:
{sources_summary}

---
Monitor automático flightsearch (GitHub Actions).
Regra anti-spam: só envia se preço < alvo ou quebra do último alerta.
"""

    html = f"""
<html><body style="font-family: sans-serif; line-height: 1.5;">
<h2>✈️ Alerta SAO → PAR (só ida)</h2>
<p><strong>Motivo:</strong> {reason}</p>
<table cellpadding="6" style="border-collapse: collapse;">
  <tr><td>Preço</td><td><strong style="font-size:1.3em;">R$ {offer.price_brl:,.2f}</strong></td></tr>
  <tr><td>Referência mercado</td><td>R$ {reference_price:,.2f}</td></tr>
  <tr><td>Preço-alvo</td><td>R$ {target_price:,.2f}</td></tr>
  <tr><td>Data</td><td>{offer.departure_date}</td></tr>
  <tr><td>Companhia</td><td>{offer.airline}</td></tr>
  <tr><td>Duração</td><td>{_format_duration(offer.duration_min)}</td></tr>
  <tr><td>Escalas</td><td>{offer.stops}</td></tr>
  <tr><td>Fonte</td><td>{offer.source}</td></tr>
</table>
<p>
  <a href="{gf}">Abrir no Google Flights</a> ·
  <a href="{sky}">Abrir no Skyscanner</a>
</p>
<pre style="background:#f4f4f4;padding:12px;font-size:12px;">{sources_summary}</pre>
</body></html>
"""
    return subject, text, html  # type: ignore[return-value]


def _send_resend(subject: str, text: str, html: str, to_email: str) -> None:
    api_key = os.environ["RESEND_API_KEY"]
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "text": text,
            "html": html,
        },
        timeout=30,
    )
    if not resp.ok:
        logger.error("Resend HTTP %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _send_smtp(subject: str, text: str, html: str, to_email: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    from_email = os.getenv("EMAIL_FROM", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_email, [to_email], msg.as_string())


def send_status_email(
    offer: FlightOffer,
    *,
    reference_price: float,
    target_price: float,
    sources_summary: str,
    alert_pending_reason: str,
) -> bool:
    """E-mail informativo (não é alerta de preço) — útil para validar Resend/SMTP."""
    to_email = os.getenv("ALERT_EMAIL")
    if not to_email:
        logger.error("ALERT_EMAIL não configurado.")
        return False

    subject = (
        f"[flightsearch] Monitor ativo — menor preço R$ {offer.price_brl:,.0f} "
        f"(alvo R$ {target_price:,.0f})"
    )
    text = f"""Monitor flightsearch — status da varredura

Menor preço agora: R$ {offer.price_brl:,.2f}
Referência de mercado: R$ {reference_price:,.2f}
Preço-alvo para alerta: R$ {target_price:,.2f}

Melhor oferta:
  {offer.departure_date} | {offer.airline} | {offer.stops} escala(s) | {offer.source}

Por que não alertou:
  {alert_pending_reason}

Fontes:
{sources_summary}

---
Este é um e-mail de status/teste. Alertas reais só quando o preço cruzar o alvo.
"""
    html = f"<html><body><pre>{text}</pre></body></html>"

    try:
        if os.getenv("RESEND_API_KEY"):
            _send_resend(subject, text, html, to_email)
        elif os.getenv("SMTP_HOST"):
            _send_smtp(subject, text, html, to_email)
        else:
            logger.error("Configure RESEND_API_KEY ou SMTP_HOST para enviar e-mail.")
            return False
        logger.info("E-mail de status enviado para %s", to_email)
        return True
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail de status: %s", exc)
        return False


def send_alert_email(
    offer: FlightOffer,
    *,
    reason: str,
    reference_price: float,
    target_price: float,
    sources_summary: str,
) -> bool:
    to_email = os.getenv("ALERT_EMAIL")
    if not to_email:
        logger.error("ALERT_EMAIL não configurado.")
        return False

    subject, text, html = build_email_body(
        offer,
        reason=reason,
        reference_price=reference_price,
        target_price=target_price,
        sources_summary=sources_summary,
    )

    try:
        if os.getenv("RESEND_API_KEY"):
            _send_resend(subject, text, html, to_email)
        elif os.getenv("SMTP_HOST"):
            _send_smtp(subject, text, html, to_email)
        else:
            logger.error("Configure RESEND_API_KEY ou SMTP_HOST para enviar e-mail.")
            return False
        logger.info("E-mail enviado para %s", to_email)
        return True
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail: %s", exc)
        return False
