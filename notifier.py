"""Notificações por e-mail com alertas amarelo (watch) e verde (emissão)."""

from __future__ import annotations

import logging
import os
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from enum import Enum

import requests

from config import PREFERRED_DEPARTURE_DATES, TARGET_DISCOUNT_PCT, YELLOW_BAND_ABOVE_GREEN_PCT
from links import resolve_links
from models import FlightOffer
from times import format_schedule

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


def _alert_recipients() -> list[str]:
    """ALERT_EMAIL e ALERT_EMAIL_CC aceitam vários endereços separados por vírgula."""
    seen: set[str] = set()
    recipients: list[str] = []
    for var in ("ALERT_EMAIL", "ALERT_EMAIL_CC"):
        raw = os.getenv(var, "")
        for part in raw.replace(";", ",").split(","):
            email = part.strip().lower()
            if email and email not in seen:
                seen.add(email)
                recipients.append(email)
    return recipients


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
    schedule = format_schedule(
        offer.departure_date,
        offer.departure_time,
        offer.arrival_time,
        offer.arrival_date,
    )
    schedule_html = (
        f'<tr><td colspan="3" style="padding:8px 0 0 0;">Horário<br>'
        f'<strong style="color:#0f172a;">{schedule}</strong></td></tr>'
        if schedule
        else ""
    )
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
                {schedule_html}
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
    scan_min: float | None = None,
    reference_basis: str = "",
) -> tuple[str, str, str]:
    theme = THEMES[level]
    best = offers[0]
    stamp = datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC")
    uid = uuid.uuid4().hex[:8]
    subject = (
        f"{theme.emoji} [{stamp}] SAO→PAR só ida · "
        f"{_format_brl(best.price_brl)} · {_format_date_br(best.departure_date)} · #{uid}"
    )

    cards_text = []
    for i, offer in enumerate(offers, 1):
        ideal = " [DATA IDEAL]" if offer.departure_date in PREFERRED_DEPARTURE_DATES else ""
        schedule = format_schedule(
            offer.departure_date,
            offer.departure_time,
            offer.arrival_time,
            offer.arrival_date,
        )
        schedule_line = f"   Horário: {schedule}\n" if schedule else ""
        cards_text.append(
            f"{i}. {_format_brl(offer.price_brl)} — {_format_date_br(offer.departure_date)}{ideal}\n"
            f"   {offer.airline} | {offer.origin_airport or 'SAO'}→{offer.destination_airport or 'PAR'} | "
            f"{_format_duration(offer.duration_min)} | {offer.stops} esc.\n"
            f"{schedule_line}"
            f"   Google Flights: {resolve_links(offer)['google_flights']}\n"
            f"   Aviasales: {resolve_links(offer).get('aviasales', '—')}"
        )

    scan_line = (
        f"Melhor preço no scan: {_format_brl(scan_min)}\n" if scan_min is not None else ""
    )
    ref_detail = f" ({reference_basis})" if reference_basis else ""

    text = f"""{theme.emoji} {theme.label.upper()} — São Paulo → França (só ida)

{reason}

{scan_line}Referência CAPES: {_format_brl(reference_price)}{ref_detail}
Alvo verde (compra, -{TARGET_DISCOUNT_PCT:.0f}% da ref.): {_format_brl(green_target)}
Faixa amarela (observação): {_format_brl(green_target)} a {_format_brl(yellow_target)} (+{YELLOW_BAND_ABOVE_GREEN_PCT:.0f}% sobre verde)
Datas ideais: 24/07 e 25/07/2026

Top {len(offers)} opções agora:
{chr(10).join(cards_text)}

---
flightsearch · monitor automático
"""

    cards_html = "".join(_offer_card_html(o, i, theme) for i, o in enumerate(offers, 1))
    ideal_note = (
        "Priorizamos <strong>24/07</strong> e <strong>25/07</strong>, depois voos "
        "<strong>diretos</strong> ou com menos escalas."
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<!-- flightsearch-alert:{uid} -->
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
                      <td width="50%" style="padding:4px 0;">Referência CAPES<br><strong style="color:#0f172a;font-size:16px;">{_format_brl(reference_price)}</strong></td>
                      <td width="50%" style="padding:4px 0;">Alvo verde (compra)<br><strong style="color:#065f46;font-size:16px;">{_format_brl(green_target)}</strong></td>
                    </tr>
                    <tr>
                      <td colspan="2" style="padding:6px 0 0 0;font-size:12px;color:#64748b;">
                        {f"Scan atual: <strong>{_format_brl(scan_min)}</strong> · " if scan_min is not None else ""}
                        {reference_basis or "baseline conservador entre fontes"}
                      </td>
                    </tr>
                    <tr>
                      <td colspan="2" style="padding:10px 0 0 0;border-top:1px solid #e2e8f0;">
                        Faixa amarela: <strong style="color:#92400e;">{_format_brl(green_target)} – {_format_brl(yellow_target)}</strong>
                        <span style="color:#64748b;"> (+{YELLOW_BAND_ABOVE_GREEN_PCT:.0f}% sobre verde)</span>
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


def _send_resend(subject: str, text: str, html: str, to_emails: list[str]) -> None:
    api_key = os.environ["RESEND_API_KEY"]
    from_email = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
    ref_id = str(uuid.uuid4())
    resp = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": from_email,
            "to": to_emails,
            "subject": subject,
            "text": text,
            "html": html,
            "headers": {
                "X-Entity-Ref-ID": ref_id,
                "X-Flightsearch-Alert": ref_id,
            },
        },
        timeout=30,
    )
    if not resp.ok:
        logger.error("Resend HTTP %s: %s", resp.status_code, resp.text)
    resp.raise_for_status()


