"""Notificações por e-mail com alertas amarelo (watch) e verde (emissão)."""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum

import requests

from config import PREFERRED_DEPARTURE_DATES, TARGET_DISCOUNT_PCT, YELLOW_DISCOUNT_PCT
from links import resolve_links
from models import FlightOffer

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"


@dataclass(frozen=True)
class AlertTheme:
    level: AlertLevel
    label: str
    emoji: str
    header_bg: str
    header_text: str
    accent: str
    badge_bg: str
    badge_text: str
    border: str


THEMES = {
    AlertLevel.GREEN: AlertTheme(
        level=AlertLevel.GREEN,
        label="Emissão recomendada",
        emoji="🟢",
        header_bg="#0f766e",
        header_text="#ecfdf5",
        accent="#14b8a6",
        badge_bg="#d1fae5",
        badge_text="#065f46",
        border="#99f6e4",
    ),
    AlertLevel.YELLOW: AlertTheme(
        level=AlertLevel.YELLOW,
        label="Oportunidade em observação",
        emoji="🟡",
        header_bg="#b45309",
        header_text="#fffbeb",
        accent="#f59e0b",
        badge_bg="#fef3c7",
        badge_text="#92400e",
        border="#fde68a",
    ),
}


def _format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "—"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h{mins:02d}"


def _format_date_br(iso_date: str) -> str:
    try:
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
    except ValueError:
        return iso_date


def _format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    visible = local[:2] if len(local) > 2 else "*"
    return f"{visible}***@{domain}"


def _ideal_badge(departure_date: str) -> str:
    if departure_date in PREFERRED_DEPARTURE_DATES:
        return "★ Data ideal"
    return ""


def _offer_card_html(offer: FlightOffer, rank: int, theme: AlertTheme) -> str:
    ideal = _ideal_badge(offer.departure_date)
    ideal_html = (
        f'<span style="display:inline-block;margin-left:8px;padding:2px 8px;'
        f'background:{theme.badge_bg};color:{theme.badge_text};'
        f'font-size:11px;font-weight:600;border-radius:999px;">{ideal}</span>'
        if ideal
        else ""
    )
    route = f"{offer.origin_airport or 'SAO'} → {offer.destination_airport or 'PAR'}"
    urls = resolve_links(offer)
    gf = urls["google_flights"]
    sky = urls["skyscanner"]
    avia = urls.get("aviasales", "")
    stops = "Direto" if offer.stops == 0 else f"{offer.stops} escala(s)"
    avia_btn = (
        f'<a href="{avia}" style="display:inline-block;margin-right:8px;padding:10px 16px;'
        f'background:#1e293b;color:#ffffff;text-decoration:none;font-size:13px;'
        f'font-weight:600;border-radius:8px;">Aviasales</a>'
        if avia
        else ""
    )

    return f"""
    <tr>
      <td style="padding:0 0 16px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
               style="border:1px solid {theme.border};border-radius:12px;overflow:hidden;background:#ffffff;">
          <tr>
            <td style="padding:16px 20px;background:#f8fafc;border-bottom:1px solid #e2e8f0;">
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                <tr>
                  <td style="font-size:13px;color:#64748b;font-weight:600;">#{rank}</td>
                  <td align="right" style="font-size:24px;font-weight:700;color:#0f172a;">
                    {_format_brl(offer.price_brl)}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 20px;">
              <div style="font-size:18px;font-weight:700;color:#0f172a;margin-bottom:4px;">
                {_format_date_br(offer.departure_date)}{ideal_html}
              </div>
              <div style="font-size:15px;color:#334155;margin-bottom:12px;">
                {offer.airline}
                {f" · voo {offer.flight_number}" if offer.flight_number else ""}
              </div>
              <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
                     style="font-size:13px;color:#475569;">
                <tr>
                  <td width="33%" style="padding:8px 0;">Rota<br><strong style="color:#0f172a;">{route}</strong></td>
                  <td width="33%" style="padding:8px 0;">Duração<br><strong style="color:#0f172a;">{_format_duration(offer.duration_min)}</strong></td>
                  <td width="33%" style="padding:8px 0;">Paradas<br><strong style="color:#0f172a;">{stops}</strong></td>
                </tr>
              </table>
              <div style="margin-top:14px;font-size:12px;color:#94a3b8;">
                Fonte: {offer.source}
              </div>
              <div style="margin-top:16px;">
                {avia_btn}
                <a href="{gf}" style="display:inline-block;margin-right:8px;padding:10px 16px;
                   background:{theme.accent};color:#ffffff;text-decoration:none;font-size:13px;
                   font-weight:600;border-radius:8px;">Google Flights</a>
                <a href="{sky}" style="display:inline-block;padding:10px 16px;background:#e2e8f0;
                   color:#0f172a;text-decoration:none;font-size:13px;font-weight:600;border-radius:8px;">
                   Skyscanner
                </a>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    """


