"""
generate_prefactura.py
Genera el PDF de prefactura por propiedad a partir de datos de Firebase Firestore.
Puede ejecutarse en modo 'semanal' (lunes a domingo anterior) o 'mensual' (mes anterior completo).
"""

import os
import sys
import json
import datetime
import smtplib
import locale
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

import firebase_admin
from firebase_admin import credentials, firestore

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.lib import colors

# ─────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────
EMAIL_FROM    = "info@mallorcahomecheckers.com"
EMAIL_TO      = "info@mallorcahomecheckers.com"
SMTP_SERVER   = "smtpout.secureserver.net"
SMTP_PORT     = 465
GMAIL_APP_PWD = os.environ.get("GMAIL_APP_PASSWORD", "")

# ─────────────────────────────────────────
# FIREBASE INIT
# ─────────────────────────────────────────
def init_firebase():
    """Inicializa Firebase con service account desde variable de entorno."""
    sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT", "")
    if not sa_json:
        raise ValueError("FIREBASE_SERVICE_ACCOUNT no está configurado.")
    sa_dict = json.loads(sa_json)
    if not firebase_admin._apps:
        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred)
    return firestore.client()

# ─────────────────────────────────────────
# CÁLCULOS
# ─────────────────────────────────────────
def calc_base(s):
    tipo = s.get("tipoLimpieza", "")
    if tipo in ("Inicial/Obra", "Check"):
        lim = float(s.get("horas", 0) or 0) * float(s.get("tarifa", 0) or 0)
    else:
        lim = float(s.get("precioLimpieza", 0) or 0)
    extras = sum(
        float(e.get("precio", 0) or 0) + float(e.get("importe", 0) or 0)
        for e in (s.get("extras") or [])
    )
    arreglos = float(s.get("arreglosImporte", 0) or 0)
    return lim + extras + arreglos

def fmt_eur(n):
    try:
        n = float(n)
    except:
        return "—"
    return f"{n:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_date(d):
    if not d:
        return "—"
    try:
        return datetime.date.fromisoformat(str(d)[:10]).strftime("%d/%m/%Y")
    except:
        return str(d)[:10]

# ─────────────────────────────────────────
# RANGO DE FECHAS
# ─────────────────────────────────────────
def get_date_range(mode):
    today = datetime.date.today()
    if mode == "semanal":
        # Semana anterior: lunes a domingo
        last_monday = today - datetime.timedelta(days=today.weekday() + 7)
        last_sunday  = last_monday + datetime.timedelta(days=6)
        label = f"Semana {last_monday.strftime('%d/%m')} – {last_sunday.strftime('%d/%m/%Y')}"
        return last_monday, last_sunday, label
    else:  # mensual
        first_day = today.replace(day=1)
        last_month_last = first_day - datetime.timedelta(days=1)
        last_month_first = last_month_last.replace(day=1)
        months_es = ["enero","febrero","marzo","abril","mayo","junio",
                     "julio","agosto","septiembre","octubre","noviembre","diciembre"]
        label = f"{months_es[last_month_last.month-1].capitalize()} {last_month_last.year}"
        return last_month_first, last_month_last, label

# ─────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────
def fetch_data(db, date_from, date_to):
    servicios_ref = db.collection("servicios").stream()
    props_ref     = {d.id: d.to_dict() for d in db.collection("propiedades").stream()}
    clientes_ref  = {d.id: d.to_dict() for d in db.collection("clientes").stream()}

    servicios = []
    for doc in servicios_ref:
        s = doc.to_dict()
        fecha_str = s.get("fechaServicio", "")
        if not fecha_str:
            continue
        try:
            fecha = datetime.date.fromisoformat(str(fecha_str)[:10])
        except:
            continue
        if date_from <= fecha <= date_to:
            s["_prop"]   = props_ref.get(s.get("propiedadId", ""), {})
            s["_cliente"] = clientes_ref.get(s.get("clienteId", ""), {})
            s["_fecha"]   = fecha
            servicios.append(s)

    # Agrupar por propiedad, guardando cliente por propiedad
    by_prop = {}
    prop_cliente = {}  # prop_nombre -> cliente_nombre
    for s in servicios:
        prop_nombre = s["_prop"].get("nombre", "Sin propiedad") if s["_prop"] else "Sin propiedad"
        cli_nombre  = s["_cliente"].get("nombre", "") if s["_cliente"] else ""
        by_prop.setdefault(prop_nombre, []).append(s)
        if prop_nombre not in prop_cliente:
            prop_cliente[prop_nombre] = cli_nombre

    # Ordenar propiedades y servicios dentro de cada una
    for k in by_prop:
        by_prop[k].sort(key=lambda x: x["_fecha"])

    return dict(sorted(by_prop.items())), prop_cliente

