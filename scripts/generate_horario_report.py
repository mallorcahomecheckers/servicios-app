#!/usr/bin/env python3
"""
Reporte semanal de horarios — Mallorca Home Checkers
Se ejecuta cada lunes via GitHub Actions y envía un email con el
resumen de horas trabajadas y saldo de la semana anterior.
"""

import os
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, date

import firebase_admin
from firebase_admin import credentials, db

# ── Configuración ─────────────────────────────────────────────────────────────
EMAIL_FROM     = "info@mallorcahomecheckers.com"
SMTP_PASSWORD  = os.environ.get("GMAIL_APP_PASSWORD", "")
EMAIL_TO       = "info@mallorcahomecheckers.com"
SMTP_SERVER    = "smtpout.secureserver.net"
SMTP_PORT      = 465
FIREBASE_DB    = "https://mhc-app-184e9-default-rtdb.europe-west1.firebasedatabase.app"

COLORS = ["#2563eb", "#db2777", "#16a34a", "#d97706", "#7c3aed", "#0891b2", "#dc2626", "#65a30d"]
DAYS_ES = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MONTHS_ES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# ── Firebase init ─────────────────────────────────────────────────────────────
def init_firebase():
    sa = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
    cred = credentials.Certificate(sa)
    firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB})

# ── Helpers de tiempo ─────────────────────────────────────────────────────────
def parse_time(s):
    if not s:
        return None
    try:
        h, m = map(int, s.split(":"))
        return h * 60 + m
    except:
        return None

def calc_hours(ingreso, salida):
    a, b = parse_time(ingreso), parse_time(salida)
    if a is None or b is None:
        return None
    diff = b - a
    if diff < 0:
        diff += 1440
    return diff / 60

def fmt_hours(h, signed=False):
    if h is None:
        return "—"
    neg = h < 0
    ah = abs(h)
    s = f"{int(ah)}h {round((ah % 1) * 60):02d}m"
    if signed:
        return ("−" if neg else "+") + s
    return s

def get_week_range():
    """Devuelve (lunes_pasado, domingo_pasado) como strings YYYY-MM-DD"""
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday, last_sunday

def dates_in_range(start, end):
    """Lista de dates entre start y end inclusive"""
    days = []
    cur = start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days

# ── Cálculo de datos ──────────────────────────────────────────────────────────
def compute_report(state, week_start, week_end):
    persons   = state.get("persons", [])
    records   = state.get("records", {})
    targets   = state.get("targets", {})
    vacations = state.get("vacations", {})
    libres    = state.get("libres", {})
    festivos  = state.get("festivos", {})

    week_dates = dates_in_range(week_start, week_end)
    week_strs  = [d.isoformat() for d in week_dates]

    report = []
    for person in persons:
        p_records   = records.get(person, {})
        p_vacations = vacations.get(person, [])
        p_libres    = libres.get(person, [])
        target_week = targets.get(person)  # horas/semana acordadas

        # horas trabajadas esta semana
        worked = 0.0
        day_details = []
        for d in week_dates:
            fecha = d.isoformat()
            rec   = p_records.get(fecha, {})
            h     = calc_hours(rec.get("ingreso"), rec.get("salida"))
            is_vac   = fecha in p_vacations
            is_libre = fecha in p_libres
            is_fest  = fecha in festivos

            day_details.append({
                "fecha":   fecha,
                "date":    d,
                "weekday": d.weekday(),
                "ingreso": rec.get("ingreso", ""),
                "salida":  rec.get("salida", ""),
                "nota":    rec.get("nota", ""),
                "hours":   h,
                "vac":     is_vac,
                "libre":   is_libre,
                "festivo": is_fest,
                "festivo_name": festivos.get(fecha, ""),
            })
            if h:
                worked += h

        # objetivo efectivo (descontando vacaciones y libres)
        if target_week:
            off_days = sum(1 for d in day_details if d["vac"] or d["libre"])
            h_per_day = target_week / 7
            effective_target = max(0, (7 - off_days) * h_per_day)
        else:
            effective_target = None

        balance = (worked - effective_target) if effective_target is not None else None

        report.append({
            "person":           person,
            "days":             day_details,
            "worked":           worked,
            "target":           target_week,
            "effective_target": effective_target,
            "balance":          balance,
        })

    return report