def _send_smtp(subject: str, text: str, html: str, to_emails: list[str]) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    from_email = os.getenv("EMAIL_FROM", user)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = ", ".join(to_emails)
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="flightsearch.local")
    msg["X-Entity-Ref-ID"] = str(uuid.uuid4())
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_email, to_emails, msg.as_string())


def _smtp_configured() -> bool:
    return bool(
        os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD")
    )


def _dispatch_email(subject: str, text: str, html: str) -> bool:
    recipients = _alert_recipients()
    if not recipients:
        logger.error("Nenhum destinatário — configure ALERT_EMAIL (e opcionalmente ALERT_EMAIL_CC).")
        return False
    try:
        resend_ready = bool(os.getenv("RESEND_API_KEY"))
        smtp_ready = _smtp_configured()
        # Resend em onboarding@resend.dev só entrega para o e-mail da conta — use SMTP com CC.
        if smtp_ready and (len(recipients) > 1 or not resend_ready):
            _send_smtp(subject, text, html, recipients)
        elif resend_ready:
            _send_resend(subject, text, html, recipients)
        elif smtp_ready:
            _send_smtp(subject, text, html, recipients)
        else:
            logger.error("Configure RESEND_API_KEY ou SMTP_HOST para enviar e-mail.")
            return False
        masked = ", ".join(_mask_email(email) for email in recipients)
        logger.info("E-mail enviado para %s", masked)
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
    scan_min: float | None = None,
    reference_basis: str = "",
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
        scan_min=scan_min,
        reference_basis=reference_basis,
    )
    return _dispatch_email(subject, text, html)


def send_status_email(
    offers: list[FlightOffer],
    *,
    reference_price: float,
    green_target: float,
    yellow_target: float,
    alert_pending_reason: str,
    scan_min: float | None = None,
    reference_basis: str = "",
    test_mode: bool = True,
) -> bool:
    """E-mail de pulso/status. Em modo teste, prefixo [TESTE] é adicionado."""
    reason = (
        f"[TESTE] Verificação de entrega — {alert_pending_reason}"
        if test_mode
        else alert_pending_reason
    )
    return send_tiered_alert(
        AlertLevel.YELLOW,
        offers,
        reason=reason,
        reference_price=reference_price,
        green_target=green_target,
        yellow_target=yellow_target,
        scan_min=scan_min,
        reference_basis=reference_basis,
    )
