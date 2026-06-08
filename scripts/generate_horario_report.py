#!/usr/bin/env python3
"""
Reporte Semanal de Horarios - Mallorca Home Checkers
Lógica: horas_acordadas_semana vs horas_registradas → pendiente o extra
"""

import os
import json
import smtplib
import math
from datetime import datetime, date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import firebase_admin
from firebase_admin import credentials, db

# ── Firebase ──────────────────────────────────────────────────────────────────
def init_firebase():
    sa = os.environ.get("FIREBASE_SERVICE_ACCOUNT")
    if not sa:
        raise RuntimeError("FIREBASE_SERVICE_ACCOUNT no está configurado")
    cred = credentials.Certificate(json.loads(sa))
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://mhc-app-184e9-default-rtdb.europe-west1.firebasedatabase.app"
    })

# ── Calendario (mismo que index.html) ────────────────────────────────────────
CALENDAR_DATA = [
  {"fecha":"2025-12-29","semana":1,"dia":"lunes","casa":"12"},{"fecha":"2025-12-30","semana":1,"dia":"martes","casa":"12"},{"fecha":"2025-12-31","semana":1,"dia":"miércoles","casa":"12"},
  {"fecha":"2026-01-01","semana":1,"dia":"jueves","casa":"1"},{"fecha":"2026-01-02","semana":1,"dia":"viernes","casa":"1"},{"fecha":"2026-01-03","semana":1,"dia":"sábado","casa":"1"},{"fecha":"2026-01-04","semana":1,"dia":"domingo","casa":"1"},
  {"fecha":"2026-01-05","semana":2,"dia":"lunes","casa":"1"},{"fecha":"2026-01-06","semana":2,"dia":"martes","casa":"1"},{"fecha":"2026-01-07","semana":2,"dia":"miércoles","casa":"1"},{"fecha":"2026-01-08","semana":2,"dia":"jueves","casa":"1"},{"fecha":"2026-01-09","semana":2,"dia":"viernes","casa":"1"},{"fecha":"2026-01-10","semana":2,"dia":"sábado","casa":"1"},{"fecha":"2026-01-11","semana":2,"dia":"domingo","casa":"1"},
  {"fecha":"2026-01-12","semana":3,"dia":"lunes","casa":"1"},{"fecha":"2026-01-13","semana":3,"dia":"martes","casa":"1"},{"fecha":"2026-01-14","semana":3,"dia":"miércoles","casa":"1"},{"fecha":"2026-01-15","semana":3,"dia":"jueves","casa":"1"},{"fecha":"2026-01-16","semana":3,"dia":"viernes","casa":"1"},{"fecha":"2026-01-17","semana":3,"dia":"sábado","casa":"1"},{"fecha":"2026-01-18","semana":3,"dia":"domingo","casa":"1"},
  {"fecha":"2026-01-19","semana":4,"dia":"lunes","casa":"1"},{"fecha":"2026-01-20","semana":4,"dia":"martes","casa":"1"},{"fecha":"2026-01-21","semana":4,"dia":"miércoles","casa":"1"},{"fecha":"2026-01-22","semana":4,"dia":"jueves","casa":"1"},{"fecha":"2026-01-23","semana":4,"dia":"viernes","casa":"1"},{"fecha":"2026-01-24","semana":4,"dia":"sábado","casa":"1"},{"fecha":"2026-01-25","semana":4,"dia":"domingo","casa":"1"},
  {"fecha":"2026-01-26","semana":5,"dia":"lunes","casa":"1"},{"fecha":"2026-01-27","semana":5,"dia":"martes","casa":"1"},{"fecha":"2026-01-28","semana":5,"dia":"miércoles","casa":"1"},{"fecha":"2026-01-29","semana":5,"dia":"jueves","casa":"1"},{"fecha":"2026-01-30","semana":5,"dia":"viernes","casa":"1"},{"fecha":"2026-01-31","semana":5,"dia":"sábado","casa":"1"},
  {"fecha":"2026-02-01","semana":5,"dia":"domingo","casa":"2"},{"fecha":"2026-02-02","semana":6,"dia":"lunes","casa":"2"},{"fecha":"2026-02-03","semana":6,"dia":"martes","casa":"2"},{"fecha":"2026-02-04","semana":6,"dia":"miércoles","casa":"2"},{"fecha":"2026-02-05","semana":6,"dia":"jueves","casa":"2"},{"fecha":"2026-02-06","semana":6,"dia":"viernes","casa":"2"},{"fecha":"2026-02-07","semana":6,"dia":"sábado","casa":"2"},{"fecha":"2026-02-08","semana":6,"dia":"domingo","casa":"2"},
  {"fecha":"2026-02-09","semana":7,"dia":"lunes","casa":"2"},{"fecha":"2026-02-10","semana":7,"dia":"martes","casa":"2"},{"fecha":"2026-02-11","semana":7,"dia":"miércoles","casa":"2"},{"fecha":"2026-02-12","semana":7,"dia":"jueves","casa":"2"},{"fecha":"2026-02-13","semana":7,"dia":"viernes","casa":"2"},{"fecha":"2026-02-14","semana":7,"dia":"sábado","casa":"2"},{"fecha":"2026-02-15","semana":7,"dia":"domingo","casa":"2"},
  {"fecha":"2026-02-16","semana":8,"dia":"lunes","casa":"2"},{"fecha":"2026-02-17","semana":8,"dia":"martes","casa":"2"},{"fecha":"2026-02-18","semana":8,"dia":"miércoles","casa":"2"},{"fecha":"2026-02-19","semana":8,"dia":"jueves","casa":"2"},{"fecha":"2026-02-20","semana":8,"dia":"viernes","casa":"2"},{"fecha":"2026-02-21","semana":8,"dia":"sábado","casa":"2"},{"fecha":"2026-02-22","semana":8,"dia":"domingo","casa":"2"},
  {"fecha":"2026-02-23","semana":9,"dia":"lunes","casa":"2"},{"fecha":"2026-02-24","semana":9,"dia":"martes","casa":"2"},{"fecha":"2026-02-25","semana":9,"dia":"miércoles","casa":"2"},{"fecha":"2026-02-26","semana":9,"dia":"jueves","casa":"2"},{"fecha":"2026-02-27","semana":9,"dia":"viernes","casa":"2"},{"fecha":"2026-02-28","semana":9,"dia":"sábado","casa":"2"},
  {"fecha":"2026-03-01","semana":9,"dia":"domingo","casa":"3"},{"fecha":"2026-03-02","semana":10,"dia":"lunes","casa":"3"},{"fecha":"2026-03-03","semana":10,"dia":"martes","casa":"3"},{"fecha":"2026-03-04","semana":10,"dia":"miércoles","casa":"3"},{"fecha":"2026-03-05","semana":10,"dia":"jueves","casa":"3"},{"fecha":"2026-03-06","semana":10,"dia":"viernes","casa":"3"},{"fecha":"2026-03-07","semana":10,"dia":"sábado","casa":"3"},{"fecha":"2026-03-08","semana":10,"dia":"domingo","casa":"3"},
  {"fecha":"2026-03-09","semana":11,"dia":"lunes","casa":"3"},{"fecha":"2026-03-10","semana":11,"dia":"martes","casa":"3"},{"fecha":"2026-03-11","semana":11,"dia":"miércoles","casa":"3"},{"fecha":"2026-03-12","semana":11,"dia":"jueves","casa":"3"},{"fecha":"2026-03-13","semana":11,"dia":"viernes","casa":"3"},{"fecha":"2026-03-14","semana":11,"dia":"sábado","casa":"3"},{"fecha":"2026-03-15","semana":11,"dia":"domingo","casa":"3"},
  {"fecha":"2026-03-16","semana":12,"dia":"lunes","casa":"3"},{"fecha":"2026-03-17","semana":12,"dia":"martes","casa":"3"},{"fecha":"2026-03-18","semana":12,"dia":"miércoles","casa":"3"},{"fecha":"2026-03-19","semana":12,"dia":"jueves","casa":"3"},{"fecha":"2026-03-20","semana":12,"dia":"viernes","casa":"3"},{"fecha":"2026-03-21","semana":12,"dia":"sábado","casa":"3"},{"fecha":"2026-03-22","semana":12,"dia":"domingo","casa":"3"},
  {"fecha":"2026-03-23","semana":13,"dia":"lunes","casa":"3"},{"fecha":"2026-03-24","semana":13,"dia":"martes","casa":"3"},{"fecha":"2026-03-25","semana":13,"dia":"miércoles","casa":"3"},{"fecha":"2026-03-26","semana":13,"dia":"jueves","casa":"3"},{"fecha":"2026-03-27","semana":13,"dia":"viernes","casa":"3"},{"fecha":"2026-03-28","semana":13,"dia":"sábado","casa":"3"},{"fecha":"2026-03-29","semana":13,"dia":"domingo","casa":"3"},{"fecha":"2026-03-30","semana":13,"dia":"lunes","casa":"3"},{"fecha":"2026-03-31","semana":13,"dia":"martes","casa":"3"},
  {"fecha":"2026-04-01","semana":14,"dia":"miércoles","casa":"4"},{"fecha":"2026-04-02","semana":14,"dia":"jueves","casa":"4"},{"fecha":"2026-04-03","semana":14,"dia":"viernes","casa":"4"},{"fecha":"2026-04-04","semana":14,"dia":"sábado","casa":"4"},{"fecha":"2026-04-05","semana":14,"dia":"domingo","casa":"4"},
  {"fecha":"2026-04-06","semana":15,"dia":"lunes","casa":"4"},{"fecha":"2026-04-07","semana":15,"dia":"martes","casa":"4"},{"fecha":"2026-04-08","semana":15,"dia":"miércoles","casa":"4"},{"fecha":"2026-04-09","semana":15,"dia":"jueves","casa":"4"},{"fecha":"2026-04-10","semana":15,"dia":"viernes","casa":"4"},{"fecha":"2026-04-11","semana":15,"dia":"sábado","casa":"4"},{"fecha":"2026-04-12","semana":15,"dia":"domingo","casa":"4"},
  {"fecha":"2026-04-13","semana":16,"dia":"lunes","casa":"4"},{"fecha":"2026-04-14","semana":16,"dia":"martes","casa":"4"},{"fecha":"2026-04-15","semana":16,"dia":"miércoles","casa":"4"},{"fecha":"2026-04-16","semana":16,"dia":"jueves","casa":"4"},{"fecha":"2026-04-17","semana":16,"dia":"viernes","casa":"4"},{"fecha":"2026-04-18","semana":16,"dia":"sábado","casa":"4"},{"fecha":"2026-04-19","semana":16,"dia":"domingo","casa":"4"},
  {"fecha":"2026-04-20","semana":17,"dia":"lunes","casa":"4"},{"fecha":"2026-04-21","semana":17,"dia":"martes","casa":"4"},{"fecha":"2026-04-22","semana":17,"dia":"miércoles","casa":"4"},{"fecha":"2026-04-23","semana":17,"dia":"jueves","casa":"4"},{"fecha":"2026-04-24","semana":17,"dia":"viernes","casa":"4"},{"fecha":"2026-04-25","semana":17,"dia":"sábado","casa":"4"},{"fecha":"2026-04-26","semana":17,"dia":"domingo","casa":"4"},
  {"fecha":"2026-04-27","semana":18,"dia":"lunes","casa":"4"},{"fecha":"2026-04-28","semana":18,"dia":"martes","casa":"4"},{"fecha":"2026-04-29","semana":18,"dia":"miércoles","casa":"4"},{"fecha":"2026-04-30","semana":18,"dia":"jueves","casa":"4"},
  {"fecha":"2026-05-01","semana":18,"dia":"viernes","casa":"5"},{"fecha":"2026-05-02","semana":18,"dia":"sábado","casa":"5"},{"fecha":"2026-05-03","semana":18,"dia":"domingo","casa":"5"},
  {"fecha":"2026-05-04","semana":19,"dia":"lunes","casa":"5"},{"fecha":"2026-05-05","semana":19,"dia":"martes","casa":"5"},{"fecha":"2026-05-06","semana":19,"dia":"miércoles","casa":"5"},{"fecha":"2026-05-07","semana":19,"dia":"jueves","casa":"5"},{"fecha":"2026-05-08","semana":19,"dia":"viernes","casa":"5"},{"fecha":"2026-05-09","semana":19,"dia":"sábado","casa":"5"},{"fecha":"2026-05-10","semana":19,"dia":"domingo","casa":"5"},
  {"fecha":"2026-05-11","semana":20,"dia":"lunes","casa":"5"},{"fecha":"2026-05-12","semana":20,"dia":"martes","casa":"5"},{"fecha":"2026-05-13","semana":20,"dia":"miércoles","casa":"5"},{"fecha":"2026-05-14","semana":20,"dia":"jueves","casa":"5"},{"fecha":"2026-05-15","semana":20,"dia":"viernes","casa":"5"},{"fecha":"2026-05-16","semana":20,"dia":"sábado","casa":"5"},{"fecha":"2026-05-17","semana":20,"dia":"domingo","casa":"5"},
  {"fecha":"2026-05-18","semana":21,"dia":"lunes","casa":"5"},{"fecha":"2026-05-19","semana":21,"dia":"martes","casa":"5"},{"fecha":"2026-05-20","semana":21,"dia":"miércoles","casa":"5"},{"fecha":"2026-05-21","semana":21,"dia":"jueves","casa":"5"},{"fecha":"2026-05-22","semana":21,"dia":"viernes","casa":"5"},{"fecha":"2026-05-23","semana":21,"dia":"sábado","casa":"5"},{"fecha":"2026-05-24","semana":21,"dia":"domingo","casa":"5"},
  {"fecha":"2026-05-25","semana":22,"dia":"lunes","casa":"5"},{"fecha":"2026-05-26","semana":22,"dia":"martes","casa":"5"},{"fecha":"2026-05-27","semana":22,"dia":"miércoles","casa":"5"},{"fecha":"2026-05-28","semana":22,"dia":"jueves","casa":"5"},{"fecha":"2026-05-29","semana":22,"dia":"viernes","casa":"5"},{"fecha":"2026-05-30","semana":22,"dia":"sábado","casa":"5"},{"fecha":"2026-05-31","semana":22,"dia":"domingo","casa":"5"},
  {"fecha":"2026-06-01","semana":23,"dia":"lunes","casa":"6"},{"fecha":"2026-06-02","semana":23,"dia":"martes","casa":"6"},{"fecha":"2026-06-03","semana":23,"dia":"miércoles","casa":"6"},{"fecha":"2026-06-04","semana":23,"dia":"jueves","casa":"6"},{"fecha":"2026-06-05","semana":23,"dia":"viernes","casa":"6"},{"fecha":"2026-06-06","semana":23,"dia":"sábado","casa":"6"},{"fecha":"2026-06-07","semana":23,"dia":"domingo","casa":"6"},
  {"fecha":"2026-06-08","semana":24,"dia":"lunes","casa":"6"},{"fecha":"2026-06-09","semana":24,"dia":"martes","casa":"6"},{"fecha":"2026-06-10","semana":24,"dia":"miércoles","casa":"6"},{"fecha":"2026-06-11","semana":24,"dia":"jueves","casa":"6"},{"fecha":"2026-06-12","semana":24,"dia":"viernes","casa":"6"},{"fecha":"2026-06-13","semana":24,"dia":"sábado","casa":"6"},{"fecha":"2026-06-14","semana":24,"dia":"domingo","casa":"6"},
  {"fecha":"2026-06-15","semana":25,"dia":"lunes","casa":"6"},{"fecha":"2026-06-16","semana":25,"dia":"martes","casa":"6"},{"fecha":"2026-06-17","semana":25,"dia":"miércoles","casa":"6"},{"fecha":"2026-06-18","semana":25,"dia":"jueves","casa":"6"},{"fecha":"2026-06-19","semana":25,"dia":"viernes","casa":"6"},{"fecha":"2026-06-20","semana":25,"dia":"sábado","casa":"6"},{"fecha":"2026-06-21","semana":25,"dia":"domingo","casa":"6"},
  {"fecha":"2026-06-22","semana":26,"dia":"lunes","casa":"6"},{"fecha":"2026-06-23","semana":26,"dia":"martes","casa":"6"},{"fecha":"2026-06-24","semana":26,"dia":"miércoles","casa":"6"},{"fecha":"2026-06-25","semana":26,"dia":"jueves","casa":"6"},{"fecha":"2026-06-26","semana":26,"dia":"viernes","casa":"6"},{"fecha":"2026-06-27","semana":26,"dia":"sábado","casa":"6"},{"fecha":"2026-06-28","semana":26,"dia":"domingo","casa":"6"},
  {"fecha":"2026-06-29","semana":27,"dia":"lunes","casa":"6"},{"fecha":"2026-06-30","semana":27,"dia":"martes","casa":"6"},
  {"fecha":"2026-07-01","semana":27,"dia":"miércoles","casa":"7"},{"fecha":"2026-07-02","semana":27,"dia":"jueves","casa":"7"},{"fecha":"2026-07-03","semana":27,"dia":"viernes","casa":"7"},{"fecha":"2026-07-04","semana":27,"dia":"sábado","casa":"7"},{"fecha":"2026-07-05","semana":27,"dia":"domingo","casa":"7"},
  {"fecha":"2026-07-06","semana":28,"dia":"lunes","casa":"7"},{"fecha":"2026-07-07","semana":28,"dia":"martes","casa":"7"},{"fecha":"2026-07-08","semana":28,"dia":"miércoles","casa":"7"},{"fecha":"2026-07-09","semana":28,"dia":"jueves","casa":"7"},{"fecha":"2026-07-10","semana":28,"dia":"viernes","casa":"7"},{"fecha":"2026-07-11","semana":28,"dia":"sábado","casa":"7"},{"fecha":"2026-07-12","semana":28,"dia":"domingo","casa":"7"},
  {"fecha":"2026-07-27","semana":31,"dia":"lunes","casa":"7"},{"fecha":"2026-07-28","semana":31,"dia":"martes","casa":"7"},{"fecha":"2026-07-29","semana":31,"dia":"miércoles","casa":"7"},{"fecha":"2026-07-30","semana":31,"dia":"jueves","casa":"7"},{"fecha":"2026-07-31","semana":31,"dia":"viernes","casa":"7"},
  {"fecha":"2026-08-01","semana":31,"dia":"sábado","casa":"8"},{"fecha":"2026-08-02","semana":31,"dia":"domingo","casa":"8"},
  {"fecha":"2026-12-01","semana":49,"dia":"martes","casa":"12"},{"fecha":"2026-12-28","semana":53,"dia":"lunes","casa":"12"},{"fecha":"2026-12-29","semana":53,"dia":"martes","casa":"12"},{"fecha":"2026-12-30","semana":53,"dia":"miércoles","casa":"12"},{"fecha":"2026-12-31","semana":53,"dia":"jueves","casa":"12"},
]

