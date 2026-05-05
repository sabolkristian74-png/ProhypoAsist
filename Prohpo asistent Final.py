import json
import os
import re
from html import escape
from datetime import datetime, timedelta, date
from pathlib import Path
from functools import wraps
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, jsonify
from calculations.hypo import (
    calculate_monthly_payment,
    generate_amortization_schedule,
    optimize_insurance_initial,
)

app = Flask(__name__)
app.secret_key = "prohypo-secret"
FAQ_FILE_PATH = Path(__file__).resolve().parent / "data" / "faq_items.json"
INTERESTING_NUMBERS_FILE_PATH = Path(__file__).resolve().parent / "data" / "zaujimave_cisla.json"

# Heslo na vstup do aplikácie - môžete ho zmeniť
APP_PASSWORD = "0000"

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('logged_in') is not True:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

APP_TEMPLATE = """<!doctype html>
<html lang="sk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ProHypo Asistent </title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;background:#f0f6fc;color:#1a2e5a;margin:0;padding:0;overflow-x:hidden;}
    .app-wrapper{display:flex;min-height:100vh;gap:0;}
    .sidebar{width:200px;background:#fff;border-right:1px solid #ddd;padding:16px 0;box-shadow:2px 0 8px rgba(0,0,0,.08);}
    .nav{display:flex;flex-direction:column;gap:2px;padding:0;margin:0;}
    .nav a{display:block;padding:12px 16px;text-decoration:none;color:#29b6e8;font-weight:500;border-left:3px solid transparent;font-size:0.95rem;transition:all 0.2s;}
    .nav a:hover{background:#f0f6fc;border-left-color:#29b6e8;color:#1e8fb7;}
    .nav a[href*="logout"]{color:#c00;margin-top:auto;}
    .main-content{flex:1;padding:20px;overflow-y:auto;}
    .container{width:100%;max-width:none;margin:0;padding:0;box-sizing:border-box;}
    .card{background:#fff;border-radius:8px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.1);}
    .app-shell{width:100%;max-width:none;margin:0;box-sizing:border-box;background:#fff;border-radius:8px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,.1);}
    input,select,textarea{width:100%;padding:8px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px;}
    .btn{background:#29b6e8;color:white;padding:10px 14px;border:none;border-radius:4px;cursor:pointer;}
    .btn:hover{background:#1e8fb7;}
    .error{color:#c00;font-weight:bold;}
    .result{background:#edf7f9;color:#046f8d;border:1px solid #29b6e8;padding:12px;border-radius:4px;white-space:pre-wrap;}
    .copy-btn{margin-bottom:10px;}
    .faq-group{margin-bottom:20px;max-width:50%;margin-left:0;margin-right:auto;}
    .faq-item{margin:0 0 10px;}
    .faq-question{width:100%;text-align:left;background:#edf7f9;color:#046f8d;border:1px solid #29b6e8;padding:10px;border-radius:4px;cursor:pointer;font-weight:600;}
    .faq-answer{display:none;background:#f8fbff;border:1px solid #d6e6f5;border-radius:4px;padding:10px;margin-top:6px;white-space:pre-wrap;}
    .form-container{max-width:50%;margin:0;}
  </style>
  <script>
    function copyToClipboard(elementId) {
      const text = document.getElementById(elementId).innerText;
      navigator.clipboard.writeText(text)
        .then(() => alert('Text bol skopírovaný do schránky.'))
        .catch((err) => alert('Kopírovanie zlyhalo: ' + err));
    }

    function openEmailInOutlook(elementId, recipientEmail, customSubject) {
      const element = document.getElementById(elementId);
      const emailBody = element.textContent || element.innerText;
      if (!recipientEmail || recipientEmail.trim() === '') {
        alert('Zadajte emailovú adresu príjemcu!');
        return;
      }
      const subject = customSubject || 'Správa od ProHypo Asistenta';
      const mailtoLink = 'mailto:' + encodeURIComponent(recipientEmail) + 
                         '?subject=' + encodeURIComponent(subject) + 
                         '&body=' + encodeURIComponent(emailBody);
      window.location.href = mailtoLink;
    }

    function updateVystupnyMailFields() {
      const select = document.querySelector("select[name='typ_mailu']");
      if (!select) return;
      const typ = select.value;
      const nehnutelnost = document.getElementById('nehnutelnost_fields');
      const zivotne = document.getElementById('zivotne_fields');
      if (!nehnutelnost || !zivotne) return;
      if (typ === 'nehnutelnost') {
        nehnutelnost.style.display = 'block';
        zivotne.style.display = 'none';
      } else {
        nehnutelnost.style.display = 'none';
        zivotne.style.display = 'block';
      }
    }

    window.addEventListener('load', updateVystupnyMailFields);

    function toggleFaqAnswer(button) {
        const answer = button.nextElementSibling;
        if (!answer) return;
        const isOpen = answer.style.display === 'block';
        answer.style.display = isOpen ? 'none' : 'block';
    }

    function toggleFeedbackForm() {
        const container = document.getElementById('feedbackContainer');
        if (!container) return;
        const isOpen = container.style.display === 'block';
        container.style.display = isOpen ? 'none' : 'block';
    }
  </script>
</head>
<body style="margin:0;padding:0;overflow-x:hidden;">
<div class="app-wrapper">
  <div class="sidebar">
    <div class="nav">
      <a href="{{ url_for('home') }}">🏠 Domov</a>
      <a href="{{ url_for('notice') }}">📅 Výpovedná lehota</a>
      <a href="{{ url_for('vypocetny_email') }}">📧 Výročný email</a>
      <a href="{{ url_for('vystupny_mail') }}">📤 Výstupný mail</a>
      <a href="{{ url_for('backoffice') }}">⚙️ Backoffice email</a>
      <a href="{{ url_for('hypo') }}">🏦 Hypo VS Poistná suma</a>
      <a href="{{ url_for('izp') }}">📊 IŽP</a>
      <a href="{{ url_for('rzp') }}">🛡️ RŽP</a>
      <a href="{{ url_for('najcastejsie_otazky') }}">❓ FAQ</a>
      <a href="{{ url_for('zaujimave_cisla') }}">📈 Čísla</a>
      <a href="{{ url_for('logout') }}">🚪 Odhlásiť sa</a>
    </div>
  </div>
  
  <div class="main-content">
    <div class="container">
      <div class="app-shell">
        <h1 style="margin-top:0;">ProHypo servis asistent</h1>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for cat, msg in messages %}
              <p class="error">{{ msg }}</p>
            {% endfor %}
          {% endif %}
        {% endwith %}
        {{ content|safe }}
      </div>
    </div>
  </div>
</div>
</body>
</html>"""


def yes_no(value):
    return "Áno" if value else "Nie"


def calculate_notice_date(day_text, month_text, year_text):
    day_text = str(day_text).strip()
    month_text = str(month_text).strip()
    year_text = str(year_text).strip()
    if not all([day_text, month_text, year_text]):
        raise ValueError("Vyplň všetky polia!")
    day = int(day_text)
    month = int(month_text)
    year = int(year_text)
    if not (1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2100):
        raise ValueError("Rozsah: deň 1-31, mesiac 1-12, rok 2000-2100")
    target_date = datetime.strptime(f"{year:04d}-{month:02d}-{day:02d}", "%Y-%m-%d")
    result_date = target_date - timedelta(days=44)
    return result_date.strftime("%d.%m.%Y")


def build_email_text(oslovenie, meno, typ, adresa_nehnutelnosti, poistovna, zmluva, vyrocie_pz):
    oslovenie = str(oslovenie).strip()
    meno = str(meno).strip()
    typ = str(typ).strip()
    adresa_nehnutelnosti = str(adresa_nehnutelnosti).strip()
    poistovna = str(poistovna).strip()
    zmluva = str(zmluva).strip()
    vyrocie_pz = str(vyrocie_pz).strip()
    if not all([oslovenie, meno, typ, adresa_nehnutelnosti, poistovna, zmluva, vyrocie_pz]):
        raise ValueError("Vyplň všetky polia!")
    return (
        f"Dobrý deň {oslovenie} {meno},\n\n"
        f"posielam Vám informáciu o blížiacom sa výročí Vašej poistnej zmluvy {typ} na adrese {adresa_nehnutelnosti} v poisťovni {poistovna} (č. zmluvy: {zmluva}), ktorú sme spoločne uzatvárali.\n"
        f"Výročie tejto poistnej zmluvy je {vyrocie_pz}. Pravdepodobne Vám do mailu prišiel nový predpis na platbu nasledujúceho obdobia.\n"
        f"Neprehliadnite dátum zaplatenia poistnej zmluvy. V prípade nezaplatenia, zmluva zaniká. Spoločne by sme tak museli riešiť proces uzatvárania a vinkulácie zmluvy nanovo.\n\n"
        f"Ak ste medzičasom zmluvu zaplatili považujte tento email za vybavený.\n"
        f"V prípade otázok ma kontaktujte.\n\n"
        f"Za odpoveď ďakujem a prajem príjemný zvyšok dňa,"
    )


def build_backoffice_email_text(meno_klienta, cislo_zmluvy, typ_zmluvy, vinkulacia, slsp, prioritne, datum_spracovania, zaznam, pca, delenie_provizie, ine, poznamky):
    meno_klienta = str(meno_klienta).strip()
    cislo_zmluvy = str(cislo_zmluvy).strip()
    typ_zmluvy = str(typ_zmluvy).strip()
    vinkulacia = str(vinkulacia).strip()
    slsp = str(slsp).strip()
    prioritne = str(prioritne).strip()
    datum_spracovania = str(datum_spracovania).strip()
    zaznam = str(zaznam).strip()
    pca = str(pca).strip()
    delenie_provizie = str(delenie_provizie).strip()
    ine = str(ine).strip()
    poznamky = str(poznamky).strip()

    if not all([meno_klienta, cislo_zmluvy, typ_zmluvy, vinkulacia, zaznam, pca]):
        raise ValueError("Vyplň všetky povinné polia!")

    priority_text = "PRIORITNÉ!\n\n" if prioritne.lower() == "áno" else ""
    datum_text = f"Dátum spracovania – banka: {datum_spracovania}\n" if datum_spracovania else ""

    return f"""{priority_text}Ahojte,\n\nposielam informácie k nahratiu a spracovaniu zmluvy\nKlient: {meno_klienta}\nČíslo zmluvy: {cislo_zmluvy}\nTyp zmluvy: {typ_zmluvy}\nVinkulácia: {vinkulacia}\nSLSP: {slsp}\n{datum_text}Záznam: {zaznam}\nPCA: {pca}\nDelenie provízie: {delenie_provizie}\nIné: {ine}\nPoznámky (čo konkrétne treba a netreba urobiť): {poznamky}\nZa spracovanie ďakujem."""


def load_faq_items():
    if not FAQ_FILE_PATH.exists():
        return []
    with FAQ_FILE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    faq_items = []
    for item in data:
        sekcia = str(item.get("sekcia", "Bez sekcie")).strip() or "Bez sekcie"
        otazka = str(item.get("otazka", "")).strip()
        odpoved = str(item.get("odpoved", "")).strip()
        if not otazka or not odpoved:
            continue
        faq_items.append({"sekcia": sekcia, "otazka": otazka, "odpoved": odpoved})
    return faq_items


def linkify_text(text):
    if not text:
        return ""
    pattern = re.compile(r"(https?://[^\s<>'\"]+)")
    return pattern.sub(
        r"<a href='\1' target='_blank' rel='noopener noreferrer'>\1</a>",
        text,
    )


def load_interesting_numbers():
    if not INTERESTING_NUMBERS_FILE_PATH.exists():
        return []
    with INTERESTING_NUMBERS_FILE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    items = []
    for item in data:
        sekcia = str(item.get("sekcia", "Vedeli ste, že...?")).strip() or "Vedeli ste, že...?"
        otazka = str(item.get("otazka", "")).strip()
        odpoved = str(item.get("odpoved", "")).strip()
        if not otazka or not odpoved:
            continue
        items.append({"sekcia": sekcia, "otazka": otazka, "odpoved": odpoved})
    return items


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get('logged_in') is True:
        return redirect(url_for('home'))

    if request.method == "POST":
        password = request.form.get("password", "")
        if password == APP_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('home'))
        else:
            session['logged_in'] = False
            flash("Nesprávne heslo! Skúste znova.")
    
    login_template = """<!doctype html>
<html lang="sk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ProHypo Asistent - Prihlásenie</title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;background:#f0f6fc;color:#1a2e5a;margin:0;padding:0;display:flex;align-items:center;justify-content:center;min-height:100vh;}
    .login-container{background:#fff;border-radius:8px;padding:40px;box-shadow:0 2px 8px rgba(0,0,0,.15);max-width:400px;width:100%;}
    h1{text-align:center;color:#1a2e5a;margin-bottom:30px;}
    input{width:100%;padding:10px;margin:10px 0 20px;border:1px solid #ccc;border-radius:4px;box-sizing:border-box;}
    .btn{background:#29b6e8;color:white;padding:11px 15px;border:none;border-radius:4px;cursor:pointer;width:100%;font-weight:bold;}
    .btn:hover{background:#1e8fb7;}
    .error{color:#c00;text-align:center;margin-bottom:15px;font-weight:bold;}
  </style>
</head>
<body>
  <div class="login-container">
    <h1>🔐 ProHypo Asistent</h1>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        {% for msg in messages %}
          <p class="error">{{ msg }}</p>
        {% endfor %}
      {% endif %}
    {% endwith %}
    <form method="post">
      <label for="password" style="display:block;margin-bottom:10px;">Heslo:</label>
      <input type="password" id="password" name="password" placeholder="Zadajte heslo" required autofocus>
      <button class="btn" type="submit">Prihlásiť sa</button>
    </form>
  </div>
</body>
</html>"""
    
    return render_template_string(login_template)


@app.route("/logout")
def logout():
    session.clear()
    flash("Odhlásili ste sa.")
    return redirect(url_for('login'))


