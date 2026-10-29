#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veille cyber automatique - Gabriel / Kapelgy
- Collecte les flux RSS/Atom cyber publics (CERT-FR, CISA, BleepingComputer, etc.)
- Genere un rapport Markdown pour chaque nouvelle news (resume, impact, tags)
- Tient une synthese quotidienne
- Tourne en continu (boucle) - lance-le avec launchd (Mac) ou systemd (Linux)
Aucune dependance externe : bibliotheque standard Python 3.9+ uniquement.
Option : si Ollama tourne en local, --ollama genere des resumes IA (sinon resumes extractifs).
"""

import argparse
import hashlib
import html
import json
import logging
import os
import re
import sys
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ------------------------------------------------------------------ config ---

BASE_DIR = Path(os.environ.get("VEILLE_DIR", Path.home() / "veille-cyber"))
RAPPORTS_DIR = BASE_DIR / "rapports"
STATE_FILE = BASE_DIR / "etat.json"
LOG_FILE = BASE_DIR / "veille.log"

INTERVALLE_DEFAUT = 1800          # 30 min entre deux passages
TIMEOUT_HTTP = 20                 # secondes
MAX_SEEN = 8000                   # taille max de la memoire anti-doublons
USER_AGENT = "Mozilla/5.0 (compatible; veille-cyber locale)"

FLUX = [
    ("CERT-FR (ANSSI)",   "https://www.cert.ssi.gouv.fr/feed/"),
    ("CISA",              "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
    ("BleepingComputer",  "https://www.bleepingcomputer.com/feed/"),
    ("The Hacker News",   "https://feeds.feedburner.com/TheHackersNews"),
    ("SecurityWeek",      "https://www.securityweek.com/feed/"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ("ZATAZ",             "https://www.zataz.com/feed/"),
    ("IT-Connect",        "https://www.it-connect.fr/feed/"),
]

# Tags de pertinence metier : (tag, mots-cles, explication "pourquoi ca compte")
REGLES_TAGS = [
    ("NIS2 / conformite",
     ["nis2", "nis 2", "dora", "rgpd", "gdpr", "directive", "conformite", "compliance", "anssi", "regulation", "reglementation"],
     "Sujet conformite/reglementaire : angle direct pour tes audits Kapelgy et le canal MSP (NIS2 oblige beaucoup de PME/ETI a se mettre en regle)."),
    ("PQC / crypto",
     ["post-quantum", "post quantum", "pqc", "kyber", "dilithium", "cryptographie", "chiffrement", "quantum", "quantique", "tls", "certificat"],
     "Crypto/PQC : coeur de l'offre Kapelgy (audit reseau + migration post-quantique), a suivre de pres."),
    ("MSP / clients",
     ["msp", "mssp", "managed service", "prestataire", "supply chain", "fournisseur", "pme", "smb"],
     "Impacte les MSP/prestataires : tes clients et prospects sont concernes, bon angle commercial."),
    ("Vulnerabilites / correctifs",
     ["vulnerabilit", "cve-", "cvss", "exploit", " rce", "remote code execution", "correctif", "patch tuesday", "mise a jour de securite", "security update", "fortinet", "vmware", "citrix"],
     "Correctif a deployer : pense a tes clients MSP/PME (fenetre d'exposition) et a tes audits (verifier que le patchement est suivi)."),
    ("Attaques / ransomware",
     ["ransomware", "rancongiciel", "cyberattaque", "cyberattack", "data breach", "fuite de donnees", "compromission", "phishing", "hameconnage", "botnet", "apt", "espion"],
     "Attaque en cours ou compromission : utile pour sensibiliser clients et eleves avec des cas reels et recents."),
    ("Cours B3",
     ["vpn", "openvpn", "dhcp", "dns", "active directory", "pare-feu", "firewall", "wireshark", "cisco", "linux", "debian", "ssh", "reseau", "network"],
     "Reutilisable en cours : colle aux sujets de tes TPs B3 (reseau, services Linux, VPN, AD)."),
]

REGLES_SEVERITE = [
    ("CRITIQUE", ["critique", "critical", "zero-day", "0day", "0-day", "actively exploited", "activement exploite", "exploitee dans la nature", "known exploited", "kev", "cvss 9", "cvss 10", "alerte"]),
    ("ELEVE",    ["eleve", "high", "important", "severe", "ransomware", "rancongiciel", "compromission", "fuite de donnees", "data breach", "breach"]),
]

# --------------------------------------------------------------- utilitaires -

def nettoie_html(texte):
    if not texte:
        return ""
    texte = re.sub(r"(?s)<(script|style).*?</\1>", " ", texte)
    texte = re.sub(r"(?s)<[^>]+>", " ", texte)
    texte = html.unescape(texte)
    return re.sub(r"\s+", " ", texte).strip()


def resume_extractif(texte, max_car=600):
    """Resume honnete : les 2-3 premieres phrases du texte source."""
    phrases = re.split(r"(?<=[.!?])\s+", texte)
    out = ""
    for p in phrases:
        if len(out) + len(p) > max_car and out:
            break
        out = (out + " " + p).strip()
    if not out:
        out = texte[:max_car]
    return out


def resume_ollama(modele, titre, texte):
    """Resume via un Ollama local (http://localhost:11434). Leve une exception si indisponible."""
    prompt = (
        "Tu es un analyste cybersecurite. Resume en francais, en 4 phrases maximum, "
        "cette actualite cyber pour un dirigeant de societe d'audit reseau qui donne aussi des cours.\n\n"
        f"Titre : {titre}\n\nTexte : {texte[:4000]}"
    )
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=json.dumps({"model": modele, "prompt": prompt, "stream": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8")).get("response", "").strip()


def tags_et_severite(texte_complet):
    bas = texte_complet.lower()
    tags, raisons = [], []
    for tag, mots, pourquoi in REGLES_TAGS:
        if any(m in bas for m in mots):
            tags.append(tag)
            raisons.append(pourquoi)
    severite = "MODERE"
    for niveau, mots in REGLES_SEVERITE:
        if any(m in bas for m in mots):
            severite = niveau
            break
    return severite, tags, raisons


def identifiant(item):
    brut = item.get("guid") or item.get("lien") or (item.get("titre", "") + item.get("date", ""))
    return hashlib.sha256(brut.encode("utf-8", "ignore")).hexdigest()[:24]


def slug(titre):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", titre.lower()).strip("-")
    return (s[:60] or "sans-titre")

# ------------------------------------------------------------- lecture flux --

def telecharge(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT_HTTP) as r:
        return r.read()


def parse_flux(nom, contenu):
    """Parse RSS 2.0 et Atom. Renvoie une liste de dicts titre/lien/date/desc/guid."""
    items = []
    try:
        racine = ET.fromstring(contenu)
    except ET.ParseError as e:
        logging.warning("%s : flux illisible (%s)", nom, e)
        return items

    def texte_de(el, *chemins):
        for c in chemins:
            n = el.find(c)
            if n is not None and n.text:
                return n.text.strip()
            if n is not None and c.endswith("link"):
                href = n.get("href")
                if href:
                    return href.strip()
        return ""

    ATOM = "{http://www.w3.org/2005/Atom}"
    for it in racine.iter("item"):  # RSS 2.0
        items.append({
            "titre": texte_de(it, "title"),
            "lien": texte_de(it, "link", "guid"),
            "date": texte_de(it, "pubDate", "date", "{http://purl.org/dc/elements/1.1/}date"),
            "desc": texte_de(it, "description", "{http://purl.org/rss/1.0/modules/content/}encoded"),
            "guid": texte_de(it, "guid"),
        })
    for it in racine.iter(ATOM + "entry"):  # Atom
        lien = ""
        for l in it.findall(ATOM + "link"):
            if l.get("rel") in (None, "alternate") and l.get("href"):
                lien = l.get("href")
                break
        items.append({
            "titre": texte_de(it, ATOM + "title"),
            "lien": lien,
            "date": texte_de(it, ATOM + "published", ATOM + "updated"),
            "desc": texte_de(it, ATOM + "summary", ATOM + "content"),
            "guid": texte_de(it, ATOM + "id"),
        })
    return [i for i in items if i["titre"]]

# ------------------------------------------------------------------ etat -----

def charge_etat():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"vus": []}


def sauve_etat(etat):
    etat["vus"] = etat["vus"][-MAX_SEEN:]
    STATE_FILE.write_text(json.dumps(etat, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------------------------------------------------------------- rapports ---

def ecrit_rapport(item, source, severite, tags, raisons, resume, mode_resume):
    jour = datetime.now().strftime("%Y-%m-%d")
    dossier = RAPPORTS_DIR / jour
    dossier.mkdir(parents=True, exist_ok=True)
    heure = datetime.now().strftime("%Hh%M")
    chemin = dossier / f"{heure}-{slug(item['titre'])}.md"
    tags_txt = ", ".join(tags) if tags else "General cyber"
    pourquoi = "\n".join(f"- {r}" for r in raisons) or "- Actualite cyber generale, a survoler."
    corps = f"""# {item['titre']}

- **Source** : {source}
- **Date** : {item['date'] or 'inconnue'}
- **Lien** : {item['lien']}
- **Severite estimee** : {severite}
- **Pertinence** : {tags_txt}
- **Resume** : {mode_resume}

## Resume

{resume}

## Pourquoi ca compte pour toi

{pourquoi}
"""
    chemin.write_text(corps, encoding="utf-8")
    return chemin


def maj_synthese(nouveaux):
    """Ajoute les nouvelles entrees a la synthese du jour."""
    if not nouveaux:
        return
    jour = datetime.now().strftime("%Y-%m-%d")
    chemin = RAPPORTS_DIR / f"synthese-{jour}.md"
    neuf = not chemin.exists()
    with chemin.open("a", encoding="utf-8") as f:
        if neuf:
            f.write(f"# Synthese veille cyber du {jour}\n\n")
        for n in nouveaux:
            f.write(f"## [{n['severite']}] {n['titre']}\n")
            f.write(f"- {n['source']} - {n['tags']} - [rapport complet]({jour}/{n['rapport'].name})\n")
            f.write(f"- {n['lien']}\n\n")

# ------------------------------------------------------------------ moteur ---

def passage(args):
    etat = charge_etat()
    vus = set(etat["vus"])
    nouveaux = []
    for nom, url in FLUX:
        try:
            contenu = telecharge(url)
        except Exception as e:
            logging.warning("%s : telechargement impossible (%s)", nom, e)
            continue
        for item in parse_flux(nom, contenu):
            iid = identifiant(item)
            if iid in vus:
                continue
            vus.add(iid)
            etat["vus"].append(iid)
            texte = nettoie_html(item.get("desc", ""))
            severite, tags, raisons = tags_et_severite(item["titre"] + " " + texte)
            mode_resume = "extractif (premieres phrases de l'article)"
            resume = resume_extractif(texte)
            if args.ollama:
                try:
                    resume = resume_ollama(args.ollama, item["titre"], texte)
                    mode_resume = f"IA locale Ollama ({args.ollama})"
                except Exception as e:
                    logging.info("Ollama indisponible, resume extractif (%s)", e)
            chemin = ecrit_rapport(item, nom, severite, tags, raisons, resume, mode_resume)
            nouveaux.append({
                "titre": item["titre"], "source": nom, "severite": severite,
                "tags": ", ".join(tags) if tags else "General", "lien": item["lien"],
                "rapport": chemin,
            })
            logging.info("[%s] %s (%s)", severite, item["titre"], nom)
    maj_synthese(nouveaux)
    sauve_etat(etat)
    logging.info("Passage termine : %d nouvelle(s) news.", len(nouveaux))
    return len(nouveaux)


def main():
    ap = argparse.ArgumentParser(description="Veille cyber automatique (Mac + Linux)")
    ap.add_argument("--once", action="store_true", help="un seul passage puis sortie")
    ap.add_argument("--intervalle", type=int, default=INTERVALLE_DEFAUT,
                    help="secondes entre passages (defaut 1800)")
    ap.add_argument("--ollama", metavar="MODELE", default=None,
                    help="modele Ollama local pour les resumes IA (ex: llama3.1)")
    args = ap.parse_args()

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    RAPPORTS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)],
    )
    logging.info("Demarrage veille cyber - dossier : %s", BASE_DIR)

    if args.once:
        passage(args)
        return
    while True:
        try:
            passage(args)
        except Exception as e:
            logging.error("Erreur passage : %s", e)
        time.sleep(args.intervalle)


if __name__ == "__main__":
    main()
