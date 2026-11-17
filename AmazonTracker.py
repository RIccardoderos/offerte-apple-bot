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
        "prezzo_target": 1250.00
    },
    {
        "nome": "iPad A16",
        "url": "https://www.amazon.it/dp/B0DZ75RKZH",
        "prezzo_target": 400.00
    },
    {
        "nome": "MacBook Pro M5 Pro",
        "url": "https://www.amazon.it/dp/B0GR1B65JZ",
        "prezzo_target": 2000.00
    },
    {
        "nome": "PS5 con 2 controller",
        "url": "https://www.amazon.it/dp/B0CLT54ZNZ",
        "prezzo_target": 400.00
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
        return valore if valore > 50 else None
    except ValueError:
        return None

def imposta_posizione_italia(session, headers):
    """Carica il widget modale del CAP di Amazon.it e imposta 33100 con il token CSRF reale."""
    try:
        home = session.get("https://www.amazon.it/", headers=headers, timeout=15)
        time.sleep(random.uniform(1, 2))

        # Carica il popup "Scegli la tua posizione" per ottenere il vero anti-csrftoken-a2z
        popover_headers = headers.copy()
        popover_headers.update({
            "Accept": "text/html,*/*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.amazon.it/"
        })
        popover = session.get(
            "https://www.amazon.it/portal-migration/hz/glow/get-rendered-address-selections?deviceType=desktop&pageType=Gateway&storeContext=NoStoreName&actionSource=desktop-modal",
            headers=popover_headers,
            timeout=15
        )
        token_match = re.search(r'CSRF_TOKEN\s*:\s*"([^"]+)"', popover.text)
        if not token_match:
            token_match = re.search(r'"anti-csrftoken-a2z"\s*:\s*"([^"]+)"', popover.text)

        if token_match:
            post_headers = headers.copy()
            post_headers.update({
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "Origin": "https://www.amazon.it",
                "Referer": "https://www.amazon.it/",
                "X-Requested-With": "XMLHttpRequest",
                "anti-csrftoken-a2z": token_match.group(1)
            })
            payload = {
                "locationType": "LOCATION_INPUT",
                "zipCode": "33100",
                "storeContext": "generic",
                "deviceType": "web",
                "pageType": "Gateway",
                "actionSource": "glow"
            }
            res = session.post(
                "https://www.amazon.it/portal-migration/hz/glow/address-change?actionSource=glow",
                data=payload,
                headers=post_headers,
                timeout=15
            )
            print(f"Impostazione CAP 33100: HTTP {res.status_code}")
            time.sleep(random.uniform(1, 2))
        else:
            print("Token CSRF posizione non trovato nel modale.")
    except Exception as e:
        print(f"Errore impostazione CAP: {e}")

def estrai_prezzo_pagina(soup):
    selettori = [
        "#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen",
        "#corePrice_feature_div span.a-price span.a-offscreen",
        "#tp_price_block_total_price_ww span.a-offscreen",
        ".apexPriceToPay span.a-offscreen",
        "#price_inside_buybox",
        "#newBuyBoxPrice",
        "#olp_feature_div span.a-color-price",
        "#fod-cx-box span.a-price span.a-offscreen"
    ]
    for selettore in selettori:
        elemento = soup.select_one(selettore)
        if elemento:
            valore = pulisci_prezzo(elemento.text)
            if valore:
                return valore

    price_whole = soup.find("span", {"class": "a-price-whole"})
    price_fraction = soup.find("span", {"class": "a-price-fraction"})
    if price_whole:
        w = re.sub(r'\D', '', price_whole.text)
        f = re.sub(r'\D', '', price_fraction.text) if price_fraction else "00"
        if w:
            valore = float(f"{w}.{f}")
            if valore > 50:
                return valore
    return None

def check_amazon_prices():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.it/"
    }

    with requests.Session(impersonate="chrome") as session:
        imposta_posizione_italia(session, headers)

        for prodotto in PRODOTTI_APPLE:
            print(f"Controllo in corso per: {prodotto['nome']}...")
            try:
                response = session.get(prodotto["url"], headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                current_price = estrai_prezzo_pagina(soup)

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
                    # Diagnostica precisa per capire cosa vede Amazon sulla pagina
                    cap_attuale = soup.select_one("#glow-ingress-line2")
                    cap_str = cap_attuale.get_text(strip=True) if cap_attuale else "Sconosciuto"
                    avail = soup.select_one("#availability")
                    avail_str = avail.get_text(" ", strip=True)[:80] if avail else "Box disponibilità assente"
                    print(f"Prezzo non trovato per {prodotto['nome']} | Posizione rilevata: '{cap_str}' | Stato: '{avail_str}'")
                    
            except Exception as e:
                print(f"Errore durante lo scraping di {prodotto['nome']}: {e}")
            
            time.sleep(random.uniform(5, 9))

if __name__ == "__main__":
    print("Avvio scansione singola prodotti per GitHub Actions...")
    check_amazon_prices()
    print("Scansione completata.")