# ─────────────────────────────────────────
# GENERAR PDF
# ─────────────────────────────────────────
DARK       = colors.HexColor("#1e2a3a")
ACCENT     = colors.HexColor("#2563eb")
LIGHT_GRAY = colors.HexColor("#f0f2f5")
MID_GRAY   = colors.HexColor("#7a8a9e")
BORDER     = colors.HexColor("#dde1ea")
WHITE      = colors.white
EXTRA_BG   = colors.HexColor("#f5f7fa")
TOTAL_COL  = colors.HexColor("#1d4ed8")

def make_styles():
    return {
        "title": ParagraphStyle("title",
            fontName="Helvetica-Bold", fontSize=20, textColor=DARK,
            spaceAfter=4, leading=24),
        "subtitle": ParagraphStyle("subtitle",
            fontName="Helvetica", fontSize=10, textColor=MID_GRAY,
            spaceAfter=2, leading=14),
        "prop_header": ParagraphStyle("prop_header",
            fontName="Helvetica-Bold", fontSize=12, textColor=WHITE,
            leading=16, leftIndent=8),
        "service_date": ParagraphStyle("service_date",
            fontName="Helvetica-Bold", fontSize=9, textColor=DARK, leading=13),
        "service_tipo": ParagraphStyle("service_tipo",
            fontName="Helvetica", fontSize=9, textColor=MID_GRAY, leading=13),
        "service_price": ParagraphStyle("service_price",
            fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT,
            alignment=TA_RIGHT, leading=13),
        "extra_label": ParagraphStyle("extra_label",
            fontName="Helvetica", fontSize=8, textColor=MID_GRAY,
            leftIndent=16, leading=12),
        "extra_total": ParagraphStyle("extra_total",
            fontName="Helvetica", fontSize=8, textColor=MID_GRAY,
            alignment=TA_RIGHT, leading=12),
        "extras_sum": ParagraphStyle("extras_sum",
            fontName="Helvetica-Oblique", fontSize=8, textColor=MID_GRAY,
            leftIndent=16, leading=12),
        "line_total": ParagraphStyle("line_total",
            fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT,
            alignment=TA_RIGHT, leading=13),
        "prop_total": ParagraphStyle("prop_total",
            fontName="Helvetica-Bold", fontSize=10, textColor=TOTAL_COL,
            alignment=TA_RIGHT, leading=14),
        "grand_label": ParagraphStyle("grand_label",
            fontName="Helvetica-Bold", fontSize=12, textColor=DARK,
            leading=16),
        "grand_value": ParagraphStyle("grand_value",
            fontName="Helvetica-Bold", fontSize=12, textColor=TOTAL_COL,
            alignment=TA_RIGHT, leading=16),
        "nota": ParagraphStyle("nota",
            fontName="Helvetica-Oblique", fontSize=7.5, textColor=MID_GRAY,
            leftIndent=16, leading=11),
    }

