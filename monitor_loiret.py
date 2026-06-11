import os, json, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup, NavigableString

EMAIL_FROM = os.environ["EMAIL_FROM"]
EMAIL_TO   = os.environ["EMAIL_TO"]
EMAIL_PASS = os.environ["EMAIL_PASS"]
STATE_FILE = "arrete_state.json"
BASE_URL   = "https://www.loiret.gouv.fr"

MOIS = {1:"Janvier",2:"Fevrier",3:"Mars",4:"Avril",5:"Mai",6:"Juin",
        7:"Juillet",8:"Aout",9:"Septembre",10:"Octobre",11:"Novembre",12:"Decembre"}

def get_url():
    now = datetime.now()
    slug = f"{MOIS[now.month]}-{now.year}"
    base = f"{BASE_URL}/Publications/Recueil-des-actes-administratifs/Recueil-des-actes-administratifs-departementaux"
    return [f"{base}/{slug}2", f"{base}/{slug}"]

def fetch_arretes(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "lxml")
    arretes = []
    for b in soup.find_all("b"):
        titre = b.get_text(strip=True)
        if not titre.startswith("RAA"):
            continue
        contenu = []
        pdf_url = None
        for sib in b.parent.next_siblings:
            if isinstance(sib, NavigableString):
                continue
            b2 = sib.find("b")
            if b2 and b2.get_text(strip=True).startswith("RAA"):
                break
            for a in sib.find_all("a", href=True):
                href = a["href"]
                if "telechargement" in href or ".pdf" in href.lower():
                    pdf_url = BASE_URL + href if href.startswith("/") else href
            t = sib.get_text(" ", strip=True)
            if t and "Telecharger" not in t and len(t) > 5:
                contenu.append(t)
        arretes.append({"id": titre, "titre": titre, "contenu": " ".join(contenu)[:300], "pdf": pdf_url})
    return arretes

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"seen": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_email(arretes):
    destinataires = [a.strip() for a in EMAIL_TO.split(",")]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Nouveaux arretes prefectoraux Loiret ({len(arretes)})"
    msg["From"] = EMAIL_FROM
    msg["To"] = ", ".join(destinataires)
    lignes = []
    for a in arretes:
        lignes.append(f"\n{a['titre']}\n{a['contenu']}")
        if a.get("pdf"):
            lignes.append(f"PDF : {a['pdf']}")
    texte = "Nouveaux arretes prefectoraux du Loiret :\n" + "\n".join(lignes)
    msg.attach(MIMEText(texte, "plain", "utf-8"))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(EMAIL_FROM, EMAIL_PASS)
        s.sendmail(EMAIL_FROM, destinataires, msg.as_string())
    print(f"Email envoye : {len(arretes)} arrete(s) a {len(destinataires)} destinataire(s)")

def main():
    state = load_state()
    seen = set(state["seen"])
    tous = []
    for url in get_url():
        tous += fetch_arretes(url)
    vus = set()
    uniques = []
    for a in tous:
        if a["id"] not in vus:
            vus.add(a["id"])
            uniques.append(a)
    nouveaux = [a for a in uniques if a["id"] not in seen]
    print(f"Trouve : {len(uniques)} arretes, {len(nouveaux)} nouveaux")
    if nouveaux:
        send_email(nouveaux)
        state["seen"] = list(seen | {a["id"] for a in nouveaux})
        save_state(state)

main()
