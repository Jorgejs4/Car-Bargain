"""Envío de alertas por email (Fase 10).

Usa SMTP estándar (Gmail, Outlook, Resend…). Si `settings.smtp_host` no está
configurado, `send_deal_email` no hace nada y devuelve `False` (las
notificaciones siguen funcionando vía web).
"""

import logging
import smtplib
from email.message import EmailMessage
from html import escape

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_html(notification_title: str, body: dict) -> str:
    brand = body.get("brand") or ""
    model = body.get("model") or ""
    year = body.get("year")
    country = body.get("country") or ""
    price = body.get("price")
    margin = body.get("absolute_margin")
    cross = body.get("cross_border_margin")
    total = body.get("total_cost_es")
    url = body.get("url")

    rows = []
    if brand or model:
        rows.append(f"<tr><td><b>Vehículo</b></td><td>{escape(str(brand))} {escape(str(model))}".strip() + "</td></tr>")
    if year:
        rows.append(f"<tr><td><b>Año</b></td><td>{escape(str(year))}</td></tr>")
    if country:
        rows.append(f"<tr><td><b>País</b></td><td>{escape(str(country))}</td></tr>")
    if price is not None:
        rows.append(f"<tr><td><b>Precio</b></td><td>{price:,.2f} €</td></tr>")
    if margin is not None:
        color = "#16a34a" if margin > 0 else "#dc2626"
        rows.append(f"<tr><td><b>Margen estimado</b></td><td style='color:{color}'>{margin:+,.2f} €</td></tr>")
    if cross is not None:
        color = "#16a34a" if cross > 0 else "#dc2626"
        rows.append(f"<tr><td><b>Margen cross-border</b></td><td style='color:{color}'>{cross:+,.2f} €</td></tr>")
    if total is not None:
        rows.append(f"<tr><td><b>Coste total en España</b></td><td>{total:,.2f} €</td></tr>")

    table = "".join(rows) if rows else "<tr><td>Sin detalles.</td></tr>"
    link = f'<p><a href="{escape(str(url), quote=True)}" style="color:#2563eb">Ver anuncio</a></p>' if url else ""

    return f"""<html><body style="font-family:Arial,Helvetica,sans-serif;color:#111827;background:#f3f4f6;padding:24px">
<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:8px;overflow:hidden;border:1px solid #e5e7eb">
 <div style="background:#1f2937;color:#ffffff;padding:16px 24px"><h2 style="margin:0;font-size:18px">Nueva ganga: {escape(notification_title)}</h2></div>
<div style="padding:24px">
<p style="margin-top:0">Se ha detectado un anuncio que cumple tus criterios:</p>
<table cellspacing="0" cellpadding="6" style="font-size:14px">{table}</table>
{link}
<p style="color:#6b7280;font-size:12px">Recibes este email porque tienes activadas las alertas por correo en Car Bargains.</p>
</div></div></body></html>"""


def send_deal_email(notification_title: str, body: dict) -> bool:
    """Envía la notificación de una ganga al destinatario configurado.

    Devuelve True si se envió; False si no hay SMTP configurado o falla.
    """
    host = settings.smtp_host
    to = settings.alert_email_to
    if not host or not to:
        return False

    msg = EmailMessage()
    msg["Subject"] = f"[Car Bargains] Ganga: {notification_title}"
    msg["From"] = settings.smtp_from or settings.smtp_user or "alertas@carbargains.local"
    msg["To"] = to
    msg.set_content(_build_html(notification_title, body), subtype="html")

    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(host, settings.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(host, settings.smtp_port, timeout=15)
            if settings.smtp_use_tls:
                server.starttls()
        try:
            if settings.smtp_user and settings.smtp_password:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        finally:
            server.quit()
        logger.info("Email de alerta enviado a %s: %s", to, notification_title)
        return True
    except Exception:
        logger.exception("Fallo al enviar email de alerta a %s", to)
        return False