def build_pdf(by_prop, label, mode, output_path):
    from reportlab.platypus import Table, TableStyle

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
    )
    W = A4[0] - 3.6*cm
    styles = make_styles()
    story = []
    today_str = datetime.date.today().strftime("%d/%m/%Y")

    # ── CABECERA ──
    title_tipo = "Prefactura Semanal" if mode == "semanal" else "Prefactura Mensual"
    story.append(Paragraph(f"Servicios por Propiedad — {label}", styles["title"]))
    story.append(Paragraph(f"{title_tipo} · Generado el {today_str}", styles["subtitle"]))
    story.append(Spacer(1, 0.4*cm))
    story.append(HRFlowable(width=W, thickness=1.5, color=ACCENT, spaceAfter=0.5*cm))

    grand_total = 0.0

    for prop_nombre, servicios in by_prop.items():
        block = []

        # Cabecera propiedad (fondo azul oscuro)
        prop_table = Table(
            [[Paragraph(prop_nombre, styles["prop_header"])]],
            colWidths=[W]
        )
        prop_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), DARK),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("ROUNDEDCORNERS", [4, 4, 0, 0]),
        ]))
        block.append(prop_table)

        prop_total = 0.0
        is_first = True

        for s in servicios:
            fecha      = fmt_date(s.get("fechaServicio"))
            tipo       = s.get("tipoLimpieza") or "N/A"
            ocupacion  = s.get("ocupacion") or ""
            extras     = s.get("extras") or []
            nota       = s.get("observaciones") or s.get("detalleArreglos") or ""
            arreglos_imp = float(s.get("arreglosImporte", 0) or 0)

            # Precio limpieza
            if tipo in ("Inicial/Obra", "Check"):
                precio_limp = float(s.get("horas", 0) or 0) * float(s.get("tarifa", 0) or 0)
            else:
                precio_limp = float(s.get("precioLimpieza", 0) or 0)

            # Extras
            extras_tarifa  = sum(float(e.get("precio", 0) or 0) for e in extras)
            extras_compras = sum(float(e.get("importe", 0) or 0) for e in extras)
            total_linea    = calc_base(s)
            prop_total    += total_linea

            # Separador entre servicios
            if not is_first:
                block.append(HRFlowable(width=W, thickness=0.5, color=BORDER, spaceAfter=0))
            is_first = False

            # Fila principal del servicio
            col_left  = W * 0.72
            col_right = W * 0.28

            top_row = Table(
                [[
                    Paragraph(f"<b>{fecha}</b>  {tipo}  <font color='#7a8a9e'>{ocupacion}</font>", styles["service_date"]),
                    Paragraph(fmt_eur(precio_limp) if precio_limp else "—", styles["service_price"]),
                ]],
                colWidths=[col_left, col_right]
            )
            top_row.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), WHITE),
                ("TOPPADDING",    (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                ("LEFTPADDING",   (0,0), (-1,-1), 10),
                ("RIGHTPADDING",  (0,0), (-1,-1), 10),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ]))
            block.append(top_row)

            # Nota/observaciones
            if nota:
                nota_row = Table(
                    [[Paragraph(f"Nota: {nota}", styles["nota"]), ""]],
                    colWidths=[col_left, col_right]
                )
                nota_row.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,-1), WHITE),
                    ("TOPPADDING",    (0,0), (-1,-1), 0),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                    ("LEFTPADDING",   (0,0), (-1,-1), 10),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 10),
                ]))
                block.append(nota_row)

            # Extras individuales
            if extras:
                for e in extras:
                    e_label = e.get("icon","■") + " " + e.get("label","")
                    e_precio = float(e.get("precio", 0) or 0)
                    e_importe = float(e.get("importe", 0) or 0)
                    if e_importe:
                        e_txt = f"{fmt_eur(e_precio)} + compra: {fmt_eur(e_importe)}"
                    else:
                        e_txt = fmt_eur(e_precio) if e_precio else "—"
                    e_row = Table(
                        [[Paragraph(f"■ ■ {e_label}: {e_txt.replace(' €','€')}", styles["extra_label"]), ""]],
                        colWidths=[col_left, col_right]
                    )
                    e_row.setStyle(TableStyle([
                        ("BACKGROUND", (0,0), (-1,-1), EXTRA_BG),
                        ("TOPPADDING",    (0,0), (-1,-1), 2),
                        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
                        ("LEFTPADDING",   (0,0), (-1,-1), 10),
                        ("RIGHTPADDING",  (0,0), (-1,-1), 10),
                    ]))
                    block.append(e_row)

                # Resumen extras + total línea
                extras_parts = []
                if extras_tarifa:
                    extras_parts.append(f"Extras: {fmt_eur(extras_tarifa)}")
                if extras_compras:
                    extras_parts.append(f"Compras: {fmt_eur(extras_compras)}")
                ext_sum_txt = " · ".join(extras_parts)

                sum_row = Table(
                    [[
                        Paragraph(ext_sum_txt, styles["extras_sum"]),
                        Paragraph(fmt_eur(total_linea), styles["line_total"]),
                    ]],
                    colWidths=[col_left, col_right]
                )
                sum_row.setStyle(TableStyle([
                    ("BACKGROUND", (0,0), (-1,-1), EXTRA_BG),
                    ("TOPPADDING",    (0,0), (-1,-1), 2),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                    ("LEFTPADDING",   (0,0), (-1,-1), 10),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 10),
                    ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ]))
                block.append(sum_row)

        # Total propiedad
        grand_total += prop_total
        total_row = Table(
            [[
                Paragraph(f"TOTAL {prop_nombre.split(' - ')[0] if ' - ' in prop_nombre else prop_nombre}", styles["grand_label"]),
                Paragraph(fmt_eur(prop_total), styles["prop_total"]),
            ]],
            colWidths=[W * 0.6, W * 0.4]
        )
        total_row.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,-1), LIGHT_GRAY),
            ("TOPPADDING",    (0,0), (-1,-1), 8),
            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
            ("LEFTPADDING",   (0,0), (-1,-1), 10),
            ("RIGHTPADDING",  (0,0), (-1,-1), 10),
            ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ("LINEABOVE",     (0,0), (-1,0), 1.5, ACCENT),
        ]))
        block.append(total_row)
        block.append(Spacer(1, 0.5*cm))

        story.append(KeepTogether(block[:4]))  # cabecera + primer servicio juntos
        story.extend(block[4:])

    # ── TOTAL GENERAL ──
    story.append(HRFlowable(width=W, thickness=2, color=ACCENT, spaceBefore=0.3*cm, spaceAfter=0.3*cm))
    gt_row = Table(
        [[
            Paragraph("TOTAL GENERAL", ParagraphStyle("gt_l",
                fontName="Helvetica-Bold", fontSize=14, textColor=DARK, leading=18)),
            Paragraph(fmt_eur(grand_total), ParagraphStyle("gt_r",
                fontName="Helvetica-Bold", fontSize=14, textColor=TOTAL_COL,
                alignment=TA_RIGHT, leading=18)),
        ]],
        colWidths=[W * 0.55, W * 0.45]
    )
    gt_row.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#eff6ff")),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 12),
        ("RIGHTPADDING",  (0,0), (-1,-1), 12),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(gt_row)

    doc.build(story)
    print(f"✅ PDF generado: {output_path}")
    return output_path