MESES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
          7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

# ── Helpers de tiempo ─────────────────────────────────────────────────────────
def parse_time(s):
    """'HH:MM' → minutos desde medianoche, o None"""
    if not s:
        return None
    try:
        h, m = s.split(":")
        return int(h) * 60 + int(m)
    except Exception:
        return None

def calc_hours(entrada, salida):
    """Devuelve horas trabajadas (float) o None si falta dato."""
    a, b = parse_time(entrada), parse_time(salida)
    if a is None or b is None:
        return None
    diff = b - a
    if diff < 0:
        diff += 1440  # noche → día siguiente
    return diff / 60.0

def fmt_hours(h, signed=False):
    """
    Convierte horas (float) a '5h 10m'.
    signed=True → '+5h 10m' o '−5h 10m'
    """
    if h is None:
        return "—"
    neg = h < 0
    ah = abs(h)
    total_min = round(ah * 60)
    hh = total_min // 60
    mm = total_min % 60
    s = f"{hh}h {mm:02d}m"
    if signed:
        s = ("−" if neg else "+") + s
    return s

# ── Lógica de cálculo ─────────────────────────────────────────────────────────
def get_week_days(semana_num):
    return [d for d in CALENDAR_DATA if d["semana"] == semana_num]

def get_month_days(mes_num):
    return [d for d in CALENDAR_DATA if int(d["casa"]) == mes_num]