@app.route("/")
@login_required
def home():
    content = (
        "<div style='display:flex; flex-direction:column; min-height:60vh;'>"
        "<div><p>Víta ťa ProHypo Asistent. Vyber si modul v ktorom chceš pracovať.</p></div>"
        "<div style='margin-top:auto; padding-top:30px; border-top:1px solid #e0e0e0;'>"
        "<button type='button' class='btn' onclick=\"toggleFeedbackForm()\">Mám nápad / Našiel som chybu</button>"
        "<div id='feedbackContainer' style='display:none; margin-top:15px; transition:all 0.3s ease;'>"
        "<p style='font-size:0.9rem;color:#666;'>Našiel si chybu alebo máš nápad na vylepšenie? Napíš nám o tom!</p>"
        "<form>"
        "<label for='chybatext' style='display:block;margin-bottom:8px;font-weight:bold;'>Tvoja správa:</label>"
        "<textarea id='chybatext' placeholder='Opíš chybu alebo podaj nápad na zlepšenie...' style='min-height:120px;'></textarea>"
        "<button type='button' class='btn' onclick=\"openEmailInOutlook('chybatext', 'kristiansamuel.sabol@prohypo.sk', 'Chyba alebo zmena v aplikácií')\">Poslať na programátora</button>"
        "</form>"
        "</div>"
        "</div>"
        "</div>"
    )
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/notice", methods=["GET", "POST"])
@login_required
def notice():
    response = None
    today = datetime.now()
    if request.method == "POST":
        day = request.form.get("day")
        month = request.form.get("month")
        year = request.form.get("year")
        try:
            response = calculate_notice_date(day, month, year)
        except Exception as e:
            flash(str(e))

    day_value = request.form.get('day') or str(today.day)
    month_value = request.form.get('month') or str(today.month)
    year_value = request.form.get('year') or str(today.year)

    result_html = ""
    if response:
        result_html = f"<div class='result'>Dátum doručenia výpovede: <strong>{response}</strong></div>"
    content = (
        "<div class='form-container'>"
        "<h2>Zadaj dátum výročia PZ</h2>"
        "<form method='post'>"
        f"Deň:<input name='day' value='{day_value}' required>"
        f"Mesiac:<input name='month' value='{month_value}' required>"
        f"Rok:<input name='year' value='{year_value}' required>"
        "<button class='btn' type='submit'>Vypočítať</button>"
        "</form>"
        f"{result_html}"
        "</div>"
    )

    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/email")
@login_required
def email_redirect():
    return redirect(url_for('vypocetny_email'))


@app.route("/vypocetny_email", methods=["GET", "POST"])
@login_required
def vypocetny_email():
    result = None
    today_str = datetime.now().strftime("%d.%m.%Y")
    if request.method == "POST":
        data = {k: request.form.get(k, "") for k in ["oslovenie", "meno", "typ", "adresa_nehnutelnosti", "poistovna", "zmluva", "vyrocie_pz"]}
        try:
            result = build_email_text(**data)
        except Exception as e:
            flash(str(e))

    result_block = ""
    email_priemcu = request.form.get('email_priemcu', '')
    if result:
        result_block = f"""<div class='result'>
        <button class='btn copy-btn' type='button' onclick="copyToClipboard('emailResult')">Kopírovať email</button>
        <button class='btn copy-btn' type='button' onclick="openEmailInOutlook('emailResult', '{email_priemcu}')">Otvoriť v Outlooku</button>
        <pre id='emailResult'>{result}</pre>
        </div>"""

    prazdne_data = {
        'meno': request.form.get('meno', ''),
        'typ': request.form.get('typ', 'byt'),
        'adresa_nehnutelnosti': request.form.get('adresa_nehnutelnosti', ''),
        'poistovna': request.form.get('poistovna', 'Allianz'),
        'zmluva': request.form.get('zmluva', ''),
        'vyrocie_pz': request.form.get('vyrocie_pz', today_str),
    }

    content = ""
    content += "<div class='form-container'>"
    content += "<h2>Výročný email</h2>"
    content += "<form method='post'>"
    content += "Oslovenie:<select name='oslovenie'><option value='pán'>pán</option><option value='pani'>pani</option></select>"
    content += f"Meno:<input name='meno' value='{prazdne_data['meno']}' required>"
    content += f"Email príjemcu:<input name='email_priemcu' type='email' value='{request.form.get('email_priemcu', '')}'>"
    content += "Typ nehnuteľnosti:<select name='typ' required>"
    content += f"<option value='bytu' {'selected' if prazdne_data['typ'].lower()=='bytu' else ''}>Byt</option>"
    content += f"<option value='domu' {'selected' if prazdne_data['typ'].lower()=='domu' else ''}>Dom</option>"
    content += "</select>"
    content += f"Adresa nehnuteľnosti:<input name='adresa_nehnutelnosti' value='{prazdne_data['adresa_nehnutelnosti']}' required>"
    content += "Poisťovňa:<select name='poistovna' required>"
    content += f"<option value='Allianz' {'selected' if prazdne_data['poistovna']=='Allianz' else ''}>Allianz</option>"
    content += f"<option value='Generali' {'selected' if prazdne_data['poistovna']=='Generali' else ''}>Generali</option>"
    content += f"<option value='Uniqa' {'selected' if prazdne_data['poistovna']=='Uniqa' else ''}>Uniqa</option>"
    content += f"<option value='Premium' {'selected' if prazdne_data['poistovna']=='Premium' else ''}>Premium</option>"
    content += f"<option value='Union' {'selected' if prazdne_data['poistovna']=='Union' else ''}>Union</option>"
    content += f"<option value='Colonnade' {'selected' if prazdne_data['poistovna']=='Colonnade' else ''}>Colonnade</option>"

    content += "</select>"
    content += f"Číslo zmluvy:<input name='zmluva' value='{prazdne_data['zmluva']}' required>"
    content += f"Výročie PZ:<input name='vyrocie_pz' value='{prazdne_data['vyrocie_pz']}' required>"
    content += "<button class='btn' type='submit'>Vygenerovať</button>"
    content += "</form>"
    content += "</div>"
    content += result_block
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/vystupny_mail", methods=["GET", "POST"])
@login_required
def vystupny_mail():
    result = None
    if request.method == "POST":
        data = {
            "typ_mailu": request.form.get("typ_mailu", "nehnutelnost"),
            "oslovenie": request.form.get("oslovenie", ""),
            "priezvisko": request.form.get("priezvisko", ""),
            "typ_nehnutelnosti": request.form.get("typ_nehnutelnosti", ""),
            "adresa": request.form.get("adresa", ""),
            "portal_uzavretia": request.form.get("portal_uzavretia", "najpoistenie"),
            "poistovna1": request.form.get("poistovna1", ""),
            "pocet_zmluv": request.form.get("pocet_zmluv", "1"),
            "poistovna2": request.form.get("poistovna2", ""),
            "zaciatok_poistenia": request.form.get("zaciatok_poistenia", ""),
        }

        typ_mailu = data["typ_mailu"]
        oslovenie = data["oslovenie"].strip()
        priezvisko = data["priezvisko"].strip()

        if typ_mailu == "nehnutelnost":
            typ = data["typ_nehnutelnosti"].strip()
            adresa = data["adresa"].strip()
            portal_uzavretia = data["portal_uzavretia"].strip().lower()
            if portal_uzavretia == "externy_portal":
                portal_sentence = "Platobné údaje nájdete v tele mailu, ktorý Vám prišiel z portálu poisťovne spolu so zmluvnou dokumentáciou."
            else:
                portal_sentence = "Platobné údaje nájdete v tele mailu, ktorý Vám prišiel zo systému Najpoistenie spolu so zmluvnou dokumentáciou."
            if not all([oslovenie, priezvisko, typ, adresa]):
                flash("Vyplňte všetky polia pre nehnuteľnosť!")
            else:
                result = (
                    f"Dobrý deň {oslovenie} {priezvisko},\n\n"
                    f"Práve som Vám uzatvoril poistenie {typ} na adrese {adresa}.\n"
                    f"{portal_sentence}\n"
                    f"Prosím Vás o zaslanie potvrdenia o zaplatení, aby som mohol zmluvu vinkulovať v prospech financujúcej banky.\n\n"
                    f"V prípade otázok ma neváhajte kontaktovať"
                )
        else:  # zivotne poistenie
            poistovna1 = data["poistovna1"].strip()
            pocet_zmluv = data["pocet_zmluv"].strip()
            poistovna2 = data["poistovna2"].strip()
            zaciatok = data["zaciatok_poistenia"].strip()

            if not all([oslovenie, priezvisko, poistovna1, pocet_zmluv, zaciatok]):
                flash("Vyplňte všetky povinné polia pre životné poistenie!")
            elif pocet_zmluv == "2" and not poistovna2:
                flash("Vyplňte druhú poisťovňu pre 2 zmluvy!")
            else:
                if pocet_zmluv == "2" and poistovna2:
                    poistenia = f"v poisťovni {poistovna1} a v poisťovni {poistovna2}"
                    result = (
                        f"Dobrý deň {oslovenie} {priezvisko},\n\n"
                        f"V prílohe Vám posielam poistné zmluvy životného poistenia, ktoré sme spolu uzatvorili {poistenia}.\n\n"
                        f"Platobné údaje ({poistovna1}):\n"
                        f"IBAN -\nVS -\nSuma -\nSplatnosť -\n\n"
                        f"Platobné údaje ({poistovna2}):\n"
                        f"IBAN -\nVS -\nSuma -\nSplatnosť -\n\n"
                        f"Odporúčam Vám nastaviť si trvalé príkazy.\n"
                        f"Poistné krytie je nastavené tak, ako sme si ho spolu prechádzali so začiatkom poistenia od {zaciatok}.\n\n"
                        f"V prípade akýchkoľvek otázok, zmien/úprav v zmluvách do budúcna, ma neváhajte kontaktovať.\n\n"
                        f"S pozdravom,\n"
                    )
                else:
                    poistenia = f"v poisťovni {poistovna1}"
                    result = (
                        f"Dobrý deň {oslovenie} {priezvisko},\n\n"
                        f"V prílohe Vám posielam poistnú zmluvu Životného poistenia, ktorú sme spolu uzatvorili {poistenia}.\n\n"
                        f"Platobné údaje:\n"
                        f"IBAN -\nVS -\nSuma -\nSplatnosť -\n\n"
                        f"Odporúčam Vám nastaviť si trvalý príkaz.\n"
                        f"Poistné krytie je nastavené tak, ako sme si ho spolu prechádzali so začiatkom poistenia od {zaciatok}.\n\n"
                        f"V prípade akýchkoľvek otázok, zmien/úprav v zmluve do budúcna, ma neváhajte kontaktovať.\n\n"
                        f"S pozdravom,\n"
                    )

    result_block = ""
    email_priemcu = request.form.get('email_priemcu', '')
    if result:
        result_block = f"""<div class='result'>
        <button class='btn copy-btn' type='button' onclick=\"copyToClipboard('vystupnyResult')\">Kopírovať mail</button>
        <button class='btn copy-btn' type='button' onclick=\"openEmailInOutlook('vystupnyResult', '{email_priemcu}')\">Otvoriť v Outlooku</button>
        <pre id='vystupnyResult'>{result}</pre>
        </div>"""

    form_data = {
        'typ_mailu': request.form.get('typ_mailu', 'nehnutelnost'),
        'oslovenie': request.form.get('oslovenie', 'pán'),
        'priezvisko': request.form.get('priezvisko', ''),
        'typ_nehnutelnosti': request.form.get('typ_nehnutelnosti', 'Byt'),
        'adresa': request.form.get('adresa', ''),
        'portal_uzavretia': request.form.get('portal_uzavretia', 'najpoistenie'),
        'poistovna1': request.form.get('poistovna1', 'Uniqa'),
        'pocet_zmluv': request.form.get('pocet_zmluv', '1'),
        'poistovna2': request.form.get('poistovna2', ''),
        'zaciatok_poistenia': request.form.get('zaciatok_poistenia', '01.01.2026'),
    }

    content = ""
    content += "<div class='form-container'>"
    content += "<h2>Výstupný mail</h2>"
    content += "<form method='post'>"
    content += f"Email príjemcu:<input name='email_priemcu' type='email' value='{request.form.get('email_priemcu', '')}'>"
    content += "Typ výstupného mailu: <select name='typ_mailu' onchange='updateVystupnyMailFields()'>"
    content += f"<option value='nehnutelnost' {'selected' if form_data['typ_mailu']=='nehnutelnost' else ''}>Poistenie nehnuteľnosti</option>"
    content += f"<option value='zivotne' {'selected' if form_data['typ_mailu']=='zivotne' else ''}>Životné poistenie</option>"
    content += "</select>"

    content += "Oslovenie:<select name='oslovenie'><option value='pán' " + ("selected" if form_data['oslovenie']=='pán' else "") + ">pán</option><option value='pani' " + ("selected" if form_data['oslovenie']=='pani' else "") + ">pani</option></select>"
    content += f"Priezvisko:<input name='priezvisko' value='{form_data['priezvisko']}' required>"

    # Sekcia pre nehnuteľnosť
    content += f"<div id='nehnutelnost_fields' style='display:{'block' if form_data['typ_mailu']=='nehnutelnost' else 'none'};'>"
    content += "Typ nehnuteľnosti:<select name='typ_nehnutelnosti'>"
    content += f"<option value='bytu' {'selected' if form_data['typ_nehnutelnosti']=='Byt' else ''}>Byt</option>"
    content += f"<option value='rodinného domu' {'selected' if form_data['typ_nehnutelnosti']=='Rodinný dom' else ''}>Rodinný dom</option>"
    content += f"<option value='apartmánu' {'selected' if form_data['typ_nehnutelnosti']=='Apartmán' else ''}>Apartmán</option>"
    content += "</select>"
    content += f"Adresa nehnuteľnosti:<input name='adresa' value='{form_data['adresa']}' >"
    content += "Uzatvorenie poistenia: <select name='portal_uzavretia'>"
    content += f"<option value='najpoistenie' {'selected' if form_data['portal_uzavretia']=='najpoistenie' else ''}>Najpoistenie</option>"
    content += f"<option value='externy_portal' {'selected' if form_data['portal_uzavretia']=='externy_portal' else ''}>Externý portál</option>"
    content += "</select>"
    content += "</div>"

    # Sekcia pre životné poistenie
    content += f"<div id='zivotne_fields' style='display:{'block' if form_data['typ_mailu']=='zivotne' else 'none'};'>"
    content += "Poisťovňa:<select name='poistovna1'>"
    content += f"<option value='Uniqa' {'selected' if form_data['poistovna1']=='Uniqa' else ''}>Uniqa</option>"
    content += f"<option value='NN' {'selected' if form_data['poistovna1']=='NN' else ''}>NN</option>"
    content += f"<option value='ČSOB' {'selected' if form_data['poistovna1']=='ČSOB' else ''}>ČSOB</option>"
    content += f"<option value='Generali' {'selected' if form_data['poistovna1']=='Generali' else ''}>Generali</option>"
    content += "</select>"
    content += "Počet zmlúv:<select name='pocet_zmluv'>"
    content += f"<option value='1' {'selected' if form_data['pocet_zmluv']=='1' else ''}>1</option>"
    content += f"<option value='2' {'selected' if form_data['pocet_zmluv']=='2' else ''}>2</option>"
    content += "</select>"
    content += "Poisťovňa 2:<select name='poistovna2'>"
    content += f"<option value='' {'selected' if form_data['poistovna2']=='' else ''}>- žiadna -</option>"
    content += f"<option value='Uniqa' {'selected' if form_data['poistovna2']=='Uniqa' else ''}>Uniqa</option>"
    content += f"<option value='NN' {'selected' if form_data['poistovna2']=='NN' else ''}>NN</option>"
    content += f"<option value='ČSOB' {'selected' if form_data['poistovna2']=='ČSOB' else ''}>ČSOB</option>"
    content += f"<option value='Generali' {'selected' if form_data['poistovna2']=='Generali' else ''}>Generali</option>"
    content += "</select>"
    content += f"Začiatok poistenia:<input name='zaciatok_poistenia' value='{form_data['zaciatok_poistenia']}' >"
    content += "</div>"

    content += "<button class='btn' type='submit'>Vygenerovať</button>"
    content += "</form>"
    content += "</div>"
    content += result_block
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/backoffice", methods=["GET", "POST"])
@login_required
def backoffice():
    result = None
    if request.method == "POST":
        data = {
            "meno_klienta": request.form.get("meno_klienta", ""),
            "cislo_zmluvy": request.form.get("cislo_zmluvy", ""),
            "typ_zmluvy": request.form.get("typ_zmluvy", ""),
            "vinkulacia": yes_no(request.form.get("vinkulacia") == "on"),
            "slsp": yes_no(request.form.get("slsp") == "on"),
            "prioritne": yes_no(request.form.get("prioritne") == "on"),
            "datum_spracovania": request.form.get("datum_spracovania", ""),
            "zaznam": yes_no(request.form.get("zaznam") == "on"),
            "pca": yes_no(request.form.get("pca") == "on"),
            "delenie_provizie": request.form.get("delenie_provizie", "Žiadne delenie"),
            "ine": request.form.get("ine", ""),
            "poznamky": request.form.get("poznamky", ""),
        }
        try:
            result = build_backoffice_email_text(**data)
        except Exception as e:
            flash(str(e))

    result_block = ""
    email_priemcu = request.form.get('email_priemcu', '')
    meno_klienta = request.form.get('meno_klienta', '')
    if result:
        result_block = f"""<div class='result'>
        <button class='btn copy-btn' type='button' onclick=\"copyToClipboard('backofficeResult')\">Kopírovať email</button>
        <button class='btn copy-btn' type='button' onclick=\"openEmailInOutlook('backofficeResult', '{email_priemcu}', '{meno_klienta}')\">Otvoriť v Outlooku</button>
        <pre id='backofficeResult'>{result}</pre>
        </div>"""

    form_data = {
        'meno_klienta': request.form.get('meno_klienta', ''),
        'cislo_zmluvy': request.form.get('cislo_zmluvy', ''),
        'typ_zmluvy': request.form.get('typ_zmluvy', 'nehnuteľnosť'),
        'vinkulacia': 'checked' if request.form.get('vinkulacia') else '',
        'slsp': 'checked' if request.form.get('slsp') else '',
        'prioritne': 'checked' if request.form.get('prioritne') else '',
        'datum_spracovania': request.form.get('datum_spracovania', ''),
        'zaznam': 'checked' if request.form.get('zaznam') else '',
        'pca': 'checked' if request.form.get('pca') else '',
        'delenie_provizie': request.form.get('delenie_provizie', 'Žiadne delenie'),
        'ine': request.form.get('ine', ''),
        'poznamky': request.form.get('poznamky', ''),
    }

    content = ""
    content += "<div class='form-container'>"
    content += "<h2>Backoffice email</h2>"
    content += "<form method='post'>"
    content += f"Email príjemcu:<input name='email_priemcu' type='email' value='{request.form.get('email_priemcu', 'bo.specialisti@prohypo.sk')}'>"
    content += f"Meno klienta:<input name='meno_klienta' value='{form_data['meno_klienta']}' required>"
    content += f"Číslo zmluvy:<input name='cislo_zmluvy' value='{form_data['cislo_zmluvy']}' required>"
    content += "Typ zmluvy:<select name='typ_zmluvy' required>"
    content += f"<option value='nehnuteľnosť' {'selected' if form_data['typ_zmluvy']=='nehnuteľnosť' else ''}>nehnuteľnosť</option>"
    content += f"<option value='auto' {'selected' if form_data['typ_zmluvy']=='auto' else ''}>auto</option>"
    content += f"<option value='investície' {'selected' if form_data['typ_zmluvy']=='investície' else ''}>investície</option>"
    content += f"<option value='leasing' {'selected' if form_data['typ_zmluvy']=='leasing' else ''}>leasing</option>"
    content += f"<option value='životka' {'selected' if form_data['typ_zmluvy']=='životka' else ''}>životka</option>"
    content += f"<option value='podnikatelia' {'selected' if form_data['typ_zmluvy']=='podnikatelia' else ''}>podnikatelia</option>"
    content += "</select>"
    content += f"Vinkulácia:<label><input type='checkbox' name='vinkulacia' {form_data['vinkulacia']}></label>"
    content += f"SLSP:<label><input type='checkbox' name='slsp' {form_data['slsp']}></label>"
    content += f"Prioritné:<label><input type='checkbox' name='prioritne' {form_data['prioritne']}></label>"
    content += f"Dátum spracovania - banka:<input name='datum_spracovania' value='{form_data['datum_spracovania']}'>"
    content += f"Záznam:<label><input type='checkbox' name='zaznam' {form_data['zaznam']}></label>"
    content += f"PCA:<label><input type='checkbox' name='pca' {form_data['pca']}></label>"
    content += "Delenie provízie:<select name='delenie_provizie'>"
    content += f"<option value='Žiadne delenie' {'selected' if form_data['delenie_provizie']=='Žiadne delenie' else ''}>Žiadne delenie</option>"
    content += f"<option value='Bruno' {'selected' if form_data['delenie_provizie']=='Bruno' else ''}>Bruno</option>"
    content += f"<option value='Kriška' {'selected' if form_data['delenie_provizie']=='Kriška' else ''}>Kriška</option>"
    content += f"<option value='Kšenzo' {'selected' if form_data['delenie_provizie']=='Kšenzo' else ''}>Kšenzo</option>"
    content += f"<option value='Fio' {'selected' if form_data['delenie_provizie']=='Fio' else ''}>Fio</option>"
    content += f"<option value='Miško' {'selected' if form_data['delenie_provizie']=='Miško' else ''}>Miško</option>"
    content += f"<option value='Naty' {'selected' if form_data['delenie_provizie']=='Naty' else ''}>Naty</option>"
    content += f"<option value='Finax - poslať Nadi !' {'selected' if form_data['delenie_provizie']=='Finax' else ''}>Finax</option>"
    content += "</select>"
    content += f"Iné:<input name='ine' value='{form_data['ine']}'>"
    content += f"Poznámky:<textarea name='poznamky'>{form_data['poznamky']}</textarea>"
    content += "<button class='btn' type='submit'>Vygenerovať</button>"
    content += "</form>"
    content += "</div>"
    content += result_block
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/najcastejsie_otazky")
@login_required
def najcastejsie_otazky():
    faq_items = load_faq_items()
    if not faq_items:
        flash("Súbor otázok je prázdny alebo chýba.")
        content = "<h2>Najčastejšie otázky</h2><p>Zatiaľ nie sú dostupné žiadne otázky.</p>"
        return render_template_string(APP_TEMPLATE, content=content)

    groups = {}
    for item in faq_items:
        groups.setdefault(item["sekcia"], []).append(item)

    nadine_links = {
        "Vinkulácie": "https://docs.google.com/spreadsheets/d/1sM415O7Mcw9x9dlFe9MYvXNRn-sjHiE8/edit?gid=508251846#gid=508251846"
    }

    content = "<h2>Najčastejšie otázky</h2>"
    for sekcia, items in groups.items():
        content += f"<div class='faq-group'><h3>{sekcia}</h3>"
        for item in items:
            answer_html = linkify_text(item["odpoved"])
            content += "<div class='faq-item'>"
            content += f"<button type='button' class='faq-question' onclick='toggleFaqAnswer(this)'>{item['otazka']}</button>"
            content += f"<div class='faq-answer'>{answer_html}"
            if sekcia == "Nadine linky" and item["otazka"] == "Na ktorom linku, čo nájdem?":
                content += "<div class='faq-links' style='margin-top:10px;'>"
                for title, url in nadine_links.items():
                    content += (
                        f"<a class='btn' href='{url}' target='_blank' rel='noopener noreferrer'>{title}</a>"
                    )
                content += "</div>"
            content += "</div>"
            content += "</div>"
        content += "</div>"

    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/zaujimave_cisla")