def build_tiered_email(
    level: AlertLevel,
    offers: list[FlightOffer],
    *,
    reason: str,
    reference_price: float,
    green_target: float,
    yellow_target: float,
) -> tuple[str, str, str]:
    theme = THEMES[level]
    best = offers[0]
    subject = (
        f"{theme.emoji} {theme.label} — SAO→PAR a partir de "
        f"{_format_brl(best.price_brl)} ({_format_date_br(best.departure_date)})"
    )

    cards_text = []
    for i, offer in enumerate(offers, 1):
        ideal = " [DATA IDEAL]" if offer.departure_date in PREFERRED_DEPARTURE_DATES else ""
        cards_text.append(
            f"{i}. {_format_brl(offer.price_brl)} — {_format_date_br(offer.departure_date)}{ideal}\n"
            f"   {offer.airline} | {offer.origin_airport or 'SAO'}→{offer.destination_airport or 'PAR'} | "
            f"{_format_duration(offer.duration_min)} | {offer.stops} esc.\n"
            f"   Google Flights: {resolve_links(offer)['google_flights']}"
        )

    text = f"""{theme.emoji} {theme.label.upper()} — São Paulo → França (só ida)

{reason}

Referência de mercado: {_format_brl(reference_price)}
Alvo verde (-{TARGET_DISCOUNT_PCT:.0f}%): {_format_brl(green_target)}
Faixa amarela (-{YELLOW_DISCOUNT_PCT:.0f}%): abaixo de {_format_brl(yellow_target)}
Datas ideais: 24/07 e 25/07/2026

Top {len(offers)} opções agora:
{chr(10).join(cards_text)}

---
flightsearch · monitor automático
"""

    cards_html = "".join(_offer_card_html(o, i, theme) for i, o in enumerate(offers, 1))
    ideal_note = "Priorizamos voos em <strong>24/07</strong> e <strong>25/07</strong> quando o preço é equivalente."

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:#f1f5f9;padding:24px 12px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="max-width:600px;width:100%;">
        <tr>
          <td style="background:{theme.header_bg};color:{theme.header_text};padding:28px 32px;border-radius:16px 16px 0 0;">
            <div style="font-size:13px;font-weight:600;letter-spacing:0.06em;text-transform:uppercase;opacity:0.9;">
              flightsearch · SAO → PAR
            </div>
            <div style="font-size:28px;font-weight:800;margin-top:8px;line-height:1.2;">
              {theme.emoji} {theme.label}
            </div>
            <div style="font-size:15px;margin-top:10px;line-height:1.5;opacity:0.95;">{reason}</div>
          </td>
        </tr>
        <tr>
          <td style="background:#ffffff;padding:24px 32px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
            <table width="100%" cellpadding="0" cellspacing="0" role="presentation"
                   style="background:#f8fafc;border-radius:10px;margin-bottom:20px;">
              <tr>
                <td style="padding:16px 18px;font-size:13px;color:#475569;">
                  <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                    <tr>
                      <td width="50%" style="padding:4px 0;">Referência<br><strong style="color:#0f172a;font-size:16px;">{_format_brl(reference_price)}</strong></td>
                      <td width="50%" style="padding:4px 0;">Alvo verde<br><strong style="color:#065f46;font-size:16px;">{_format_brl(green_target)}</strong></td>
                    </tr>
                    <tr>
                      <td colspan="2" style="padding:10px 0 0 0;border-top:1px solid #e2e8f0;">
                        Faixa amarela: abaixo de <strong style="color:#92400e;">{_format_brl(yellow_target)}</strong>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <div style="font-size:14px;color:#64748b;margin-bottom:16px;">{ideal_note}</div>
            <div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:12px;">
              Top {len(offers)} opções agora
            </div>
            <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
              {cards_html}
            </table>
          </td>
        </tr>
        <tr>
          <td style="background:#ffffff;padding:0 32px 28px;border-radius:0 0 16px 16px;
                     border:1px solid #e2e8f0;border-top:none;">
            <div style="font-size:12px;color:#94a3b8;line-height:1.6;text-align:center;">
              Alerta automático · reembolso CAPES: prefira tarifa oficial via Google Flights ou cia. aérea.<br>
              Datas monitoradas: 23 a 27/07/2026 · prioridade 24 e 25/07.
            </div>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return subject, text, html


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


def _dispatch_email(subject: str, text: str, html: str) -> bool:
    to_email = os.getenv("ALERT_EMAIL")
    if not to_email:
        logger.error("ALERT_EMAIL não configurado.")
        return False
    try:
        if os.getenv("RESEND_API_KEY"):
            _send_resend(subject, text, html, to_email)
        elif os.getenv("SMTP_HOST"):
            _send_smtp(subject, text, html, to_email)
        else:
            logger.error("Configure RESEND_API_KEY ou SMTP_HOST para enviar e-mail.")
            return False
        logger.info("E-mail enviado para %s", _mask_email(to_email))
        return True
    except Exception as exc:
        logger.exception("Falha ao enviar e-mail: %s", exc)
        return False


def send_tiered_alert(
    level: AlertLevel,
    offers: list[FlightOffer],
    *,
    reason: str,
    reference_price: float,
    green_target: float,
    yellow_target: float,
) -> bool:
    if not offers:
        return False
    subject, text, html = build_tiered_email(
        level,
        offers,
        reason=reason,
        reference_price=reference_price,
        green_target=green_target,
        yellow_target=yellow_target,
    )
    return _dispatch_email(subject, text, html)


def send_status_email(
    offers: list[FlightOffer],
    *,
    reference_price: float,
    green_target: float,
    yellow_target: float,
    alert_pending_reason: str,
) -> bool:
    """E-mail de teste/status com o mesmo layout, nível amarelo."""
    reason = f"Teste de entrega — {alert_pending_reason}"
    return send_tiered_alert(
        AlertLevel.YELLOW,
        offers,
        reason=reason,
        reference_price=reference_price,
        green_target=green_target,
        yellow_target=yellow_target,
    )