def is_off_day(person, fecha, vacations, libres):
    return fecha in (vacations.get(person) or []) or fecha in (libres.get(person) or [])

def week_worked(person, days, records):
    """Suma de horas trabajadas en una semana."""
    total = 0.0
    p_recs = records.get(person) or {}
    for d in days:
        r = p_recs.get(d["fecha"]) or {}
        h = calc_hours(r.get("ingreso"), r.get("salida"))
        if h is not None:
            total += h
    return total

def week_target(person, days, targets, vacations, libres):
    """
    Objetivo real de la semana = horas_contrato / 7 × días_activos_de_esa_semana
    (descontando vacaciones y libres).
    """
    t = targets.get(person)
    if not t:
        return None
    h_per_day = t / 7.0
    active = sum(1 for d in days if not is_off_day(person, d["fecha"], vacations, libres))
    return max(0.0, active * h_per_day)

def month_worked(person, mes_num, records):
    days = get_month_days(mes_num)
    total = 0.0
    p_recs = records.get(person) or {}
    for d in days:
        r = p_recs.get(d["fecha"]) or {}
        h = calc_hours(r.get("ingreso"), r.get("salida"))
        if h is not None:
            total += h
    return total

def month_target(person, mes_num, targets, vacations, libres):
    """Objetivo mensual: horas_contrato × semanas_en_mes (proporcional por días)."""
    t = targets.get(person)
    if not t:
        return None
    days = get_month_days(mes_num)
    h_per_day = t / 7.0
    active = sum(1 for d in days if not is_off_day(person, d["fecha"], vacations, libres))
    return max(0.0, active * h_per_day)

