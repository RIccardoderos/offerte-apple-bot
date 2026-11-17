import os
import re
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

# Configurazioni Telegram lette in sicurezza dalle Secrets di GitHub
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# Lista dei prodotti da monitorare
PRODOTTI_APPLE = [
    {
        "nome": "MacBook Air M5",
        "url": "https://www.amazon.it/dp/B0GR1NGNSB",
        "prezzo_target": 1550.00
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
        "prezzo_target": 900.00
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

def estrai_prezzo(soup, html_text):
    # 1. Selettori CSS (sia desktop che mobile /gp/aw/d/)
    selettori_prezzo = [
        "#corePriceDisplay_desktop_feature_div span.a-price span.a-offscreen",
        "#corePrice_feature_div span.a-price span.a-offscreen",
        "#tp_price_block_total_price_ww span.a-offscreen",
        ".apexPriceToPay span.a-offscreen",
        "#priceblock_ourprice",
        "#price_inside_buybox",
        "#newBuyBoxPrice",
        "#olp_feature_div span.a-color-price",
        "span.a-price span.a-offscreen"
    ]

    for selettore in selettori_prezzo:
        elemento = soup.select_one(selettore)
        if elemento and elemento.text.strip():
            testo_pulito = re.sub(r'[^\d,]', '', elemento.text.strip()).replace(',', '.')
            try:
                valore = float(testo_pulito)
                if valore > 50:
                    return valore
            except ValueError:
                continue

    # 2. Fallback classico su a-price-whole + a-price-fraction (quello che funzionava per la PS5)
    price_element = soup.find("span", {"class": "a-price-whole"})
    fraction_element = soup.find("span", {"class": "a-price-fraction"})
    if price_element:
        price_str = re.sub(r'\D', '', price_element.text)
        fraction_str = re.sub(r'\D', '', fraction_element.text) if fraction_element else "00"
        if price_str:
            valore = float(f"{price_str}.{fraction_str}")
            if valore > 50:
                return valore

    # 3. Ricerca nei metadati JSON nascosti
    for pattern in [r'"priceAmount"\s*:\s*([0-9]+\.[0-9]{2})', r'"buyingPrice"\s*:\s*([0-9]+\.[0-9]{2})']:
        match = re.search(pattern, html_text)
        if match:
            try:
                valore = float(match.group(1))
                if valore > 50:
                    return valore
            except ValueError:
                continue

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
                # Tentativo 1: URL standard pulito
                response = session.get(prodotto["url"], headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                current_price = estrai_prezzo(soup, response.text)

                # Tentativo 2: Se non trova il prezzo (es. blocco geografico Apple), prova l'endpoint mobile /gp/aw/d/
                if current_price is None and asin:
                    mobile_url = f"https://www.amazon.it/gp/aw/d/{asin}"
                    resp_mob = session.get(mobile_url, headers=headers, timeout=15)
                    soup_mob = BeautifulSoup(resp_mob.content, "html.parser")
                    current_price = estrai_prezzo(soup_mob, resp_mob.text)

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