# ── HTML del email ────────────────────────────────────────────────────────────
def build_html(report, week_start, week_end):
    week_label = f"{week_start.day} {MONTHS_ES[week_start.month]} – {week_end.day} {MONTHS_ES[week_end.month]} {week_end.year}"

    # Cabecera
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Reporte Horario Semanal</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;">
<div style="max-width:680px;margin:0 auto;padding:24px 16px;">

  <!-- Header -->
  <div style="background:#1e293b;border-radius:16px 16px 0 0;padding:24px 28px;">
    <div style="font-size:22px;font-weight:800;color:#fff;">📋 Reporte Semanal de Horarios</div>
    <div style="font-size:14px;color:#94a3b8;margin-top:4px;">Mallorca Home Checkers · {week_label}</div>
  </div>

  <!-- Resumen global -->
  <div style="background:#fff;padding:20px 28px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;">
    <div style="display:flex;gap:16px;flex-wrap:wrap;">
"""

    for i, r in enumerate(report):
        color = COLORS[i % len(COLORS)]
        bal   = r["balance"]
        bal_color = "#16a34a" if (bal is not None and bal >= 0) else ("#ef4444" if bal is not None else "#94a3b8")
        bal_bg    = "#f0fdf4" if (bal is not None and bal >= 0) else ("#fef2f2" if bal is not None else "#f8fafc")

        html += f"""
      <div style="flex:1;min-width:180px;background:#f8fafc;border:1.5px solid #e2e8f0;border-radius:12px;padding:14px 16px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px;">
          <div style="width:36px;height:36px;border-radius:50%;background:{color};color:#fff;font-weight:800;font-size:13px;display:flex;align-items:center;justify-content:center;">{"".join(w[0].upper() for w in r["person"].split())[:2]}</div>
          <div>
            <div style="font-weight:700;font-size:15px;color:#0f172a;">{r["person"]}</div>
            <div style="font-size:11px;color:#64748b;">{f"{r['target']}h/sem acordadas" if r['target'] else "Sin objetivo"}</div>
          </div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
          <span style="font-size:12px;color:#64748b;">Trabajadas</span>
          <span style="font-size:15px;font-weight:800;color:#0f172a;">{fmt_hours(r["worked"])}</span>
        </div>
        {"" if r["effective_target"] is None else f'''
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <span style="font-size:12px;color:#64748b;">Objetivo</span>
          <span style="font-size:13px;font-weight:600;color:#64748b;">{fmt_hours(r["effective_target"])}</span>
        </div>
        <div style="background:#e2e8f0;border-radius:4px;height:6px;overflow:hidden;margin-bottom:8px;">
          <div style="background:{color};height:100%;width:{min(100, round(r["worked"]/r["effective_target"]*100) if r["effective_target"] > 0 else 100)}%;border-radius:4px;"></div>
        </div>
        <div style="text-align:center;background:{bal_bg};border-radius:8px;padding:4px 0;">
          <span style="font-size:13px;font-weight:800;color:{bal_color};">Saldo: {fmt_hours(bal, signed=True)}</span>
        </div>
        '''}
      </div>
"""

    html += """
    </div>
  </div>

  <!-- Calendario semanal -->
"""

    for i, r in enumerate(report):
        color = COLORS[i % len(COLORS)]
        color_light = color + "18"

        html += f"""
  <div style="background:#fff;margin-top:2px;border-left:1px solid #e2e8f0;border-right:1px solid #e2e8f0;padding:20px 28px;">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
      <div style="width:10px;height:10px;border-radius:50%;background:{color};"></div>
      <div style="font-weight:700;font-size:16px;color:#0f172a;">{r["person"]}</div>
      {f'<span style="font-size:12px;color:#64748b;margin-left:auto;">{r["target"]}h/sem acordadas</span>' if r["target"] else ""}
    </div>

    <!-- Grid calendario -->
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:separate;border-spacing:4px;">
      <tr>
