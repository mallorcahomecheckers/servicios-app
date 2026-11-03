#!/usr/bin/env python3
"""
Aviso diario de horario sin cargar - Mallorca Home Checkers

Se ejecuta de lunes a sábado a las 21:00 (hora de Mallorca). Envía un mail
con las personas de Control horario que no han cargado entrada o salida hoy.
No cuenta festivos, vacaciones ni días libres. Si todo está cargado, no envía nada.
"""

import os
import json
import smtplib
from datetime import datetime
from zoneinfo import ZoneInfo
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import firebase_admin
from firebase_admin import credentials, db

TZ = ZoneInfo("Europe/Madrid")
DB_URL = "https://mhc-app-184e9-default-rtdb.europe-west1.firebasedatabase.app"
SENDER = "mallorcahomecheckers@gmail.com"
RECEIVER = "mallorcahomecheckers@gmail.com"
APP_URL = "https://mallorcahomecheckers.github.io/servicios-app/operarios.html"

# GitHub Actions trabaja en UTC: el workflow se programa a las 19:00 y a las 20:00 UTC
# y aquí se descarta la ejecución que no cae a las 21:00 de Mallorca (horario de verano/invierno).
SCHEDULE_WINTER = "0 20 * * 1-6"  # UTC+1
SCHEDULE_SUMMER = "0 19 * * 1-6"  # UTC+2


def debe_ejecutarse(now):
    sched = (os.environ.get("TRIGGER_SCHEDULE") or "").strip()
    if not sched:  # ejecución manual
        return True
    offset_h = int(now.utcoffset().total_seconds() // 3600)
    esperado = SCHEDULE_SUMMER if offset_h == 2 else SCHEDULE_WINTER
    return sched == esperado


def como_lista(v):
    if not v:
        return []
    if isinstance(v, dict):
        return list(v.values())
    return list(v)


def es_festivo(festivos, fecha):
    if not festivos:
        return False
    if isinstance(festivos, dict):
        return fecha in festivos
    return fecha in como_lista(festivos)


def faltantes(data, fecha):
    persons = [p for p in como_lista(data.get("persons")) if p]
    if es_festivo(data.get("festivos"), fecha):
        return persons, []
    records = data.get("records") or {}
    vacations = data.get("vacations") or {}
    libres = data.get("libres") or {}
    falta = []
    for p in persons:
        if fecha in como_lista(vacations.get(p)) or fecha in como_lista(libres.get(p)):
            continue
        r = (records.get(p) or {}).get(fecha) or {}
        if not r.get("ingreso") and not r.get("salida"):
            falta.append((p, "sin entrada ni salida"))
        elif not r.get("ingreso"):
            falta.append((p, f"falta la entrada (salida {r.get('salida')})"))
        elif not r.get("salida"):
            falta.append((p, f"falta la salida (entrada {r.get('ingreso')})"))
    return persons, falta


def enviar(falta, fecha_txt):
    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        raise RuntimeError("GMAIL_APP_PASSWORD no está configurado")
    filas = "".join(
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb'><b>{p}</b></td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;color:#b4531b'>{motivo}</td></tr>"
        for p, motivo in falta
    )
    html = f"""<div style="font-family:Arial,sans-serif;color:#16201d;max-width:560px">
      <h2 style="margin:0 0 6px">Horario sin cargar</h2>
      <p style="margin:0 0 16px;color:#5b6b66">{fecha_txt}</p>
      <table style="border-collapse:collapse;width:100%">{filas}</table>
      <p style="margin-top:18px;font-size:13px;color:#5b6b66">Los operarios pueden cargarlo desde
      <a href="{APP_URL}">la app de operarios</a> (hoy o ayer). No se cuentan festivos, vacaciones ni días libres.</p>
    </div>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"⏰ Horario sin cargar – {fecha_txt} ({len(falta)})"
    msg["From"] = SENDER
    msg["To"] = RECEIVER
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SENDER, password)
        s.sendmail(SENDER, RECEIVER, msg.as_string())


def main():
    now = datetime.now(TZ)
    if not debe_ejecutarse(now):
        print("Ejecución descartada: no son las 21:00 en Mallorca con este horario.")
        return
    if now.weekday() == 6:
        print("Domingo: no se revisa.")
        return

    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT no está configurado")
    firebase_admin.initialize_app(credentials.Certificate(json.loads(sa)), {"databaseURL": DB_URL})

    fecha = now.strftime("%Y-%m-%d")
    data = db.reference("horario2026").get() or {}
    persons, falta = faltantes(data, fecha)
    print(f"{fecha}: {len(persons)} personas, {len(falta)} sin cargar")
    if not falta:
        return
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    fecha_txt = f"{dias[now.weekday()].capitalize()} {now.strftime('%d/%m/%Y')}"
    enviar(falta, fecha_txt)
    print("✅ Aviso enviado")


if __name__ == "__main__":
    main()