@login_required
def zaujimave_cisla():
    items = load_interesting_numbers()
    if not items:
        flash("Súbor zaujímavých čísel je prázdny alebo chýba.")
        content = "<h2>Zaujímavé čísla</h2><p>Zatiaľ nie sú dostupné žiadne údaje.</p>"
        return render_template_string(APP_TEMPLATE, content=content)

    groups = {}
    for item in items:
        groups.setdefault(item["sekcia"], []).append(item)

    content = "<h2>Zaujímavé čísla</h2>"
    for sekcia, section_items in groups.items():
        content += f"<div class='faq-group'><h3>{sekcia}</h3>"
        for item in section_items:
            content += "<div class='faq-item'>"
            content += f"<button type='button' class='faq-question' onclick='toggleFaqAnswer(this)'>{item['otazka']}</button>"
            content += f"<div class='faq-answer'>{item['odpoved']}</div>"
            content += "</div>"
        content += "</div>"

    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/hypo", methods=["GET"])
@login_required
def hypo():
    content = """
    <h2>Hypotekárna kalkulačka - Hypo VS Poistná suma</h2>
    <div style="display:flex;gap:20px;align-items:flex-start;">
      <div style="width:300px;">
        <div class="card" style="padding:16px;">
          <h4 style="margin-top:0;">Vstupné údaje</h4>
          <label><strong>Výška úveru (€)</strong></label>
          <input type="number" id="loan_amount" value="Zadaj výšku úveru" step="1000">
          <label><strong>Ročná úroková sadzba (%)</strong></label>
          <input type="number" id="annual_rate" value="3.8" step="0.1">
          <label><strong>Doba splácania (roky)</strong></label>
          <input type="number" id="years" value="30" step="1">
          <label><strong>Dátum prvej splátky</strong></label>
          <input type="date" id="first_payment">
          <hr style="margin:16px 0;">
          <h4 style="margin-top:0;">Parametre poistenia</h4>
          <label><strong>Poistná suma (€)</strong></label>
          <input type="number" id="insurance_sum" value="200000" step="1000">
          <label><strong>Poistná doba (roky)</strong></label>
          <input type="number" id="insurance_years" value="30" step="1">
          <label><strong>Navýšenie PS (%)</strong></label>
          <input type="number" id="increase_pct" value="0" step="0.1">
          <label><strong>Konštantná poistná suma (€)</strong></label>
          <input type="number" id="constant_insurance" value="0" step="1">
          <div style="margin-top:16px;">
            <button class="btn" onclick="runHypoCalc()" style="width:100%;padding:12px;">Vypočítať</button>
          </div>
        </div>
      </div>

      <div style="flex:1;">
        <div id="hypo_alerts" style="margin-bottom:16px;"></div>
        
        <div id="hypo_results" style="display:none;">
          <div class="card" style="padding:16px;margin-bottom:16px;">
            <div style="display:flex;gap:16px;align-items:center;justify-content:space-around;">
              <div style="text-align:center;padding:12px;">
                <div style="font-size:0.85rem;color:#666;">Výška úverového zostatku</div>
                <div id="summary_balance" style="font-weight:700;font-size:1.4rem;color:#0066cc;">—</div>
              </div>
              <div style="text-align:center;padding:12px;">
                <div style="font-size:0.85rem;color:#666;">Poistná suma pôvodná</div>
                <div id="summary_insurance" style="font-weight:700;font-size:1.4rem;color:#0066cc;">—</div>
              </div>
              <div style="text-align:center;padding:12px;">
                <div style="font-size:0.85rem;color:#666;">Podpoistenie</div>
                <div id="summary_diff" style="font-weight:700;font-size:1.4rem;color:#c00;">—</div>
              </div>
            </div>
          </div>

          <div class="card" style="padding:16px;margin-bottom:16px;">
            <h4 style="margin-top:0;">Graf splátok a poistenia</h4>
          <canvas id="hypo_chart" height="180"></canvas>
          <div class="card" style="padding:16px;">
            <h4 style="margin-top:0;">Tabuľka splátok (prvých 50 mesiacov)</h4>
            <div style="max-height:300px;overflow-y:auto;border:1px solid #eee;border-radius:4px;">
              <table style="width:100%;font-size:0.85rem;border-collapse:collapse;">
                <thead style="background:#f5f5f5;position:sticky;top:0;">
                  <tr>
                    <th style="padding:8px;text-align:left;border-bottom:1px solid #ddd;">Mesiac</th>
                    <th style="padding:8px;text-align:right;border-bottom:1px solid #ddd;">Splátka</th>
                    <th style="padding:8px;text-align:right;border-bottom:1px solid #ddd;">Úrok</th>
                    <th style="padding:8px;text-align:right;border-bottom:1px solid #ddd;">Zostatok</th>
                    <th style="padding:8px;text-align:right;border-bottom:1px solid #ddd;">Poistenie</th>
                    <th style="padding:8px;text-align:right;border-bottom:1px solid #ddd;">Rozdiel</th>
                  </tr>
                </thead>
                <tbody id="hypo_table_body"></tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
      let hypoChart = null;
      
      function fmt(val) {
        return Number(val).toLocaleString('sk-SK', {style: 'currency', currency: 'EUR'});
      }

      async function runHypoCalc() {
        const payload = {
          loan_amount: parseFloat(document.getElementById('loan_amount').value || 0),
          annual_rate: parseFloat(document.getElementById('annual_rate').value || 0),
          years: parseInt(document.getElementById('years').value || 0),
          first_payment: document.getElementById('first_payment').value || new Date().toISOString().slice(0, 10),
          insurance_sum: parseFloat(document.getElementById('insurance_sum').value || 0),
          insurance_years: parseInt(document.getElementById('insurance_years').value || 0),
            increase_pct: parseFloat(document.getElementById('increase_pct').value || 0),
            constant_insurance: parseFloat(document.getElementById('constant_insurance').value || 0),
        };

        try {
          const res = await fetch('/hypo/calc', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
          });

          if (!res.ok) {
            const err = await res.json();
            document.getElementById('hypo_alerts').innerHTML = '<div class="error" style="padding:12px;background:#ffecec;border:1px solid #f5c2c7;border-radius:4px;color:#842029;">⚠️ Chyba: ' + (err.error || 'Neznáma chyba') + '</div>';
            return;
          }

          const data = await res.json();
          renderHypoResults(data);
        } catch (e) {
          document.getElementById('hypo_alerts').innerHTML = '<div class="error" style="padding:12px;background:#ffecec;border:1px solid #f5c2c7;border-radius:4px;color:#842029;">⚠️ Chyba pripojenia: ' + e.message + '</div>';
        }
      }

      function renderHypoResults(data) {
        // Show results section
        document.getElementById('hypo_results').style.display = 'block';
        
        // Summary cards
        const last = data.schedule[data.schedule.length - 1];
        document.getElementById('summary_balance').innerText = fmt(data.schedule[0].balance);
        document.getElementById('summary_insurance').innerText = fmt(data.schedule[0].insurance);
        
        const diffs = data.schedule.map(r => r.difference);
        const negDiffs = diffs.filter(d => d < 0).map(d => Math.abs(d));
        const maxUnder = negDiffs.length ? Math.max(...negDiffs) : 0;
        document.getElementById('summary_diff').innerText = maxUnder > 0 ? '-' + fmt(maxUnder) : '—';

        // Alerts
        const alerts = document.getElementById('hypo_alerts');
        if (maxUnder > 0) {
          const minIdx = diffs.findIndex(v => v < 0);
          const minDate = data.schedule[minIdx] ? data.schedule[minIdx].date : '—';
          let msg = `Klient je poistený pod potrebu úverového zostatku. Maximálne "podpoistenie" je ${fmt(maxUnder)} (mesiac ${minDate}).`;
          if (data.optimized && data.optimized.required_initial) {
            const recommend = Math.max(0, data.optimized.required_initial - data.schedule[0].insurance);
            msg += ` Odporúčame navýšiť PS o ${fmt(recommend)}, alebo nastaviť počiatočnú PS na ${fmt(data.optimized.required_initial)}.`;
          }
          alerts.innerHTML = '<div style="padding:12px;background:#fff2f2;border:1px solid #f5c2c7;border-radius:4px;color:#842029;">⚠️ ' + msg + '</div>';
        } else {
          alerts.innerHTML = '<div style="padding:12px;background:#ecffef;border:1px solid #c7f5d6;border-radius:4px;color:#0f5132;">✅ Poistenie pokrýva zostatok úveru počas celej doby.</div>';
        }

        // Chart
        const labels = data.schedule.map(r => r.date);
        const balance = data.schedule.map(r => r.balance);
        const insurance = data.schedule.map(r => r.insurance);
        const constantSeries = data.schedule.map(r => r.constant_insurance || 0);
        const insuranceTotal = data.schedule.map(r => r.insurance_total || r.insurance + (r.constant_insurance||0));
        let optimized = null;
        if (data.optimized && data.optimized.required_initial) {
          const init = data.optimized.required_initial;
          const n = data.schedule.length;
          optimized = Array.from({length: n}, (_, i) => Math.round(init * Math.max(0, 1 - i/n) * 100) / 100);
        }

        const ctx = document.getElementById('hypo_chart').getContext('2d');
        if (hypoChart) hypoChart.destroy();
        hypoChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels,
            datasets: [
              {
                label: 'Zostatok úveru',
                data: balance,
                borderColor: '#c00',
                tension: 0.2,
                fill: false,
                pointRadius: 0
              },
              {
                label: 'Poistná suma (pôvodná)',
                data: insurance,
                borderColor: '#0066cc',
                tension: 0.2,
                fill: false,
                pointRadius: 0
              },
              {
                label: 'Konštantná poistná suma',
                data: constantSeries,
                borderColor: '#ffa500',
                borderDash: [5,3],
                tension: 0.2,
                fill: false,
                pointRadius: 0
              },
              {
                label: 'Poistná suma (celková)',
                data: insuranceTotal,
                borderColor: '#0080ff',
                backgroundColor: 'rgba(0,128,255,0.06)',
                fill: true,
                pointRadius: 0,
                tension: 0.2
              },
              ...(optimized ? [{
                label: 'PS optimalizovaná',
                data: optimized,
                borderColor: '#008000',
                tension: 0.2,
                fill: false,
                pointRadius: 0
              }] : [])
            ]
          },
          options: {
            responsive: true,
            interaction: {mode: 'index', intersect: false},
            plugins: {
              legend: {position: 'top'},
              tooltip: {callbacks: {label: ctx => ctx.dataset.label + ': ' + fmt(ctx.parsed.y)}}
            },
            scales: {
              y: {ticks: {callback: v => fmt(v)}}
            }
          }
        });

        // Table
        const tbody = document.getElementById('hypo_table_body');
        tbody.innerHTML = '';
        data.schedule.slice(0, 50).forEach(row => {
          const tr = document.createElement('tr');
          if (row.difference < 0) tr.style.background = '#ffecec';
          tr.innerHTML = `
            <td style="padding:6px;border-bottom:1px solid #eee;">${row.month}</td>
            <td style="padding:6px;border-bottom:1px solid #eee;text-align:right;">${fmt(row.payment)}</td>
            <td style="padding:6px;border-bottom:1px solid #eee;text-align:right;">${fmt(row.interest)}</td>
            <td style="padding:6px;border-bottom:1px solid #eee;text-align:right;">${fmt(row.balance)}</td>
            <td style="padding:6px;border-bottom:1px solid #eee;text-align:right;">${fmt(row.insurance)}</td>
            <td style="padding:6px;border-bottom:1px solid #eee;text-align:right;color:${row.difference < 0 ? '#c00' : '#008000'};">${fmt(row.difference)}</td>
          `;
          tbody.appendChild(tr);
        });
      }

      // Set default date
      document.addEventListener('DOMContentLoaded', () => {
        const el = document.getElementById('first_payment');
        if (!el.value) {
          el.value = new Date().toISOString().slice(0, 10);
        }
      });
    </script>
  """
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/rzp", methods=["GET"])
@login_required
def rzp():
  insurers = [
    {"slug": "allianz", "brand": "Allianz", "product": "Šťastný život", "sub": "Slovenská poisťovňa"},
    {"slug": "csob", "brand": "ČSOB", "product": "VITAL", "sub": ""},
    {"slug": "generali", "brand": "GENERALI", "product": "La Vita", "sub": ""},
    {"slug": "kooperativa", "brand": "Kooperativa", "product": "Bezstarostný život", "sub": "Vienna Insurance Group"},
    {"slug": "nn", "brand": "NN", "product": "NN Partner", "sub": ""},
    {"slug": "uniqa", "brand": "UNIQA", "product": "Život a radosť", "sub": ""},
    {"slug": "wdobrom", "brand": "wustenrot", "product": "W Dobrom", "sub": ""},
    {"slug": "4u", "brand": "U+", "product": "4U", "sub": "youpuls"},
  ]

  insurer_colors = {
    "allianz": "#1f3f95",
    "csob": "#0b4f9c",
    "generali": "#d9271c",
    "kooperativa": "#b30000",
    "nn": "#f28c00",
    "uniqa": "#0d67b2",
    "wdobrom": "#c00000",
    "4u": "#e85d10",
  }

  row_groups = [
    {
      "title": "Všeobecné",
      "rows": [
        ("min. poistné", {
          "allianz": "25€ za produkt",
          "csob": "5€/mes.",
          "generali": "15€/mes.",
          "kooperativa": "20€/mes.",
          "nn": "20€/mes.",
          "uniqa": "nie je",
          "wdobrom": "10€/mes.",
          "4u": "nie je",
        }),
        ("max. počet poistených na zmluve", {
          "allianz": "6",
          "csob": "9",
          "generali": "6",
          "kooperativa": "1+4",
          "nn": "7",
          "uniqa": "8 dospelých + deti neobmedzene",
          "wdobrom": "5",
          "4u": "10",
        }),
        ("min. vstupný vek", {
          "allianz": "2 týždne",
          "csob": "2 týždne",
          "generali": "2 týždne",
          "kooperativa": "15/18",
          "nn": "6 týždňov",
          "uniqa": "0",
          "wdobrom": "15/0",
          "4u": "6 týž. dieťa/16r. dospelý",
        }),
        ("max. vstupný vek", {
          "allianz": "70",
          "csob": "75",
          "generali": "65/70",
          "kooperativa": "75",
          "nn": "75",
          "uniqa": "75",
          "wdobrom": "70",
          "4u": "15r. dieťa/65r. dospelý",
        }),
        ("výstupný vek", {
          "allianz": "85",
          "csob": "80",
          "generali": "75",
          "kooperativa": "85",
          "nn": "80",
          "uniqa": "80",
          "wdobrom": "75",
          "4u": "26r. dieťa/80r. dospelý",
        }),
        ("asistenčné služby", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "nie",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "nie",
        }),
        ("začiatok poistenia (min.)", {
          "allianz": "1 deň po podpise",
          "csob": "1 deň po podpise",
          "generali": "1 deň po podpise",
          "kooperativa": "1 deň po podpise",
          "nn": "1. deň nasl. mesiaca po podpise",
          "uniqa": "1. deň po podpise",
          "wdobrom": "1. deň nasl. mesiaca po podpise",
          "4u": "1. deň po podpise",
        }),
        ("začiatok poistenia (max.)", {
          "allianz": "2 mesiace po podpise",
          "csob": "2 mesiace po podpise",
          "generali": "2 mesiace po podpise",
          "kooperativa": "posledný deň v mesiaci po podpise",
          "nn": "k 1. dňu nasl. mesiaca po podpise",
          "uniqa": "3 mesiace po podpise",
          "wdobrom": "k 1. dňu 2. mesiaca po podpise",
          "4u": "3 mesiace po podpise",
        }),
      ],
    },
    {
      "title": "Poistenie bez skúmania zdravotného stavu",
      "rows": [
        ("poistenie bez skúmania zdravot.stavu", {
          "allianz": "S - 300€ SNÚ - 100 000€ SNÚ(d) - 2 000€ TNÚ - 20 000€ TNÚ700(d) - 7 000€ INV(úraz) - 20 000€ DNL - 10€ DNL(d) - 3€ HNÚ - 10€ HNÚ(d) - 5€",
          "csob": "S - 300-700€ (v závislosti od vstupného veku klienta) SNÚ - 40 000€ TNÚ750% - 20 000€ INV(úraz) - 30 000€ DNL - 5€ DNL(zrýchlené plnenie) - 10€ H(úraz) - 30€",
          "generali": "S - 2000€ S(d) - 500€ SNÚ - 100 000€ SNÚ(d) - 1 500€ TNÚ1000% - 50 000€ INV(úraz) - 10 000€ DVÚ - 10€ DVÚ(d) - 10€ DNL - 10€ HNÚ - 10€ RAK - 20 000€ RAK(d) - 10 000€",
          "nn": "S - 2 400€ SNÚ - 50 000€ pri autonehode TNÚ1000% - 5 000€ DNL - 10€",
          "uniqa": "S - 2 000€ SNÚ - 80 000€ TNÚ(lineárne) - 80 000€ TNÚ1000% - 16 000€ TNÚ1000% - 8 000€ DNL - 8€<br>H - 8€",
          "wdobrom": "S, KLS(S+KLS) - 5 000€ SNÚ - 50 000€ TNÚ800% - 50 000€ INV(IVK+IVKL) - 2 000€ DNL - 10€",
          "4u": "áno (vybrané úrazové riziká)",
        }),
        ("min. PS pri hl.tarife", {
          "allianz": "300€",
          "csob": "700€",
          "generali": "330€",
          "kooperativa": "1 000 €",
          "nn": "400€",
          "uniqa": "2 000€",
          "wdobrom": "1 000 €",
          "4u": "200€",
        }),
        ("max. PS pri hl.tarife", {
          "allianz": "fixná",
          "csob": "fixná",
          "generali": "500 000€",
          "kooperativa": "závisí od príjmu klienta",
          "nn": "fixná",
          "uniqa": "nie je stanovená",
          "wdobrom": "199 000 €",
          "4u": "fixná",
        }),
      ],
    },
  
    {
      "title": "Zľavy",
      "rows": [
        ("zľava za počet pripostení", {
          "allianz": "áno",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("zľava za výšku poistného", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno (až do 45%)",
          "4u": "áno (max. 35%) + 5% za darovanie krvi",
        }),
        ("zľava nefajčiar", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "áno",
          "wdobrom": "nie",
          "4u": "áno",
        }),
        ("zľava za BMI", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "áno",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("zľava za viac zmlúv", {
          "allianz": "nie",
          "csob": "áno",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "áno",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("zľava za e-komunikáciu", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("úverová zľava (zľava za veľké riziká)", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "áno",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("zľava za výšku PS", {
          "allianz": "nie",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "áno",
          "nn": "nie",
          "uniqa": "áno",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("zľava za frekvenciu platenia", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "áno",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
      ],
    },
  ]

  risk_groups = [
    {
      "title": "Kritické choroby (súhrn)",
      "rows": [
        ("doba prežitia (v dňoch)", {
          "allianz": "15",
          "csob": "30/0 (pre vybrané dg.)",
          "generali": "15 (pre vybrané dg.)",
          "kooperativa": "30",
          "nn": "0",
          "uniqa": "0",
          "wdobrom": "0",
          "4u": "0 (balík PLUS)",
        }),
        ("max. plnenie v %", {
          "allianz": "600% (balík Platinum)",
          "csob": "300%",
          "generali": "500%",
          "kooperativa": "100%",
          "nn": "100% pre každú skupinu / 150% pri terminálnom štádiu / 740% celkovo",
          "uniqa": "600%",
          "wdobrom": "190%",
          "4u": "600% (balík PLUS)",
        }),
        ("rakovina in-situ", {
          "allianz": "30% (balík Gold a Platinum)",
          "csob": "20%",
          "generali": "25%",
          "kooperativa": "50% (iba na 1. PU)",
          "nn": "30%",
          "uniqa": "25%",
          "wdobrom": "20%",
          "4u": "20% (balík PLUS)",
        }),
        ("max. počet dg. v balíku", {
          "allianz": "70 (balík Platinum)",
          "csob": "55",
          "generali": "65",
          "kooperativa": "40",
          "nn": "69",
          "uniqa": "neuvádzajú",
          "wdobrom": "38",
          "4u": "47",
        }),
        ("čakacia doba (v mes.)", {
          "allianz": "3",
          "csob": "3",
          "generali": "2",
          "kooperativa": "0",
          "nn": "0 mes. / 3 mes. na vybraných 5 diagnóz / 6 mes. pre ďalšiu PU medzi skupinami",
          "uniqa": "0",
          "wdobrom": "0",
          "4u": "2",
        }),
      ],
    },
    {
      "title": "Smrť",
      "rows": [
        ("extrémne športy", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "áno",
          "kooperativa": "áno - vybrané",
          "nn": "áno",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "áno (jednorazové aktivity, v iných prípadoch individuálny úpis)",
        }),
        ("samovražda/čakacia doba", {
          "allianz": "áno/2roky",
          "csob": "áno/2roky",
          "generali": "áno/2roky",
          "kooperativa": "áno/2roky",
          "nn": "áno/2roky",
          "uniqa": "áno/12 mesiacov",
          "wdobrom": "áno/2roky",
          "4u": "áno/2roky",
        }),
        ("alkohol/krátenie", {
          "allianz": "max. 50% / v prípade ťažkého stupňa opitosti (od 2,01 promile) až do 99%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "od 0,51‰ do 0,99‰ = 20%\nod 1,0‰ do 1,49‰ = 30%\nod 1,50‰ do 1,99‰ = 40%\nmax. 50% (od 2‰)",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("hypo-poistenie", {
          "allianz": "KLS/INV(40/70)/KCH",
          "csob": "nie",
          "generali": "KLS/INV(40/70)/KCH",
          "kooperativa": "nie",
          "nn": "KLS/INV(40/70)",
          "uniqa": "KLS/INV(40/70)/KCH",
          "wdobrom": "KLS/INV(40/70)/KCH",
          "4u": "KLS/INV(40/55/70)/KCH",
        }),
      ],
    },
    {
      "title": "Invalidita (choroba / úraz)",
      "rows": [
        ("40/70", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "áno",
        }),
        ("územná platnosť", {
          "allianz": "Európa, EHP, Švajčiarsko, Veľká Británia",
          "csob": "SR",
          "generali": "SR",
          "kooperativa": "Európa",
          "nn": "SR",
          "uniqa": "Svet",
          "wdobrom": "SR",
          "4u": "Svet",
        }),
        ("čakacia doba (v mes.)", {
          "allianz": "2",
          "csob": "12",
          "generali": "2",
          "kooperativa": "0 - pri konšt. PS / 24 - pri kles. PS",
          "nn": "0",
          "uniqa": "0",
          "wdobrom": "0",
          "4u": "2",
        }),
        ("psych. ochorenia", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "nie",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "áno",
        }),
        ("typ výplaty plnenia", {
          "allianz": "JV(KS/KLS)/Renta",
          "csob": "JV/renta",
          "generali": "JV/renta",
          "kooperativa": "JV/renta",
          "nn": "JV/renta",
          "uniqa": "JV(KS/KLS)/Renta",
          "wdobrom": "JV(KS/KLS) nad 40%/70%, Renta nad 70%, Oslob. od platenia nad 70%",
          "4u": "JV(KS/KLS)/Renta",
        }),
        ("dokladovanie", {
          "allianz": "Právoplatné rozhodnutie príslušného orgánu o priznaní invalidity.\nAkceptuje aj doklady orgánov uvedených krajín v územnej platnosti",
          "csob": "rozhodnutie SP",
          "generali": "rozhodnutie SP",
          "kooperativa": "rozhodnutie SP",
          "nn": "rozhodnutie SP",
          "uniqa": "Právoplatné rozhodnutie príslušného orgánu o priznaní invalidity, lekársky posudok o invalidite",
          "wdobrom": "rozhodnutie SP",
          "4u": "Posudok o invalidite vydaný SP, alebo vlastné šetrenie poisťovne na základe doložených LS",
        }),
      ],
    },
    {
      "title": "Kritické choroby",
      "rows": [
        ("AIDS/HIV (pri výkone povolania/následkom transfúzie)", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Alzheimerova choroba", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100% - posledné štádium\n50% - stredné štádium\n25% - počiatočné štádium",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - vážny rozsah (nesebestačnosť 5 a viac funkcií bež. života)\n25% - mierny rozsah (stačí stanovenie dg.)",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Amputácia, strata končatín", {
          "allianz": "100% (nad lakťom / kolenom)",
          "csob": "nie",
          "generali": "100% (nad zápästím / členkom)",
          "kooperativa": "nie",
          "nn": "100% (nad zápästím / členkom)",
          "uniqa": "100% - amputácia aspoň 2 končatín (nad zápästím/členkom)\n50% - amputácia 1 končatiny (nad zápästím/členkom)",
          "wdobrom": "100% (nad lakťom / kolenom)",
          "4u": "100% (nad zápästím / členkom)",
        }),
        ("Amyotrofická laterálna skleróza (ALS)", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Angioplastika", {
          "allianz": "100% - 3 a viac tepien (balík gold a platinum)\n30% - 1 až 2 tepny (balík gold a platinum)",
          "csob": "20%",
          "generali": "25%",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "10% - neakútne katet. ošetrenie vencovitej cievy alebo inej tepny\n25% - katet. ošetrenie vencovitej cievy pri Angine pectoris",
          "wdobrom": "nie",
          "4u": "50% (max 15 000 €)",
        }),
        ("Apalický syndróm (odumretie i mozgovej kôry)", {
          "allianz": "100%",
          "csob": "nie",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Aplastická anémia", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Astma", {
          "allianz": "nie",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Autizmus", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "100%",
          "4u": "nie",
        }),
        ("Bechtereva choroba (zápalové ochorenie chrbtice)", {
          "allianz": "100%",
          "csob": "nie",
          "generali": "100%",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Brušný týfus", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("By-pass (chirurgia koronárnych venc. tepien)", {
          "allianz": "100% - otvorený hrudník / 60% - 3 a viac tepien (balík gold a platinum) / 30% - 1 až 2 tepny (balík gold a platinum)",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - otvorená hrudná kosť (sternotómia) / 50% - otvorená hrudná dutina (thorakotómia) / 25% - katet. ošetrenie vencovitej cievy pri Angine pectoris / 10% - neakútne katet. ošetrenie vencovitej cievy alebo inej tepny",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Celiakia", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "10%",
          "4u": "nie",
        }),
        ("Cievna mozgová príhoda", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100% - vážne následky\n50% - stredné následky\n25% - mierne následky",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% s následkami po 3 mes.\n25% bez následkov po 3 mes.",
          "wdobrom": "100%",
          "4u": "100% s trvalými následkami / 50% následky 3 m",
        }),
        ("Creutzfeldt-Jacobova choroba", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "nie",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Crohnova choroba", {
          "allianz": "100%",
          "csob": "nie",
          "generali": "50%",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "100% - vážny rozsah (komplikácie vyžadujúce chirurg.zákrok)\n25% - mierny rozsah (stačí stanovenie dg.)",
          "wdobrom": "30%",
          "4u": "50%/100% s resekciou čreva",
        }),
        ("Cukrovka (Diabetes mellitus I. typu)", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "30%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "nie",
        }),
        ("Cystická fibróza", {
          "allianz": "nie",
          "csob": "100%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Demencia", {
          "allianz": "100% - absencia 9 bežných činností / 60% - absencia 7 bežných činností (balík gold a platinum) / 30% - absencia 5 bežných činností (balík gold a platinum)",
          "csob": "100%",
          "generali": "nie",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - vážny rozsah (nesebestačnosť 5 a viac funkcií bež. života)\n25% - mierny rozsah (stačí stanovenie dg.)",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Dermatóza Pemfigus", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Ebola", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Encefalitída (kliešťová, bakteriálna, vírusová)", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100% (iba herpetická)",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Encefalitída-Polio myelitická (detská obrna)", {
          "allianz": "nie",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "nie",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Epilepsia", {
          "allianz": "100%",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "100%",
          "nn": "30%",
          "uniqa": "100%",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Hluchota (obojstranná, choroba/úraz)", {
          "allianz": "100% - veľký rozsah / 60% - stredný rozsah (balík gold a platinum) / 30% - mierny rozsah (balík gold a platinum)",
          "csob": "100%",
          "generali": "100% - vážny rozsah / 50% - stredný rozsah / 25% - mierny rozsah",
          "kooperativa": "100%",
          "nn": "100% (iba choroba)",
          "uniqa": "100% - úplná strata sluchu oboch uší\n50% - výrazné strata sluchu oboch uší\n25% - strata sluchu na jednom uchu",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Horúčka Dengue", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Cholera", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Kawasakihov choroba", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Kóma", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Lymská borelióza", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "10%",
          "uniqa": "10%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Malária", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "10%",
          "4u": "nie",
        }),
        ("Meningitída bakteriálna", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Meningitída vírusová", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "nie",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "nie",
        }),
        ("Narkolepsia", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Nezhubný nádor mozgu", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Ochrnutie (obrna, paralýza)", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Ochrnutie končatín (paraplégia, kvadruplégia, diplegia, hemiplégia)", {
          "allianz": "100% kvadruplégia / 60% - paraplégia, hemiplégia (balík gold a platinum) / 30% monoplégia (balík gold a platinum)",
          "csob": "100%",
          "generali": "100% - úplné ochrnutie 2,3,4 končatín\n50% - úplné ochrnutie 1 končatiny alebo čiastočné ochrnutie (paréza) 3,4 končatín\n25% - paréza 2 končatín",
          "kooperativa": "100%",
          "nn": "100% / 150% kvadruplégia",
          "uniqa": "100% - úplné ochrnutie aspoň 2 končatín\n50% - úplné ochrnutie 1 končatiny / čiastočné ochrnutie (paréza) aspoň 2 končatín",
          "wdobrom": "100% (okrem hemiplégie)",
          "4u": "100%",
        }),
        ("Omrzlina s nekrotizou tkaniva", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Operácia aorty", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Operácia srdcovej chlopne", {
          "allianz": "100% / 30% - katetrizačná (balík gold a platinum)",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100% (výmena srdcovej chlopne)",
          "nn": "100%",
          "uniqa": "100% / 50% - katetrizačná technika",
          "wdobrom": "100% (výmena srdcovej chlopne)",
          "4u": "100% / 50% - katetrizačná (max 15 000 €)",
        }),
        ("Parkinsonova choroba", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100% - vážneho rozsahu\n50% - stredného rozsahu",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - vážny rozsah (nesebestačnosť 5 a viac funkcií bež. života)\n25% - mierny rozsah (stačí stanovenie dg.)",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Pľúcna fibróza", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Pľúcna hypertenzia", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "nie",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Popáleniny (ťažké)", {
          "allianz": "nie",
          "csob": "100% (3. stupeň, 20% tela)",
          "generali": "100% (3. stupeň, 20% povrchu tela / 25% povrchu tváre / 50% povrchu hlavy)",
          "kooperativa": "100% (3. stupeň, 30% tela)",
          "nn": "50%",
          "uniqa": "nie",
          "wdobrom": "100% (3. stupeň, 20% tela)",
          "4u": "100% (3. stupeň, 20% tela)",
        }),
        ("Rakovina", {
          "allianz": "100% / 200% - vybrané dg. max. do 190 000€ (balík platinum)",
          "csob": "100%",
          "generali": "100% / 50% vybrané typy mierneho rozsahu: Ca prostaty T1N0M0, papilárny/folikulárny/modulárny Ca štítnej žľazy T1N0M0, melanóm kože T1N0M0, Ca moč. mechúra (neinvazívny, papilárny), chronická lymfat. leukémia - Binet A, Ca kože (spinocelulárny), nádory ovárií (border line), paraganglióm, feochromocytóm",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100% / 20% menej pokročilé štádia (max 20 000 €)",
        }),
        ("Rakovina in-situ", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "20%",
          "generali": "25% (zahŕňa aj 1. štádium Hodgkinovej choroby)",
          "kooperativa": "50%",
          "nn": "30%",
          "uniqa": "25% (zahŕňa aj kožný lymfóm, melanóm in situ aj T1N0M0, spinalióm, karcinóm in situ močového mechúra a neinvazívny papilárny karcinóm močového mechúra)",
          "wdobrom": "20%",
          "4u": "20% (max 20 000 €)",
        }),
        ("Reumatická horúčka", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Reumatoidná artritída", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Schistosomóza", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Skleróza multiplex", {
          "allianz": "100% - veľký rozsah / 60% - stredný rozsah (balík gold a platinum) / 30% - mierny rozsah (balík gold a platinum)",
          "csob": "100%",
          "generali": "100% - vážny rozsah / 50% - stredný rozsah / 25% - mierny rozsah",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - vážny rozsah 50% - stredný rozsah 25% - mierny rozsah",
          "wdobrom": "100%",
          "4u": "100% / 50% roztrúsená skleróza",
        }),
        ("Slepota (obidvoch očí, choroba/úraz)", {
          "allianz": "100% - veľký rozsah / 60% - stredný rozsah (balík gold a platinum) / 30% - mierny rozsah (balík gold a platinum)",
          "csob": "100%",
          "generali": "100% - vážny rozsah / 50% - stredný rozsah / 25% - mierny rozsah",
          "kooperativa": "100%",
          "nn": "100% (iba choroba)",
          "uniqa": "100% - úplná strata zraku oboch očí\n50% - výrazné zhoršenie zraku oboch očí\n25% - strata zraku na jednom oku",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Srdcový infarkt (akútny infarkt myokardu)", {
          "allianz": "100% / 30% pri NSTEMI (balík gold a platinum)",
          "csob": "100%",
          "generali": "100% / 100% aj pri type NSTEMI",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - vážny rozsah / 50% - stredný rozsah / 25% - mierny rozsah",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Strata končatín z dôvodu choroby", {
          "allianz": "100%",
          "csob": "nie",
          "generali": "100% - viacerých končatín\n50% - jednej končatiny",
          "kooperativa": "nie",
          "nn": "100%",
          "uniqa": "100% - úplná strata aspoň 2 končatín\n50% - úplná strata 1 končatiny\n25% - čiastočná strata 1 končatiny",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Strata reči (choroba/úraz)", {
          "allianz": "100%",
          "csob": "20%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100% (iba choroba)",
          "uniqa": "nie",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Svalová dystrofia/atrofia", {
          "allianz": "100% (atrofia)",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "30%",
          "uniqa": "100%",
          "wdobrom": "100% (dystrofia)",
          "4u": "nie",
        }),
        ("Systémová progresívna sklerodermia", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Systémový lupus s postihnutím obličiek", {
          "allianz": "100%",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "100%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Terminálne štádium choroby", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "nie",
          "kooperativa": "100%",
          "nn": "150% (diagnózy v zmysle VPP)",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Tetanus", {
          "allianz": "nie",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100% (4 t hosp. + 72 h pľúcna ventilácia)",
        }),
        ("Transplantácia životne dôležitých orgánov", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100% - srdce, pľúca, pečeň, obličky, podžalúdková žľaza, kostná dreň (už pri zaradení na čakaciu listinu)\n50% - ostatné orgány",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% - srdce, obličky, pečeň, pľúca, tenké črevo, pankreas, tvár, horné a dolné končatiny (vrátane zaradenia na čakaciu listinu)",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Tuberkulóza", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "100%",
        }),
        ("Závažné psychické poruchy", {
          "allianz": "nie",
          "csob": "nie",
          "generali": "100% (bipolárna a obsedívno-kompulzívna choroba)",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("Zlyhanie obličiek", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% / 50% na podstúpenie chir.zákroku",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Zlyhanie pečene", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% / 50% na podstúpenie chir.zákroku",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Zlyhanie pľúc", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100% / 50% na podstúpenie chir.zákroku",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Zlyhanie srdca (kardio-myopatia)", {
          "allianz": "100%",
          "csob": "100%",
          "generali": "100%",
          "kooperativa": "100%",
          "nn": "100%",
          "uniqa": "100%",
          "wdobrom": "100%",
          "4u": "100%",
        }),
        ("Žltá zimnica", {
          "allianz": "30% (balík gold a platinum)",
          "csob": "20%",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "10%",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
      ],
    },
    {
      "title": "Trvalé následky úrazu",
      "rows": [
        ("mikrospánok/nevoľnosť", {
          "allianz": "nie",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "áno",
        }),
        ("progresia od", {
          "allianz": "21%",
          "csob": "21%",
          "generali": "11%",
          "kooperativa": "26%",
          "nn": "15%",
          "uniqa": "5%",
          "wdobrom": "1%",
          "4u": "5% (pri tarife TN 600%)",
        }),
        ("pripoistenie", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "nie",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "áno",
        }),
        ("extra obmedzenia v PP (pozor na!)", {
          "allianz": "nie",
          "csob": "precenenie vlastných telesných síl pri platničkových, alebo chrbticových syndrómoch",
          "generali": "nie",
          "kooperativa": "nie",
          "nn": "nie",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("definícia úrazu", {
          "allianz": "vonkajšie príčiny",
          "csob": "vonkajšie/vnútorné príčiny",
          "generali": "vonkajšie/vnútorné príčiny",
          "kooperativa": "vonkajšie príčiny",
          "nn": "vonkajšie/vnútorné príčiny",
          "uniqa": "vonkajšie/vnútorné príčiny",
          "wdobrom": "vonkajšie/vnútorné príčiny",
          "4u": "vonkajšie/vnútorné príčiny",
        }),
      ],
    },
    {
      "title": "PN",
      "rows": [
        ("karenčná doba/typ výplaty PN", {
          "allianz": "29/následne/spätne, 60/spätne",
          "csob": "29/spätne, 60/následne",
          "generali": "15/spätne, 29/spätne/následne",
          "kooperativa": "22/následne",
          "nn": "28/spätne",
          "uniqa": "15/následne, 29 spätne/následne",
          "wdobrom": "28/1 spätne, 28/29 následne, 60/1 spätne",
          "4u": "29/57/85 následne aj spätne",
        }),
        ("max. dĺžka liečenia (v dňoch)", {
          "allianz": "500",
          "csob": "720",
          "generali": "365",
          "kooperativa": "365",
          "nn": "600",
          "uniqa": "bez obmedzenia",
          "wdobrom": "550",
          "4u": "730",
        }),
      ],
    },
    {
      "title": "Rizikové tehotenstvo / PS bez skúmania príjmu",
      "rows": [
        ("rizikové tehotenstvo/čakacia doba (v mes.)", {
          "allianz": "12",
          "csob": "9",
          "generali": "9",
          "kooperativa": "12",
          "nn": "9",
          "uniqa": "9",
          "wdobrom": "9",
          "4u": "10",
        }),
        ("PS bez skúmania príjmu", {
          "allianz": "20€",
          "csob": "neskúmajú príjem",
          "generali": "10€",
          "kooperativa": "nie",
          "nn": "20€",
          "uniqa": "40€ (závislosti od povolania)",
          "wdobrom": "15€ - deti a osoby bez príjmu\n20€ - zamestnanci a SZČO",
          "4u": "Vážne úrazy - 20 €\nDrobné úrazy - 10 €",
        }),
        ("čakacia doba (v mes.)", {
          "allianz": "2",
          "csob": "3",
          "generali": "3",
          "kooperativa": "3",
          "nn": "2",
          "uniqa": "2",
          "wdobrom": "2",
          "4u": "2",
        }),
        ("územná platnosť", {
          "allianz": "SR",
          "csob": "SR",
          "generali": "Európa",
          "kooperativa": "SR",
          "nn": "SR, ČR",
          "uniqa": "Európa",
          "wdobrom": "SR: 1 PU v rámci poistenia plnená v rámci ČR, Nemecko, Rakúsko",
          "4u": "ČR/SR: 1 PU v rámci poistenia plnená v rámci EÚ, EHP a Švajčiarska",
        }),
      ],
    },
    {
      "title": "Denné odškodné",
      "rows": [
        ("podvrtnutie", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "áno",
        }),
        ("pomliaždeniny", {
          "allianz": "áno",
          "csob": "áno (rozsiahle hlboké pomliaždenie)",
          "generali": "áno",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "áno",
          "wdobrom": "áno",
          "4u": "áno",
        }),
        ("jazva", {
          "allianz": "áno",
          "csob": "nie",
          "generali": "áno - od 45cm2",
          "kooperativa": "áno",
          "nn": "áno",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "nie",
        }),
        ("popáleniny", {
          "allianz": "áno - od 6cm2 povrchu tela",
          "csob": "áno - od 6cm2 povrchu tela",
          "generali": "áno",
          "kooperativa": "áno - od 2,5% povrchu tela",
          "nn": "áno - od 1% povrchu tela",
          "uniqa": "áno, od II. stupňa",
          "wdobrom": "áno - od 2% povrchu tela",
          "4u": "áno, od II. stupňa",
        }),
        ("zrýchlená likvidácia", {
          "allianz": "áno",
          "csob": "áno",
          "generali": "áno",
          "kooperativa": "nie",
          "nn": "áno",
          "uniqa": "nie",
          "wdobrom": "nie",
          "4u": "áno",
        }),
      ],
    },
    {
      "title": "Hospitalizácia",
      "rows": [
        ("čakacia doba (v mes.)", {
          "allianz": "2",
          "csob": "3",
          "generali": "3",
          "kooperativa": "3",
          "nn": "0",
          "uniqa": "2",
          "wdobrom": "2",
          "4u": "2",
        }),
        ("územná platnosť", {
          "allianz": "EU",
          "csob": "EU",
          "generali": "svet",
          "kooperativa": "Európa",
          "nn": "EU+EHP, Švajčiarsko, Veľká Británia",
          "uniqa": "svet",
          "wdobrom": "svet",
          "4u": "EU+EHP a Švajčiarsko",
        }),
        ("min. doba", {
          "allianz": "1 polnoc",
          "csob": "2 polnoci",
          "generali": "24 hod.",
          "kooperativa": "24 hod. (plnenie od 2. dňa)",
          "nn": "1 polnoc",
          "uniqa": "1 polnoc",
          "wdobrom": "1 polnoc",
          "4u": "1 polnoc",
        }),
        ("max.doba", {
          "allianz": "365 dní (úraz)",
          "csob": "365 dní",
          "generali": "nie je stanovená",
          "kooperativa": "360 dní",
          "nn": "365 dní",
          "uniqa": "nie je stanovená",
          "wdobrom": "365 dní",
          "4u": "730 dní (aj na viaceré vzájomne súvisiace PU)",
        }),
        ("výluky a obmedzenia v PP", {
          "allianz": "HIV, pohlavné choroby, obezita, psych.dg.",
          "csob": "infekčné choroby, pohlavné choroby, psych.dg.",
          "generali": "psych.dg.",
          "kooperativa": "HIV, umelé oplodnenie, potraty, sterilita, sprievod blízkej osoby, psych.dg.",
          "nn": "HIV, umelé prerušenie tehotenstva, psych.dg.",
          "uniqa": "liečba neplodnosti, psych.dg., závislosti",
          "wdobrom": "psych.dg.",
          "4u": "umelé oplodnenie, umelé prerušenie tehotenstva",
        }),
      ],
    },
  ]

  limits_groups = [
    {
      "title": "Hlavná tarifa",
      "rows": [
        ("Min.vstupný vek", {"allianz": "2 týždne", "csob": "2 týždne", "generali": "2 týždne", "kooperativa": "6 týždňov", "nn": "0", "uniqa": "15", "wdobrom": "16", "4u": "16"}),
        ("Max.vstupný vek", {"allianz": "70", "csob": "75", "generali": "70", "kooperativa": "75", "nn": "75", "uniqa": "75", "wdobrom": "70", "4u": "65"}),
        ("Max. výstupný vek", {"allianz": "85", "csob": "80", "generali": "75", "kooperativa": "80", "nn": "80", "uniqa": "80", "wdobrom": "75", "4u": "80"}),
        ("Min.PS", {"allianz": "300", "csob": "700", "generali": "330", "kooperativa": "400", "nn": "2000", "uniqa": "1000", "wdobrom": "1000", "4u": "200"}),
        ("Max.PS", {"allianz": "300", "csob": "700", "generali": "500000", "kooperativa": "400", "nn": "4000", "uniqa": "400000", "wdobrom": "400000", "4u": "200"}),
      ],
    },
    {
      "title": "HYPO",
      "rows": [
        ("Min.vstupný vek", {"allianz": "16", "csob": "nepoisťuje", "generali": "18", "kooperativa": "18", "nn": "18", "uniqa": "18", "wdobrom": "18", "4u": "16"}),
        ("Max.vstupný vek", {"allianz": "60", "csob": "60", "generali": "55", "kooperativa": "54", "nn": "65", "uniqa": "60", "wdobrom": "60", "4u": "60"}),
        ("Max.PS", {"allianz": "200000", "csob": "350000", "generali": "400000", "kooperativa": "400000", "nn": "200000", "uniqa": "400000", "wdobrom": "400000", "4u": "600000"}),
      ],
    },
    {
      "title": "Trvalé následky úrazu / Denné odškodné / Hospitalizácia",
      "rows": [
        ("Min.vstupný vek", {"allianz": "16", "csob": "2 týždne", "generali": "2 týždne", "kooperativa": "6 týždňov", "nn": "18", "uniqa": "15", "wdobrom": "16", "4u": "16"}),
        ("Max.vstupný vek", {"allianz": "60", "csob": "75", "generali": "70", "kooperativa": "75", "nn": "70", "uniqa": "65", "wdobrom": "65", "4u": "65"}),
        ("Min.PS", {"allianz": "7000", "csob": "3000", "generali": "1500", "kooperativa": "3300", "nn": "4000", "uniqa": "1000", "wdobrom": "4000", "4u": "4000"}),
        ("Max.PS", {"allianz": "100000", "csob": "50000", "generali": "100000", "kooperativa": "400000", "nn": "200000", "uniqa": "150000", "wdobrom": "400000", "4u": "400000"}),
      ],
    },
    {
      "title": "Kritické choroby (limity)",
      "rows": [
        ("Min.vstupný vek", {"allianz": "16", "csob": "14", "generali": "15", "kooperativa": "16", "nn": "18", "uniqa": "15", "wdobrom": "16", "4u": "16"}),
        ("Max.vstupný vek", {"allianz": "60", "csob": "60", "generali": "65", "kooperativa": "65", "nn": "65", "uniqa": "60", "wdobrom": "60", "4u": "60"}),
        ("Max. výstupný vek", {"allianz": "65", "csob": "65", "generali": "70", "kooperativa": "70", "nn": "70", "uniqa": "65", "wdobrom": "70", "4u": "70"}),
        ("Min.PS", {"allianz": "3000", "csob": "3000", "generali": "1500", "kooperativa": "2000", "nn": "4000", "uniqa": "1000", "wdobrom": "4000", "4u": "4000"}),
        ("Max.PS", {"allianz": "neobmedzená", "csob": "100000", "generali": "350000", "kooperativa": "400000", "nn": "200000", "uniqa": "250000", "wdobrom": "320000", "4u": "320000"}),
        ("Min.PD", {"allianz": "5", "csob": "5", "generali": "10", "kooperativa": "5", "nn": "5", "uniqa": "5", "wdobrom": "5", "4u": "5"}),
      ],
    },
    {
      "title": "Invalidita (JV/R)",
      "rows": [
        ("Min.vstupný vek", {"allianz": "16", "csob": "14", "generali": "18", "kooperativa": "16", "nn": "18", "uniqa": "18", "wdobrom": "18", "4u": "16"}),
        ("Max.vstupný vek", {"allianz": "60", "csob": "60", "generali": "60", "kooperativa": "59", "nn": "65", "uniqa": "60", "wdobrom": "60", "4u": "60"}),
        ("Min.PS", {"allianz": "5000", "csob": "5000", "generali": "1500", "kooperativa": "2000", "nn": "4000", "uniqa": "1000", "wdobrom": "4000", "4u": "4000"}),
        ("Max.PS", {"allianz": "400000", "csob": "200000", "generali": "350000", "kooperativa": "400000", "nn": "400000", "uniqa": "50000(KS)/250000(KLS)", "wdobrom": "250000", "4u": "600000"}),
      ],
    },
  ]

  # Extract 'Kritické choroby' into its own group and remove it from rizika
  critical_groups = [g for g in risk_groups if g.get("title") == "Kritické choroby"]
  risk_groups = [g for g in risk_groups if g.get("title") != "Kritické choroby"]

  def normalize_text(value):
    return escape(str(value)).replace("\n", "<br>")

  def render_insurer_head(insurer):
    sub = f'<span class="rzp-head-sub">{normalize_text(insurer["sub"])}</span>' if insurer["sub"] else ""
    color = insurer_colors.get(insurer["slug"], "#333")
    return f'''
      <th class="rzp-insurer-th" data-rzp-insurer="{insurer["slug"]}">
        <div class="rzp-head-wrap" style="--accent:{color};">
          <div class="rzp-head-brand" style="color:{color};">{normalize_text(insurer["brand"])}</div>
          <div class="rzp-head-product">{normalize_text(insurer["product"])}</div>
          {sub}
        </div>
      </th>
      '''

  def render_table(group):
    header_cells = "\n".join(render_insurer_head(insurer) for insurer in insurers)
    body_rows = []
    if not group["rows"]:
      body_rows.append(
        '<tr><td class="rzp-empty-row" colspan="9">Údaje sa budú dopĺňať.</td></tr>'
      )
    else:
      for row_label, values in group["rows"]:
        cells = []
        for insurer in insurers:
          cell_value = normalize_text(values.get(insurer["slug"], ""))
          cells.append(f'<td data-rzp-insurer="{insurer["slug"]}">{cell_value}</td>')
        body_rows.append(
          f'<tr><th class="rzp-row-label">{normalize_text(row_label)}</th>{"".join(cells)}</tr>'
        )
    return f'''
      <section class="rzp-table-block">
        <table class="rzp-table">
          <thead>
            <tr class="rzp-section-row"><th colspan="9">{normalize_text(group["title"])}</th></tr>
            <tr>
              <th class="rzp-corner"></th>
              {header_cells}
            </tr>
          </thead>
          <tbody>
            {''.join(body_rows)}
          </tbody>
        </table>
      </section>
      '''

  tables_html = "\n".join(render_table(group) for group in row_groups)
  critical_tables_html = "\n".join(render_table(group) for group in critical_groups) if critical_groups else '<div class="rzp-empty">Táto sekcia je pripravená na doplnenie údajov o kritických chorobách.</div>'
  rizika_tables_html = "\n".join(render_table(group) for group in risk_groups)
  limits_tables_html = "\n".join(render_table(group) for group in limits_groups) if limits_groups else '<div class="rzp-empty">Táto sekcia je pripravená na doplnenie limitov a výluk.</div>'
  insurer_checkboxes = "\n".join(
    f'''
    <label style="display:inline-flex;align-items:center;gap:8px;padding:4px 10px;border:1px solid #dbe3ea;border-radius:999px;background:#fff;cursor:pointer;">
      <input type="checkbox" checked data-rzp-filter="{insurer["slug"]}">
      <span>{normalize_text(insurer["product"])}</span>
    </label>
    '''
    for insurer in insurers
  )

  content = f"""
    <style>
      .rzp-page {{
        margin: -24px -24px 0;
        background: #ffffff;
        color: #222;
      }}
      .rzp-hero {{
        background: linear-gradient(180deg, #33b9ff 0%, #18a5ff 100%);
        color: #fff;
        text-align: center;
        padding: 12px 20px 14px;
        font-size: 1.95rem;
        line-height: 1.1;
        font-weight: 700;
        letter-spacing: 0.2px;
      }}
      .rzp-toolbar {{
        display: flex;
        justify-content: center;
        flex-wrap: wrap;
        gap: 16px;
        padding: 14px 20px 18px;
      }}
      .rzp-tabs {{
        display: inline-flex;
        border: 1px solid #6b6b6b;
        border-radius: 999px;
        overflow: hidden;
        background: #fff;
      }}
      .rzp-tab {{
        appearance: none;
        border: 0;
        background: #fff;
        color: #444;
        font-size: 1rem;
        padding: 11px 20px;
        cursor: pointer;
        border-right: 1px solid #6b6b6b;
      }}
      .rzp-tab:last-child {{
        border-right: 0;
      }}
      .rzp-tab.active {{
        background: #333;
        color: #fff;
        font-weight: 700;
      }}
      .rzp-button {{
        appearance: none;
        border: 1px solid #5f5f5f;
        background: #fff;
        color: #333;
        border-radius: 999px;
        padding: 11px 26px;
        font-size: 1rem;
        font-weight: 600;
        cursor: pointer;
      }}
      .rzp-filter-panel {{
        display: none;
        max-width: 1400px;
        margin: 0 auto 14px;
        padding: 14px 18px;
        background: #fff;
        border: 1px solid #e5ebf1;
        border-radius: 16px;
        box-shadow: 0 4px 18px rgba(15, 23, 42, 0.05);
      }}
      .rzp-filter-panel.show {{
        display: block;
      }}
      .rzp-filter-title {{
        margin: 0 0 12px;
        font-size: 1rem;
        font-weight: 700;
        color: #333;
      }}
      .rzp-filter-list {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .rzp-stage {{
        padding: 0 18px 22px;
      }}
      .rzp-panel {{
        display: none;
      }}
      .rzp-panel.active {{
        display: block;
      }}
      .rzp-table-block {{
        margin-bottom: 16px;
        overflow-x: auto;
        background: #fff;
        border-radius: 12px;
        border: 1px solid #c8c8c8;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
      }}
      .rzp-table {{
        width: 100%;
        min-width: 1320px;
        border-collapse: collapse;
        table-layout: fixed;
      }}
      .rzp-table th,
      .rzp-table td {{
        border: 1px solid #9f9f9f;
        padding: 7px 8px;
        vertical-align: middle;
        background: #fff;
        font-size: 0.95rem;
      }}
      .rzp-table thead th {{
        text-align: center;
      }}
      .rzp-corner {{
        width: 230px;
        background: #fff;
      }}
      .rzp-section-row th {{
        background: #62c7f2;
        color: #00324f;
        text-align: left !important;
        font-size: 1rem;
        font-weight: 700;
        padding: 6px 10px;
      }}
      .rzp-insurer-th {{
        width: 135px;
        background: #fff;
      }}
      .rzp-head-wrap {{
        display: flex;
        flex-direction: column;
        gap: 2px;
        align-items: center;
        justify-content: center;
        min-height: 78px;
      }}
      .rzp-head-brand {{
        font-size: 0.95rem;
        font-weight: 800;
        line-height: 1.05;
      }}
      .rzp-head-product {{
        font-size: 0.95rem;
        font-weight: 700;
        text-align: center;
      }}
      .rzp-head-sub {{
        display: block;
        font-size: 0.68rem;
        line-height: 1.1;
        text-align: center;
      }}
      .rzp-row-label {{
        width: 230px;
        text-align: left;
        font-weight: 500;
        background: #fff;
      }}
      .rzp-table tbody td {{
        white-space: pre-line;
        text-align: left;
        line-height: 1.15;
      }}
      .rzp-empty-row {{
        text-align: center !important;
        color: #666;
        padding: 14px 10px;
        font-style: italic;
      }}
      .rzp-note {{
        max-width: 1400px;
        margin: 0 auto 14px;
        padding: 10px 14px;
        border-left: 4px solid #18a5ff;
        background: #edf8fe;
        color: #114a66;
        border-radius: 10px;
      }}
      .rzp-empty {{
        max-width: 1400px;
        margin: 0 auto;
        padding: 18px;
        background: #fff;
        border: 1px dashed #d6dde5;
        border-radius: 18px;
        color: #5b6774;
      }}
      .rzp-closure-banner {{
        max-width: 1400px;
        margin: 0 auto 10px;
        background: #62c7f2;
        color: #00324f;
        padding: 6px 10px;
        font-weight: 700;
        border-radius: 8px;
      }}
      @media (max-width: 1200px) {{
        .rzp-table {{
          min-width: 1100px;
        }}
      }}
    </style>
    <div class="rzp-page">
      <div class="rzp-hero">Rizikové životné poistenie</div>
      <div class="rzp-toolbar">
        <div class="rzp-tabs" role="tablist" aria-label="RŽP sekcie">
          <button class="rzp-tab active" type="button" data-rzp-tab="vseobecne">Všeobecne</button>
          <button class="rzp-tab" type="button" data-rzp-tab="rizika">Riziká</button>
          <button class="rzp-tab" type="button" data-rzp-tab="kriticke_choroby">Kritické choroby</button>
          <button class="rzp-tab" type="button" data-rzp-tab="limity">Limity</button>
        </div>
        <button class="rzp-button" type="button" onclick="toggleRzpFilters()">Vybrať poisťovne</button>
        <button class="rzp-button" type="button" onclick="toggleRzpExtraFilters()">Zmeniť filtre</button>
      </div>

      <div id="rzpFilterPanel" class="rzp-filter-panel">
        <p class="rzp-filter-title">Zobrazené poisťovne</p>
        <div class="rzp-filter-list">
          {insurer_checkboxes}
        </div>
      </div>

      <div class="rzp-stage">
        <div class="rzp-panel active" data-rzp-panel="vseobecne">
          <div class="rzp-note">Sekcia Všeobecné je doplnená podľa screenshotov. Po zadaní ďalších podkapitol sem vieme pridať aj detailné tabuľky za jednotlivé riziká.</div>
          <div id="rzpGeneralTables">
            {tables_html}
          </div>
        </div>
        <div class="rzp-panel" data-rzp-panel="rizika">
            <div class="rzp-note">Sekcia Riziká je doplnená podľa dodaných screenshotov. Dáta sa dajú ďalej upravovať po jednotlivých podkapitolách.</div>
              <div class="rzp-note">Kritické choroby sú dostupné aj ako samostatná záložka.</div>
            <div id="rzpRiskTables">
              {rizika_tables_html}
            </div>
        </div>
        <div class="rzp-panel" data-rzp-panel="kriticke_choroby">
          <div class="rzp-note">Kritické choroby sú vyčlenené aj samostatne pre rýchly prehľad.</div>
          <div id="rzpCriticalTables">
            {critical_tables_html}
          </div>
        </div>
        <div class="rzp-panel" data-rzp-panel="limity">
          <div id="rzpLimitsTables">
            {limits_tables_html}
          </div>
        </div>
      </div>
    </div>

    <script>
      function toggleRzpFilters() {{
        const panel = document.getElementById('rzpFilterPanel');
        if (!panel) return;
        panel.classList.toggle('show');
      }}

      function toggleRzpExtraFilters() {{
        const activeTab = document.querySelector('.rzp-tab.active');
        if (activeTab) {{
          const nextMap = {{
            vseobecne: 'rizika',
            rizika: 'kriticke_choroby',
            kriticke_choroby: 'limity',
            limity: 'vseobecne'
          }};
          activateRzpTab(nextMap[activeTab.dataset.rzpTab] || 'vseobecne');
        }}
      }}

      function activateRzpTab(tabName) {{
        document.querySelectorAll('.rzp-tab').forEach((button) => {{
          button.classList.toggle('active', button.dataset.rzpTab === tabName);
        }});
        document.querySelectorAll('.rzp-panel').forEach((panel) => {{
          panel.classList.toggle('active', panel.dataset.rzpPanel === tabName);
        }});
      }}

      function syncRzpColumnVisibility() {{
        const selected = new Set();
        document.querySelectorAll('#rzpFilterPanel input[type="checkbox"][data-rzp-filter]').forEach((checkbox) => {{
          if (checkbox.checked) selected.add(checkbox.dataset.rzpFilter);
        }});

        document.querySelectorAll('#rzpGeneralTables [data-rzp-insurer], #rzpRiskTables [data-rzp-insurer], #rzpCriticalTables [data-rzp-insurer], #rzpLimitsTables [data-rzp-insurer]').forEach((cell) => {{
          const shouldShow = selected.has(cell.dataset.rzpInsurer);
          cell.style.display = shouldShow ? '' : 'none';
        }});

        const visibleCount = Array.from(document.querySelectorAll('#rzpFilterPanel input[type="checkbox"][data-rzp-filter]')).filter((checkbox) => checkbox.checked).length;
        const title = document.querySelector('.rzp-filter-title');
        if (title) {{
          title.textContent = 'Zobrazené poisťovne: ' + visibleCount;
        }}
      }}

      document.addEventListener('DOMContentLoaded', () => {{
        document.querySelectorAll('.rzp-tab').forEach((button) => {{
          button.addEventListener('click', () => activateRzpTab(button.dataset.rzpTab));
        }});

        document.querySelectorAll('#rzpFilterPanel input[type="checkbox"][data-rzp-filter]').forEach((checkbox) => {{
          checkbox.addEventListener('change', syncRzpColumnVisibility);
        }});

        syncRzpColumnVisibility();
      }});
    </script>
  """
  return render_template_string(APP_TEMPLATE, content=content)


@app.route("/hypo/calc", methods=["POST"])
@login_required
def hypo_calc():
    try:
        body = request.get_json() or {}
        loan_amount = float(body.get('loan_amount', 0))
        annual_rate = float(body.get('annual_rate', 0))
        years = int(body.get('years', 0))
        first_payment_str = body.get('first_payment', '')
        insurance_sum = float(body.get('insurance_sum', 0))
        insurance_years = int(body.get('insurance_years', 0))
        increase_pct = float(body.get('increase_pct', 0) or 0)

        if years <= 0 or loan_amount <= 0:
            return jsonify({'error': 'Neplatné vstupy (kladné čísla)'}), 400

        # Parse date
        try:
            first_payment = datetime.strptime(first_payment_str, '%Y-%m-%d').date()
        except Exception:
            first_payment = datetime.now().date()

        monthly = calculate_monthly_payment(loan_amount, annual_rate, years)
        schedule = generate_amortization_schedule(loan_amount, annual_rate, years, first_payment, insurance_sum, insurance_years, increase_pct)
        optimized = optimize_insurance_initial(schedule, insurance_years)
        total_interest = sum(r['interest'] for r in schedule)
        total_paid = sum(r['payment'] for r in schedule)

        return jsonify({
            'monthly_payment': round(monthly, 2),
            'schedule': schedule,
            'optimized': optimized,
            'total_interest': round(total_interest, 2),
            'total_paid': round(total_paid, 2)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _compute_izp_projection(payload):
    start_month = int(payload.get('start_month', 5) or 5)
    start_year = int(payload.get('start_year', 2024) or 2024)
    end_month = int(payload.get('end_month', 5) or 5)
    end_year = int(payload.get('end_year', 2045) or 2045)

    total_premium = float(payload.get('total_premium', 100) or 100)
    saving_part = float(payload.get('saving_part', 50) or 50)
    admin_fee = float(payload.get('admin_fee', 5) or 0)
    entry_fee_pct = float(payload.get('entry_fee_pct', 5) or 0)
    surrender_fee_pct = float(payload.get('surrender_fee_pct', 5) or 0)
    management_fee_pct = float(payload.get('management_fee_pct', 2) or 0)
    annual_yield_pct = float(payload.get('annual_yield_pct', 8) or 0)

    months = max(12, (end_year - start_year) * 12 + (end_month - start_month) + 1)
    years = max(1, round(months / 12))

    # IŽP Calculation
    yearly_rows = []
    fund_balance = 0.0
    cum_gross = 0.0
    cum_invested = 0.0
    total_fees_paid = 0.0

    monthly_admin = admin_fee
    monthly_entry = saving_part * (entry_fee_pct / 100.0)
    monthly_net_saving = max(0.0, saving_part - monthly_entry)
    monthly_mgmt = management_fee_pct / 100.0 / 12.0
    monthly_growth = annual_yield_pct / 100.0 / 12.0

    for month_idx in range(1, years * 12 + 1):
        year_idx = (month_idx - 1) // 12 + 1

        # IŽP: administratívny poplatok znižuje mesačne investovanú sumu.
        invested_this_month = max(0.0, monthly_net_saving - monthly_admin)
        cum_gross += saving_part
        cum_invested += invested_this_month

        fees_this_month = monthly_admin + monthly_entry + (fund_balance * monthly_mgmt)
        total_fees_paid += fees_this_month

        fund_balance = max(0.0, fund_balance * (1.0 + monthly_growth - monthly_mgmt) + invested_this_month)

        if month_idx % 12 == 0:
            yearly_rows.append(
                {
                    'year': year_idx,
                    'gross': round(cum_gross, 2),
                    'invested': round(cum_invested, 2),
                    'fund': round(fund_balance, 2),
                }
            )

    saved_in_izp = fund_balance
    after_surrender = max(0.0, saved_in_izp * (1.0 - surrender_fee_pct / 100.0))

    # Investment Savings Calculation (same saving_part, only entry_fee_pct and management_fee_pct)
    investment_yearly_rows = []
    investment_balance = 0.0
    investment_cum_gross = 0.0
    investment_cum_invested = 0.0
    investment_total_fees = 0.0

    # Same monthly net saving and fees as IŽP
    investment_monthly_entry = saving_part * (entry_fee_pct / 100.0)
    investment_monthly_net = max(0.0, saving_part - investment_monthly_entry)
    investment_monthly_mgmt = management_fee_pct / 100.0 / 12.0

    for month_idx in range(1, years * 12 + 1):
        year_idx = (month_idx - 1) // 12 + 1

        investment_invested_this_month = investment_monthly_net
        investment_cum_gross += saving_part
        investment_cum_invested += investment_invested_this_month

        investment_fees_this_month = investment_monthly_entry + (investment_balance * investment_monthly_mgmt)
        investment_total_fees += investment_fees_this_month

        investment_balance = max(0.0, investment_balance * (1.0 + monthly_growth - investment_monthly_mgmt) + investment_invested_this_month)

        if month_idx % 12 == 0:
            investment_yearly_rows.append(
                {
                    'year': year_idx,
                    'fund': round(investment_balance, 2),
                }
            )

    # Calculate the gain difference
    investment_gain = investment_balance - fund_balance

    # Requested formula for invested amount display:
    # Sporiaca časť * 12 * (koniec zmluvy - začiatok zmluvy)
    saving_years = max(0, end_year - start_year)
    invested_amount_formula = saving_part * 12 * saving_years

    # Calculate surrender fee amount from the final saved_in_izp
    surrender_fee_amount = saved_in_izp * (surrender_fee_pct / 100.0)

    summary = {
        'paid_fees': round(total_fees_paid, 2),
        'in_funds_more': round(max(0.0, fund_balance - cum_invested), 2),
        'future_fees': round(monthly_admin * years * 12, 2),
        'invested_amount': round(invested_amount_formula, 2),
        'saved_izp': round(saved_in_izp, 2),
        'surrender_fee_amount': round(surrender_fee_amount, 2),
        'after_surrender': round(after_surrender, 2),
        'fund_end': round(fund_balance, 2),
        'investment_fund_end': round(investment_balance, 2),
        'investment_gain': round(investment_gain, 2),
        'term_years': years,
    }

    return {
        'labels': [f"{row['year']}. r." for row in yearly_rows],
        'gross_series': [row['gross'] for row in yearly_rows],
        'invested_series': [row['invested'] for row in yearly_rows],
        'fund_series': [row['fund'] for row in yearly_rows],
        'investment_series': [row['fund'] for row in investment_yearly_rows],
        'summary': summary,
    }


@app.route("/izp", methods=["GET"])
@login_required
def izp():
    content = """
    <h2>Investičné životné poistenie</h2>

    <div id="izp_results" style="display:none;">
      <div class="card" style="padding:12px;margin-bottom:16px;">
        <h4 style="margin:0 0 10px 0;">Investičné životné poistenie</h4>
        <div style="max-width:1100px;margin:0 auto;height:420px;">
          <canvas id="izp_main_chart"></canvas>
        </div>
      </div>
    </div>

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start;">
      <div class="card" style="padding:12px;">
        <h4 style="margin:0 0 8px 0;">Detaily zmluvy</h4>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label>Začiatok zmluvy (mesiac)</label>
            <input id="start_month" type="number" value="5" min="1" max="12">
          </div>
          <div>
            <label>Začiatok zmluvy (rok)</label>
            <input id="start_year" type="number" value="2024" min="2000" max="2100">
          </div>
          <div>
            <label>Koniec zmluvy (mesiac)</label>
            <input id="end_month" type="number" value="5" min="1" max="12">
          </div>
          <div>
            <label>Koniec zmluvy (rok)</label>
            <input id="end_year" type="number" value="2045" min="2000" max="2100">
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label>Celkové poistné (€)</label>
            <input id="total_premium" type="number" value="100" step="1">
          </div>
          <div>
            <label>Sporiaca časť (€)</label>
            <input id="saving_part" type="number" value="50" step="1">
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label>Administratívny poplatok (€)</label>
            <input id="admin_fee" type="number" value="5" step="0.1">
          </div>
          <div>
            <label>Vstupný poplatok (%)</label>
            <input id="entry_fee_pct" type="number" value="5" step="0.1">
          </div>
          <div>
            <label>Odkupný poplatok (%)</label>
            <input id="surrender_fee_pct" type="number" value="5" step="0.1">
          </div>
          <div>
            <label>Správcovský poplatok (%)</label>
            <input id="management_fee_pct" type="number" value="2" step="0.1">
          </div>
          <div>
            <label>Ročný výnos (%)</label>
            <input id="annual_yield_pct" type="number" value="8" step="0.1">
          </div>
        </div>

        <button class="btn" onclick="runIzpCalc()" style="width:100%;margin-top:6px;">Prepočítať</button>
      </div>

      <div id="izp_summary" style="display:none;gap:12px;">
        <div class="card" style="padding:12px;">
          <h4 style="margin:0 0 8px 0;">Výpočet</h4>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
            <div style="border:1px solid #c9c9c9;border-radius:10px;padding:10px;text-align:center;">
              <div style="font-size:0.85rem;color:#666;">Zaplatené na poplatkoch</div>
              <div id="sum_paid_fees" style="font-size:1.8rem;font-weight:700;">0 €</div>
            </div>
            <div style="border:1px solid #c9c9c9;border-radius:10px;padding:10px;text-align:center;">
              <div style="font-size:0.85rem;color:#666;">Vo fondoch nasporíte viac o</div>
              <div id="sum_in_funds_more" style="font-size:1.8rem;font-weight:700;">0 €</div>
            </div>
          </div>

          <div style="margin-top:8px;display:grid;gap:6px;">
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Investované prostriedky</span><strong id="sum_invested">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Nasporené v IŽP</span><strong id="sum_saved_izp">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#ffebee;border-radius:10px;padding:8px 12px;"><span>Odkupný poplatok</span><strong id="sum_surrender_fee" style="color:#c62828;">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#e8f5e9;border-radius:10px;padding:8px 12px;"><span>Investičné sporenie (bez poistenia)</span><strong id="sum_investment_fund" style="color:#2e7d32;">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#c8e6c9;border-radius:10px;padding:8px 12px;"><span style="font-weight:600;color:#1b5e20;">Rozdiel (Investičné sporenie vs. IŽP)</span><strong id="sum_investment_gain" style="color:#1b5e20;font-weight:700;">0 €</strong></div>
          </div>
        </div>

        <div class="card" style="padding:12px;">
          <h4 style="margin:0 0 8px 0;">Sporenie</h4>
          <div style="font-size:0.9rem;color:#666;">Prehľad je orientačný a určený na porovnanie poplatkov a investovania v čase. Pri výpočte nieje zohľadnený vplyv inflácie a daňové výhody.</div>
          <div id="izp_alerts" style="margin-top:8px;"></div>
        </div>
      </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
      let izpChart = null;

      function eur(v){
        return Number(v || 0).toLocaleString('sk-SK', {style:'currency', currency:'EUR'});
      }

      function gatherIzpPayload(){
        const ids = [
          'start_month','start_year','end_month','end_year','total_premium','saving_part',
          'admin_fee','entry_fee_pct','surrender_fee_pct','management_fee_pct','annual_yield_pct'
        ];
        const out = {};
        ids.forEach((id)=>{
          out[id] = parseFloat(document.getElementById(id).value || 0);
        });
        return out;
      }

      function fillSummary(summary){
        // Show results section
        document.getElementById('izp_results').style.display = 'block';
        document.getElementById('izp_summary').style.display = 'grid';
        
        document.getElementById('sum_paid_fees').innerText = eur(summary.paid_fees);
        document.getElementById('sum_in_funds_more').innerText = eur(summary.in_funds_more);
        document.getElementById('sum_invested').innerText = eur(summary.invested_amount);
        document.getElementById('sum_saved_izp').innerText = eur(summary.saved_izp);
        document.getElementById('sum_surrender_fee').innerText = eur(summary.surrender_fee_amount);
        
        if (document.getElementById('sum_investment_gain')) {
          document.getElementById('sum_investment_gain').innerText = eur(summary.investment_gain);
        }
        if (document.getElementById('sum_investment_fund')) {
          document.getElementById('sum_investment_fund').innerText = eur(summary.investment_fund_end);
        }
      }

      function drawIzpChart(data){
        const ctx = document.getElementById('izp_main_chart').getContext('2d');
        if(izpChart) izpChart.destroy();

        izpChart = new Chart(ctx, {
          type:'line',
          data:{
            labels:data.labels,
            datasets:[
              {
                label:'Celkovo poistné',
                data:data.gross_series,
                borderColor:'#15a8ff',
                backgroundColor:'rgba(21,168,255,0.10)',
                fill:true,
                pointRadius:0,
                tension:0.25
              },
              {
                label:'Nasporené vo fondoch',
                data:data.fund_series,
                borderColor:'#3d5afe',
                backgroundColor:'rgba(61,90,254,0.08)',
                fill:true,
                pointRadius:0,
                tension:0.25
              },
              {
                label:'Investované prostriedky',
                data:data.invested_series,
                borderColor:'#444',
                fill:false,
                pointRadius:0,
                tension:0.20
              },
              {
                label:'Investičné sporenie',
                data:data.investment_series,
                borderColor:'#52c41a',
                backgroundColor:'rgba(82,196,26,0.08)',
                fill:true,
                pointRadius:0,
                tension:0.25
              }
            ]
          },
          options:{
            responsive:true,
            maintainAspectRatio:true,
            aspectRatio:2.4,
            interaction:{mode:'index',intersect:false},
            plugins:{
              legend:{position:'top'},
              tooltip:{callbacks:{label:(ctx)=>`${ctx.dataset.label}: ${eur(ctx.parsed.y)}`}}
            },
            scales:{
              y:{ticks:{callback:(v)=>eur(v)}}
            }
          }
        });
      }

      async function runIzpCalc(){
        const payload = gatherIzpPayload();
        const alerts = document.getElementById('izp_alerts');
        alerts.innerHTML = '';

        try{
          const res = await fetch('/izp/calc', {
            method:'POST',
            credentials:'same-origin',
            headers:{'Content-Type':'application/json'},
            body:JSON.stringify(payload)
          });

          const data = await res.json();
          if(!res.ok){
            alerts.innerHTML = `<div class="error">⚠️ ${data.error || 'Výpočet zlyhal.'}</div>`;
            return;
          }

          fillSummary(data.summary);
          drawIzpChart(data);

          const netGain = Number(data.summary.fund_end || 0) - Number(data.summary.invested_amount || 0);
          if(netGain >= 0){
            alerts.innerHTML = `<div style="padding:8px;border-radius:8px;background:#ecffef;border:1px solid #c7f5d6;color:#0f5132;">✅ Odhadované zhodnotenie je ${eur(netGain)}.</div>`;
          } else {
            alerts.innerHTML = `<div style="padding:8px;border-radius:8px;background:#fff2f2;border:1px solid #f5c2c7;color:#842029;">⚠️ Odhadované zhodnotenie je záporné (${eur(netGain)}). Skontrolujte parametre poplatkov alebo výnosu.</div>`;
          }
        } catch(err){
          alerts.innerHTML = `<div class="error">⚠️ Chyba pripojenia: ${err.message}</div>`;
        }
      }
    </script>
    """
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/izp/calc", methods=["POST"])
@login_required
def izp_calc():
    try:
        payload = request.get_json() or {}
        result = _compute_izp_projection(payload)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