"""
        # Cabecera días
        for day_name in DAYS_ES:
            html += f'        <td style="text-align:center;font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;padding-bottom:4px;">{day_name}</td>\n'

        html += "      </tr>\n      <tr>\n"

        for day in r["days"]:
            d        = day["date"]
            is_we    = d.weekday() >= 5
            has_rec  = bool(day["ingreso"] and day["salida"])
            is_vac   = day["vac"]
            is_libre = day["libre"]
            is_fest  = day["festivo"]

            # Colores de celda
            if is_vac:
                cell_bg     = "#e0f2fe"
                cell_border = "#7dd3fc"
                cell_color  = "#0369a1"
            elif is_libre:
                cell_bg     = "#faf5ff"
                cell_border = "#c4b5fd"
                cell_color  = "#7c3aed"
            elif is_fest:
                cell_bg     = "#fffbeb"
                cell_border = "#fcd34d"
                cell_color  = "#b45309"
            elif has_rec:
                cell_bg     = color_light
                cell_border = color
                cell_color  = "#0f172a"
            elif is_we:
                cell_bg     = "#f9fafb"
                cell_border = "#f1f5f9"
                cell_color  = "#9ca3af"
            else:
                cell_bg     = "#f8fafc"
                cell_border = "#e2e8f0"
                cell_color  = "#64748b"

            # Contenido celda
            if is_vac:
                status_line = '<div style="font-size:10px;color:#0369a1;">🏖 Vac.</div>'
            elif is_libre:
                status_line = '<div style="font-size:10px;color:#7c3aed;">🌴 Libre</div>'
            elif is_fest:
                status_line = f'<div style="font-size:9px;color:#b45309;">🎉</div>'
            elif has_rec:
                h = day["hours"]
                status_line = f'<div style="font-size:9px;color:{color};font-weight:700;">{fmt_hours(h)}</div>'
                status_line += f'<div style="font-size:8px;color:#64748b;">{day["ingreso"]}→{day["salida"]}</div>'
            else:
                status_line = '<div style="font-size:10px;color:#cbd5e1;">—</div>'

            nota_icon = "💬 " if day["nota"] else ""

            html += f"""        <td style="text-align:center;vertical-align:top;padding:3px;">
          <div style="background:{cell_bg};border:1.5px solid {cell_border};border-radius:8px;padding:6px 3px;min-height:64px;">
            <div style="font-size:16px;font-weight:800;color:{cell_color};">{d.day}</div>
            {status_line}
            {f'<div style="font-size:9px;">{nota_icon}</div>' if nota_icon else ""}
          </div>
        </td>
"""

        html += "      </tr>\n    </table>\n"

        # Detalle de registros de la semana
        detail_rows = [d for d in r["days"] if d["ingreso"] and d["salida"]]
        if detail_rows:
            html += '    <div style="margin-top:12px;border-top:1px solid #f1f5f9;padding-top:10px;">\n'
            for day in detail_rows:
                h = day["hours"]
                html += f"""      <div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px;">
        <span style="color:#64748b;min-width:32px;">{DAYS_ES[day["weekday"]]} {day["date"].day}</span>
        <span style="color:#374151;">{day["ingreso"]} → {day["salida"]}</span>
        <span style="font-weight:700;color:{color};">{fmt_hours(h)}</span>
        {f'<span style="color:#94a3b8;">· {day["nota"]}</span>' if day["nota"] else ""}
      </div>
"""
            html += "    </div>\n"

        html += "  </div>\n"

    # Footer
    html += f"""
  <!-- Footer -->
  <div style="background:#1e293b;border-radius:0 0 16px 16px;padding:16px 28px;text-align:center;">
    <div style="font-size:12px;color:#64748b;">📋 Mallorca Home Checkers · Reporte generado automáticamente cada lunes</div>
  </div>

</div>
</body>
</html>"""

    return html

# ── Envío de email ────────────────────────────────────────────────────────────
def send_email(subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(EMAIL_FROM, SMTP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Iniciando reporte de horarios...")
    init_firebase()

    week_start, week_end = get_week_range()
    print(f"Semana: {week_start} → {week_end}")

    state = db.reference("horario2026").get() or {}
    report = compute_report(state, week_start, week_end)

    html    = build_html(report, week_start, week_end)
    subject = f"📋 Horarios semana {week_start.day}/{week_start.month} – {week_end.day}/{week_end.month} · Mallorca Home Checkers"

    send_email(subject, html)
    print("✅ Reporte enviado correctamente.")

if __name__ == "__main__":
    main()
