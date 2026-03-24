import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "prohypo-secret"
FAQ_FILE_PATH = Path(__file__).resolve().parent / "data" / "faq_items.json"

APP_TEMPLATE = """<!doctype html>
<html lang="sk">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ProHypo Asistent </title>
  <style>
    body{font-family:Segoe UI,Arial,sans-serif;background:#f0f6fc;color:#1a2e5a;margin:0;padding:0;}
    .container{max-width:960px;margin:0 auto;padding:28px;}
    .nav{margin-bottom:24px;}
    .nav a{margin-right:12px;text-decoration:none;color:#29b6e8;font-weight:bold;}
    .card{background:#fff;border-radius:8px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,.1);}
    input,select,textarea{width:100%;padding:8px;margin:4px 0 12px;border:1px solid #ccc;border-radius:4px;}
    .btn{background:#29b6e8;color:white;padding:10px 14px;border:none;border-radius:4px;cursor:pointer;}
    .btn:hover{background:#1e8fb7;}
    .error{color:#c00;font-weight:bold;}
    .result{background:#edf7f9;color:#046f8d;border:1px solid #29b6e8;padding:12px;border-radius:4px;white-space:pre-wrap;}
    .copy-btn{margin-bottom:10px;}
    .faq-group{margin-bottom:20px;}
    .faq-item{margin:0 0 10px;}
    .faq-question{width:100%;text-align:left;background:#edf7f9;color:#046f8d;border:1px solid #29b6e8;padding:10px;border-radius:4px;cursor:pointer;font-weight:600;}
    .faq-answer{display:none;background:#f8fbff;border:1px solid #d6e6f5;border-radius:4px;padding:10px;margin-top:6px;white-space:pre-wrap;}
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
  </script>
</head>
<body>
<div class="container">
  <div class="nav">
    <a href="{{ url_for('home') }}">Domov</a>
    <a href="{{ url_for('notice') }}">Výpovedná lehota</a>
    <a href="{{ url_for('vypocetny_email') }}">Výročný email</a>
    <a href="{{ url_for('vystupny_mail') }}">Výstupný mail</a>
    <a href="{{ url_for('backoffice') }}">Backoffice email</a>
        <a href="{{ url_for('najcastejsie_otazky') }}">Najčastejšie otázky</a>
  </div>
  <div class="card">
    <h1>ProHypo servis asistent</h1>
    <p style="font-size:0.9rem;color:#FFFFFF;margin:6px 0;">Aktuálny URL: <strong>{{ request.url_root }}</strong> <br>Aktuálny host: <strong>{{ request.host }}</strong></p>
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


def build_email_text(oslovenie, meno, typ, poistovna, zmluva, vyrocie_pz):
    oslovenie = str(oslovenie).strip()
    meno = str(meno).strip()
    typ = str(typ).strip()
    poistovna = str(poistovna).strip()
    zmluva = str(zmluva).strip()
    vyrocie_pz = str(vyrocie_pz).strip()
    if not all([oslovenie, meno, typ, poistovna, zmluva, vyrocie_pz]):
        raise ValueError("Vyplň všetky polia!")
    return (
        f"Dobrý deň {oslovenie} {meno},\n\n"
        f"posielam Vám informáciu o blížiacom sa výročí Vašej poistnej zmluvy na {typ} v poisťovni {poistovna} (č. zmluvy: {zmluva}), ktorú sme spoločne uzatvárali.\n"
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


@app.route("/")
def home():
    return render_template_string(APP_TEMPLATE, content="<p>Víta ťa ProHypo Asistent. Vyber si modul v ktorom chceš pracovať."
    "</p>")


@app.route("/notice", methods=["GET", "POST"])
def notice():
    response = None
    if request.method == "POST":
        day = request.form.get("day")
        month = request.form.get("month")
        year = request.form.get("year")
        try:
            response = calculate_notice_date(day, month, year)
        except Exception as e:
            flash(str(e))

    day_value = request.form.get('day', '16')
    month_value = request.form.get('month', '3')
    year_value = request.form.get('year', '2026')

    result_html = ""
    if response:
        result_html = f"<div class='result'>Dátum doručenia výpovede: <strong>{response}</strong></div>"
    content = (
        "<h2>Zadaj dátum výročia PZ</h2>"
        "<form method='post'>"
        f"Deň:<input name='day' value='{day_value}' required>"
        f"Mesiac:<input name='month' value='{month_value}' required>"
        f"Rok:<input name='year' value='{year_value}' required>"
        "<button class='btn' type='submit'>Vypočítať</button>"
        "</form>"
        f"{result_html}"
    )

    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/email")
def email_redirect():
    return redirect(url_for('vypocetny_email'))


@app.route("/vypocetny_email", methods=["GET", "POST"])
def vypocetny_email():
    result = None
    if request.method == "POST":
        data = {k: request.form.get(k, "") for k in ["oslovenie", "meno", "typ", "poistovna", "zmluva", "vyrocie_pz"]}
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
        'poistovna': request.form.get('poistovna', 'Allianz'),
        'zmluva': request.form.get('zmluva', ''),
        'vyrocie_pz': request.form.get('vyrocie_pz', '01.01.2027'),
    }

    content = ""
    content += "<h2>Výročný email</h2>"
    content += "<form method='post'>"
    content += "Oslovenie:<select name='oslovenie'><option value='pán'>pán</option><option value='pani'>pani</option></select>"
    content += f"Meno:<input name='meno' value='{prazdne_data['meno']}' required>"
    content += f"Email príjemcu:<input name='email_priemcu' type='email' value='{request.form.get('email_priemcu', '')}'>"
    content += "Typ nehnuteľnosti:<select name='typ' required>"
    content += f"<option value='byt' {'selected' if prazdne_data['typ'].lower()=='byt' else ''}>Byt</option>"
    content += f"<option value='dom' {'selected' if prazdne_data['typ'].lower()=='dom' else ''}>Dom</option>"
    content += "</select>"
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
    content += result_block
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/vystupny_mail", methods=["GET", "POST"])
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
    content += f"<option value='Byt' {'selected' if form_data['typ_nehnutelnosti']=='Byt' else ''}>Byt</option>"
    content += f"<option value='Rodinný dom' {'selected' if form_data['typ_nehnutelnosti']=='Rodinný dom' else ''}>Rodinný dom</option>"
    content += f"<option value='Apartmán' {'selected' if form_data['typ_nehnutelnosti']=='Apartmán' else ''}>Apartmán</option>"
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
    content += result_block
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/backoffice", methods=["GET", "POST"])
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
    content += f"<option value='Finax' {'selected' if form_data['delenie_provizie']=='Finax' else ''}>Finax</option>"
    content += "</select>"
    content += f"Iné:<input name='ine' value='{form_data['ine']}'>"
    content += f"Poznámky:<textarea name='poznamky'>{form_data['poznamky']}</textarea>"
    content += "<button class='btn' type='submit'>Vygenerovať</button>"
    content += "</form>"
    content += result_block
    return render_template_string(APP_TEMPLATE, content=content)


@app.route("/najcastejsie_otazky")
def najcastejsie_otazky():
    faq_items = load_faq_items()
    if not faq_items:
        flash("Súbor otázok je prázdny alebo chýba.")
        content = "<h2>Najčastejšie otázky</h2><p>Zatiaľ nie sú dostupné žiadne otázky.</p>"
        return render_template_string(APP_TEMPLATE, content=content)

    groups = {}
    for item in faq_items:
        groups.setdefault(item["sekcia"], []).append(item)

    content = "<h2>Najčastejšie otázky</h2>"
    for sekcia, items in groups.items():
        content += f"<div class='faq-group'><h3>{sekcia}</h3>"
        for item in items:
            content += "<div class='faq-item'>"
            content += f"<button type='button' class='faq-question' onclick='toggleFaqAnswer(this)'>{item['otazka']}</button>"
            content += f"<div class='faq-answer'>{item['odpoved']}</div>"
            content += "</div>"
        content += "</div>"

    return render_template_string(APP_TEMPLATE, content=content)


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