# ── Detección de semana y mes del reporte ────────────────────────────────────
def get_report_week():
    """
    El workflow corre el lunes. Reporta la semana que ACABA DE TERMINAR
    (lunes anterior → domingo).
    """
    today = date.today()
    # Lunes de esta semana
    monday = today - timedelta(days=today.weekday())
    # Domingo de la semana pasada
    last_sunday = monday - timedelta(days=1)
    last_monday = last_sunday - timedelta(days=6)

    week_start = last_monday.strftime("%Y-%m-%d")
    week_end   = last_sunday.strftime("%Y-%m-%d")

    # Encontrar número de semana en nuestro calendario
    matching = [d for d in CALENDAR_DATA
                if d["fecha"] >= week_start and d["fecha"] <= week_end]
    semana_num = matching[0]["semana"] if matching else None
    return semana_num, week_start, week_end, last_monday.month

# ── HTML del reporte ──────────────────────────────────────────────────────────
COLORS = {
    0: "#3b82f6",  # azul
    1: "#ec4899",  # rosa
    2: "#22c55e",  # verde
    3: "#f97316",  # naranja
    4: "#8b5cf6",  # violeta
}

def person_color(i):
    return COLORS.get(i % len(COLORS), "#64748b")

def balance_bar(done, target, color):
    """HTML de barra de progreso."""
    if target is None or target == 0:
        pct = 0
    else:
        pct = min(100, round(done / target * 100))
    return f"""
    <div style="height:6px;background:#e2e8f0;border-radius:4px;margin:6px 0;">
      <div style="width:{pct}%;height:100%;background:{color};border-radius:4px;transition:width 0.3s;"></div>
    </div>"""

