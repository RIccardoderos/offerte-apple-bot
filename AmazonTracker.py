import os
import re
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

PRODOTTI_APPLE = [
    {
        "nome": "MacBook Air M5",
        "url": "https://www.amazon.it/dp/B0GR1NGNSB",
        "prezzo_target": 1250.00,
        "prezzo_minimo_atteso": 700.00
    },
    {
        "nome": "iPad A16",
        "url": "https://www.amazon.it/dp/B0DZ75RKZH",
        "prezzo_target": 400.00,
        "prezzo_minimo_atteso": 200.00
    },
    {
        "nome": "MacBook Pro M5 Pro",
        "url": "https://www.amazon.it/dp/B0GR1B65JZ",
        "prezzo_target": 2000.00,
        "prezzo_minimo_atteso": 1200.00
    },
    {
        "nome": "PS5 con 2 controller",
        "url": "https://www.amazon.it/dp/B0CLT54ZNZ",
        "prezzo_target": 400.00,
        "prezzo_minimo_atteso": 250.00
    }
]

def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Errore: TELEGRAM_TOKEN o CHAT_ID non impostati.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Errore nell'invio a Telegram: {e}")

def pulisci_prezzo(testo):
    if not testo:
        return None
    testo_pulito = re.sub(r'[^\d,]', '', testo.strip()).replace(',', '.')
    try:
        valore = float(testo_pulito)
        return valore if valore > 0 else None
    except ValueError:
        return None

def estrai_prezzo_principale(soup, prezzo_minimo_atteso):
    # Cerca solo dentro i contenitori principali della scheda prodotto (mai sull'intera pagina)
    contenitori_principali = [
        "#corePriceDisplay_desktop_feature_div",
        "#corePrice_feature_div",
        "#desktop_buybox",
        "#buybox"
    ]

    for contenitore_sel in contenitori_principali:
        contenitore = soup.select_one(contenitore_sel)
        if not contenitore:
            continue

        for sub_sel in ["span.a-price.aok-align-center span.a-offscreen", "span.a-price span.a-offscreen"]:
            elemento = contenitore.select_one(sub_sel)
            if elemento:
                valore = pulisci_prezzo(elemento.text)
                if valore and valore >= prezzo_minimo_atteso:
                    return valore

    return None

def check_amazon_prices():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.it/"
    }

    with requests.Session(impersonate="chrome") as session:
        for prodotto in PRODOTTI_APPLE:
            print(f"Controllo in corso per: {prodotto['nome']}...")
            try:
                response = session.get(prodotto["url"], headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                current_price = estrai_prezzo_principale(soup, prodotto["prezzo_minimo_atteso"])

                if current_price is not None:
                    print(f"[{time.strftime('%H:%M:%S')}] Prezzo attuale: {current_price}€ (Target: {prodotto['prezzo_target']}€)")

                    if current_price <= prodotto["prezzo_target"]:
                        msg = (
                            f"🚨 <b>CALO DI PREZZO!</b> 🚨\n\n"
                            f"📦 <b>{prodotto['nome']}</b> è sceso a <b>{current_price}€</b> "
                            f"(il tuo target era {prodotto['prezzo_target']}€)!\n\n"
                            f"🛒 <a href='{prodotto['url']}'>Compra subito su Amazon</a>"
                        )
                        send_telegram_message(msg)
                else:
                    cap_attuale = soup.select_one("#glow-ingress-line2")
                    cap_str = cap_attuale.get_text(strip=True) if cap_attuale else "Sconosciuto"
                    avail = soup.select_one("#availability")
                    avail_str = avail.get_text(" ", strip=True)[:80] if avail else "Box disponibilità assente"
                    print(f"Prezzo non trovato per {prodotto['nome']} | Posizione: '{cap_str}' | Stato: '{avail_str}'")

            except Exception as e:
                print(f"Errore durante lo scraping di {prodotto['nome']}: {e}")

            time.sleep(random.uniform(5, 9))

if __name__ == "__main__":
    print("Avvio scansione singola prodotti per GitHub Actions...")
    check_amazon_prices()
    print("Scansione completata.")
