import json
import os
import re
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
                label: 'Poistná suma pôvodná',
                data: insurance,
                borderColor: '#0066cc',
                tension: 0.2,
                fill: false,
                pointRadius: 0
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
    first_alloc = float(payload.get('first_alloc_pct', 50) or 50)
    second_alloc = float(payload.get('second_alloc_pct', 50) or 50)

    collection_fee = float(payload.get('collection_fee', 3) or 0)
    admin_fee = float(payload.get('admin_fee', 5) or 0)
    entry_fee_pct = float(payload.get('entry_fee_pct', 5) or 0)
    surrender_fee_pct = float(payload.get('surrender_fee_pct', 5) or 0)
    management_fee_pct = float(payload.get('management_fee_pct', 2) or 0)
    annual_yield_pct = float(payload.get('annual_yield_pct', 8) or 0)

    months = max(12, (end_year - start_year) * 12 + (end_month - start_month) + 1)
    years = max(1, round(months / 12))

    yearly_rows = []
    fund_balance = 0.0
    cum_gross = 0.0
    cum_invested = 0.0
    total_fees_paid = 0.0

    monthly_admin = collection_fee + admin_fee
    monthly_entry = saving_part * (entry_fee_pct / 100.0)
    monthly_net_saving = max(0.0, saving_part - monthly_entry)
    monthly_mgmt = management_fee_pct / 100.0 / 12.0
    monthly_growth = annual_yield_pct / 100.0 / 12.0

    for month_idx in range(1, years * 12 + 1):
        year_idx = (month_idx - 1) // 12 + 1

        # Jednoduchý alokačný model pre prvé dva roky
        alloc_factor = 1.0
        if year_idx == 1:
            alloc_factor = first_alloc / 100.0
        elif year_idx == 2:
            alloc_factor = second_alloc / 100.0

        invested_this_month = monthly_net_saving * alloc_factor
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

    saved_in_izp = cum_gross + fund_balance
    after_surrender = max(0.0, saved_in_izp * (1.0 - surrender_fee_pct / 100.0))

    summary = {
        'paid_fees': round(total_fees_paid, 2),
        'in_funds_more': round(max(0.0, fund_balance - cum_invested), 2),
        'future_fees': round(monthly_admin * years * 12, 2),
        'invested_amount': round(cum_invested, 2),
        'saved_izp': round(saved_in_izp, 2),
        'after_surrender': round(after_surrender, 2),
        'fund_end': round(fund_balance, 2),
        'term_years': years,
    }

    return {
        'labels': [f"{row['year']}. r." for row in yearly_rows],
        'gross_series': [row['gross'] for row in yearly_rows],
        'invested_series': [row['invested'] for row in yearly_rows],
        'fund_series': [row['fund'] for row in yearly_rows],
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

        <label>Počiatočný poplatok - alokačné %</label>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label>1. rok (%)</label>
            <input id="first_alloc_pct" type="number" value="50" step="0.1">
          </div>
          <div>
            <label>2. rok (%)</label>
            <input id="second_alloc_pct" type="number" value="50" step="0.1">
          </div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
          <div>
            <label>Inkásny poplatok (€)</label>
            <input id="collection_fee" type="number" value="3" step="0.1">
          </div>
          <div>
            <label>Administratívny poplatok (€)</label>
            <input id="admin_fee" type="number" value="5" step="0.1">
          </div>
          <div>
            <label>Vstupný/Výstupný/Variabilný (%)</label>
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
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Budúce poplatky</span><strong id="sum_future_fees">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Investované prostriedky</span><strong id="sum_invested">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Nasporené v IŽP</span><strong id="sum_saved_izp">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Po odrátaní odkup. poplatku</span><strong id="sum_after_surrender">0 €</strong></div>
            <div style="display:flex;justify-content:space-between;background:#f3f3f3;border-radius:10px;padding:8px 12px;"><span>Nasporené vo fondoch</span><strong id="sum_fund_end">0 €</strong></div>
          </div>
        </div>

        <div class="card" style="padding:12px;">
          <h4 style="margin:0 0 8px 0;">Sporenie</h4>
          <div style="font-size:0.9rem;color:#666;">Prehľad je orientačný a určený na porovnanie poplatkov a investovania v čase.</div>
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
          'first_alloc_pct','second_alloc_pct','collection_fee','admin_fee','entry_fee_pct',
          'surrender_fee_pct','management_fee_pct','annual_yield_pct'
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
        document.getElementById('sum_future_fees').innerText = eur(summary.future_fees);
        document.getElementById('sum_invested').innerText = eur(summary.invested_amount);
        document.getElementById('sum_saved_izp').innerText = eur(summary.saved_izp);
        document.getElementById('sum_after_surrender').innerText = eur(summary.after_surrender);
        document.getElementById('sum_fund_end').innerText = eur(summary.fund_end);
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