def build_html(persons, targets, records, vacations, libres,
               semana_num, week_start, week_end, mes_num):

    week_days = get_week_days(semana_num) if semana_num else []
    mes_nombre = MESES.get(mes_num, "")

    # Formatear fechas legibles
    def fmt_date(s):
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
            return dt.strftime("%-d %b %Y")
        except Exception:
            return s

    # ── Tarjetas semanales ──
    cards_html = ""
    for i, person in enumerate(persons):
        color = person_color(i)
        ini = "".join(w[0].upper() for w in person.split())[:2]

        # === SEMANA ===
        w_done   = week_worked(person, week_days, records)
        w_target = week_target(person, week_days, targets, vacations, libres)
        w_contract = targets.get(person)  # horas acordadas en contrato

        # Diferencia real: registradas − acordadas (contrato completo)
        # Para la semana usamos el objetivo proporcional (descuenta días libres/vac)
        if w_target is not None:
            w_diff = w_done - w_target
        else:
            w_diff = None

        # === MES (hasta hoy, solo días ya transcurridos) ===
        m_done   = month_worked(person, mes_num, records)
        m_target = month_target(person, mes_num, targets, vacations, libres)
        if m_target is not None:
            m_diff = m_done - m_target
        else:
            m_diff = None

        # ── Semana: colores y textos ──
        if w_diff is None:
            w_badge_bg, w_badge_color, w_badge_border = "#f8fafc","#94a3b8","#e2e8f0"
            w_label = "Sin objetivo"
            w_diff_txt = "—"
        elif w_diff >= -0.01:
            # Horas extra o exacto
            w_badge_bg, w_badge_color, w_badge_border = "#f0fdf4","#16a34a","#86efac"
            w_label = "✅ Horas extra esta semana"
            w_diff_txt = fmt_hours(w_diff, signed=True)
        else:
            # Pendiente
            w_badge_bg, w_badge_color, w_badge_border = "#fef2f2","#dc2626","#fca5a5"
            w_label = f"⏳ Pendiente de trabajar esta semana"
            w_diff_txt = fmt_hours(abs(w_diff))  # sin signo → "le quedan Xh Ym"

        # ── Mes: colores y textos ──
        if m_diff is None:
            m_badge_bg, m_badge_color, m_badge_border = "#f8fafc","#94a3b8","#e2e8f0"
            m_label = "Sin objetivo mensual"
            m_diff_txt = "—"
        elif m_diff >= -0.01:
            m_badge_bg, m_badge_color, m_badge_border = "#f0fdf4","#16a34a","#86efac"
            m_label = "✅ Horas extra en el mes"
            m_diff_txt = fmt_hours(m_diff, signed=True)
        else:
            m_badge_bg, m_badge_color, m_badge_border = "#fef2f2","#dc2626","#fca5a5"
            m_label = "⏳ Pendiente de trabajar en el mes"
            m_diff_txt = fmt_hours(abs(m_diff))

        bar_week  = balance_bar(w_done, w_target, color) if w_target else ""
        bar_month = balance_bar(m_done, m_target, color) if m_target else ""

        cards_html += f"""
        <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:16px;padding:18px 20px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.05);">
          <!-- Cabecera persona -->
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
            <div style="width:44px;height:44px;border-radius:50%;background:{color};color:#fff;
                        display:flex;align-items:center;justify-content:center;
                        font-weight:800;font-size:15px;flex-shrink:0;">{ini}</div>
            <div>
              <div style="font-size:17px;font-weight:800;color:#0f172a;">{person}</div>
              <div style="font-size:12px;color:#94a3b8;">{w_contract or "—"}h/sem acordadas</div>
            </div>
          </div>

          <!-- Bloque semana -->
          <div style="background:#f8fafc;border-radius:12px;padding:14px 16px;margin-bottom:12px;">
            <div style="font-size:11px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">
              📅 Semana {semana_num} &nbsp;·&nbsp; {fmt_date(week_start)} – {fmt_date(week_end)}
            </div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;">
              <div>
                <div style="font-size:12px;color:#64748b;">Registradas</div>
                <div style="font-size:22px;font-weight:800;color:#0f172a;">{fmt_hours(w_done)}</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:12px;color:#64748b;">Objetivo semana</div>
                <div style="font-size:16px;font-weight:700;color:#64748b;">{fmt_hours(w_target)}</div>
              </div>
            </div>
            {bar_week}
            <!-- Badge resultado semana -->
            <div style="background:{w_badge_bg};border:1.5px solid {w_badge_border};border-radius:10px;
                        padding:10px 14px;margin-top:8px;display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:13px;color:{w_badge_color};font-weight:600;">{w_label}</span>
              <span style="font-size:18px;font-weight:800;color:{w_badge_color};">{w_diff_txt}</span>
            </div>
          </div>

          <!-- Bloque mes -->
          <div style="background:#f8fafc;border-radius:12px;padding:14px 16px;">
            <div style="font-size:11px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:10px;">
              🗓 Acumulado {mes_nombre}
            </div>
            <div style="display:flex;justify-content:space-between;align-items:flex-end;">
              <div>
                <div style="font-size:12px;color:#64748b;">Registradas</div>
                <div style="font-size:22px;font-weight:800;color:#0f172a;">{fmt_hours(m_done)}</div>
              </div>
              <div style="text-align:right;">
                <div style="font-size:12px;color:#64748b;">Objetivo mes</div>
                <div style="font-size:16px;font-weight:700;color:#64748b;">{fmt_hours(m_target)}</div>
              </div>
            </div>
            {bar_month}
            <!-- Badge resultado mes -->
            <div style="background:{m_badge_bg};border:1.5px solid {m_badge_border};border-radius:10px;
                        padding:10px 14px;margin-top:8px;display:flex;justify-content:space-between;align-items:center;">
              <span style="font-size:13px;color:{m_badge_color};font-weight:600;">{m_label}</span>
              <span style="font-size:18px;font-weight:800;color:{m_badge_color};">{m_diff_txt}</span>
            </div>
          </div>
        </div>"""

    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Reporte Semanal · Sem {semana_num}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:20px 12px 40px;">

    <!-- Header -->
    <div style="background:#1e293b;border-radius:16px;padding:22px 24px;margin-bottom:20px;color:#fff;">
      <div style="font-size:22px;font-weight:800;margin-bottom:4px;">📋 Reporte Semanal de Horarios</div>
      <div style="font-size:13px;color:#94a3b8;">Mallorca Home Checkers &nbsp;·&nbsp; Semana {semana_num}: {fmt_date(week_start)} – {fmt_date(week_end)}</div>
    </div>

    <!-- Leyenda -->
    <div style="background:#fff;border:1.5px solid #e5e7eb;border-radius:12px;padding:12px 16px;margin-bottom:20px;font-size:12px;color:#64748b;line-height:1.6;">
      <b style="color:#0f172a;">Cómo leer este reporte:</b><br>
      <span style="color:#dc2626;font-weight:700;">⏳ Pendiente</span> → horas que aún debe trabajar para cumplir su contrato.<br>
      <span style="color:#16a34a;font-weight:700;">✅ Horas extra</span> → ha trabajado más de lo acordado.<br>
      El <b>objetivo semana</b> descuenta vacaciones y días libres registrados.
    </div>

    {cards_html}

    <!-- Footer -->
    <div style="text-align:center;font-size:11px;color:#94a3b8;margin-top:8px;">
      Generado automáticamente · {generated_at}
    </div>
  </div>