# ─────────────────────────────────────────
# ENVIAR EMAIL
# ─────────────────────────────────────────
def send_email(pdf_path, label, mode, n_servicios, n_propiedades, asunto_extra=""):
    tipo_txt = "Semanal" if mode == "semanal" else "Mensual"
    subject  = f"ServiGestión — Prefactura {tipo_txt}: {label}{asunto_extra}"

    if mode == "semanal":
        body = f"""Hola,

Adjunta encontrarás la prefactura de la semana: {label}

Resumen:
• Propiedades con actividad: {n_propiedades}
• Total servicios: {n_servicios}

Este email se genera automáticamente cada lunes.

Un saludo,
ServiGestión — Mallorca Home Checkers
"""
    else:
        body = f"""Hola,

Adjunta encontrarás el resumen mensual de servicios: {label}

Resumen:
• Propiedades con actividad: {n_propiedades}
• Total servicios: {n_servicios}

Este email se genera automáticamente el primer día de cada mes.

Un saludo,
ServiGestión — Mallorca Home Checkers
"""

    msg = MIMEMultipart()
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with open(pdf_path, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(pdf_path)}"')
    msg.attach(part)

    import ssl
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context) as server:
        server.login(EMAIL_FROM, GMAIL_APP_PWD)
        server.send_message(msg)
    print(f"✅ Email enviado a {EMAIL_TO}")

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "semanal"
    assert mode in ("semanal", "mensual"), "Uso: generate_prefactura.py [semanal|mensual]"

    print(f"🚀 Modo: {mode}")
    db = init_firebase()

    date_from, date_to, label = get_date_range(mode)
    print(f"📅 Rango: {date_from} → {date_to}  ({label})")

    by_prop, prop_cliente = fetch_data(db, date_from, date_to)
    n_props = len(by_prop)
    n_servs = sum(len(v) for v in by_prop.values())
    print(f"📊 {n_props} propiedades · {n_servs} servicios")

    if n_servs == 0:
        print("ℹ️  Sin servicios en este período — no se genera email.")
        return

    tipo_txt = "Semanal" if mode == "semanal" else "Mensual"

    # ── Separar: Myne vs Resto ──
    CLIENTE_SEPARADO = "Myne"
    by_prop_myne  = {k: v for k, v in by_prop.items() if prop_cliente.get(k, "").strip().lower() == CLIENTE_SEPARADO.lower()}
    by_prop_resto = {k: v for k, v in by_prop.items() if prop_cliente.get(k, "").strip().lower() != CLIENTE_SEPARADO.lower()}

    # ── Email Myne ──
    if by_prop_myne:
        n_s = sum(len(v) for v in by_prop_myne.values())
        fname = f"Prefactura_{tipo_txt}_{CLIENTE_SEPARADO}_{label.replace(' ','_').replace('/','_')}.pdf"
        path  = f"/tmp/{fname}"
        build_pdf(by_prop_myne, label, mode, path)
        send_email(path, label, mode, n_s, len(by_prop_myne), asunto_extra=f" — {CLIENTE_SEPARADO}")
        print(f"✅ Email Myne enviado ({n_s} servicios)")
    else:
        print("ℹ️  Sin servicios de Myne en este período.")

    # ── Email Resto ──
    if by_prop_resto:
        n_s = sum(len(v) for v in by_prop_resto.values())
        fname = f"Prefactura_{tipo_txt}_Resto_{label.replace(' ','_').replace('/','_')}.pdf"
        path  = f"/tmp/{fname}"
        build_pdf(by_prop_resto, label, mode, path)
        send_email(path, label, mode, n_s, len(by_prop_resto), asunto_extra=" — Resto clientes")
        print(f"✅ Email Resto enviado ({n_s} servicios)")
    else:
        print("ℹ️  Sin servicios del resto en este período.")

if __name__ == "__main__":
    main()
