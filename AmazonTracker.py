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

def estrai_prezzo_pagina(soup):
    selettori = [
        "#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen",
        "#corePrice_feature_div span.a-price span.a-offscreen",
        "#tp_price_block_total_price_ww span.a-offscreen",
        ".apexPriceToPay span.a-offscreen",
        "#price_inside_buybox",
        "#newBuyBoxPrice"
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

def estrai_prezzo_ricerca_asin(session, asin, headers):
    """Aggira il blocco geografico USA sui prodotti Apple leggendo il prezzo dalla ricerca per ASIN."""
    search_url = f"https://www.amazon.it/s?k={asin}"
    resp = session.get(search_url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.content, "html.parser")
    # Cerca il blocco risultato con l'attributo data-asin esatto
    card = soup.select_one(f'div[data-asin="{asin}"]')
    if card:
        prezzo_el = card.select_one("span.a-price span.a-offscreen")
        if prezzo_el:
            return pulisci_prezzo(prezzo_el.text)
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
            asin_match = re.search(r'/dp/([A-Z0-9]{10})', prodotto["url"])
            asin = asin_match.group(1) if asin_match else ""

            try:
                response = session.get(prodotto["url"], headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                current_price = estrai_prezzo_pagina(soup)

                # Se Amazon nasconde il prezzo Apple nella pagina prodotto (IP USA), legge dalla ricerca ASIN
                if current_price is None and asin:
                    time.sleep(random.uniform(2, 4))
                    current_price = estrai_prezzo_ricerca_asin(session, asin, headers)

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
                    page_title = soup.title.string.strip() if soup.title and soup.title.string else "Senza titolo"
                    print(f"Prezzo non trovato per {prodotto['nome']} (HTTP {response.status_code} - Titolo: {page_title}).")
                    
            except Exception as e:
                print(f"Errore durante lo scraping di {prodotto['nome']}: {e}")
            
            time.sleep(random.uniform(5, 9))

if __name__ == "__main__":
    print("Avvio scansione singola prodotti per GitHub Actions...")
    check_amazon_prices()
    print("Scansione completata.")