</body>
</html>"""
    return html

# ── Envío de email ────────────────────────────────────────────────────────────
def send_email(html_body, semana_num, week_start, week_end):
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    if not gmail_pass:
        print("⚠️  GMAIL_APP_PASSWORD no configurado — imprimiendo HTML al stdout")
        print(html_body)
        return

    # Ajusta estos valores si cambias el remitente/destinatario
    sender   = "mallorcahomecheckers@gmail.com"
    receiver = "mallorcahomecheckers@gmail.com"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📋 Reporte Horarios · Semana {semana_num} ({week_start} → {week_end})"
    msg["From"]    = sender
    msg["To"]      = receiver
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(sender, gmail_pass)
        s.sendmail(sender, receiver, msg.as_string())

    print(f"✅ Reporte enviado: Semana {semana_num} ({week_start} → {week_end})")

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    init_firebase()

    # Leer todo de Firebase
    data      = db.reference("horario2026").get() or {}
    persons   = data.get("persons")   or ["Alejandra", "Nayara"]
    records   = data.get("records")   or {}
    targets   = data.get("targets")   or {}
    vacations = data.get("vacations") or {}
    libres    = data.get("libres")    or {}

    semana_num, week_start, week_end, mes_num = get_report_week()
    if not semana_num:
        print("⚠️  No se encontró semana para el rango de fechas. Abortando.")
        return

    html = build_html(
        persons, targets, records, vacations, libres,
        semana_num, week_start, week_end, mes_num
    )
    send_email(html, semana_num, week_start, week_end)

if __name__ == "__main__":
    main()
