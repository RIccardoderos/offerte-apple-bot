import os
import re
import time
import random
from curl_cffi import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# "prezzo_minimo_atteso" ora serve solo come controllo di sicurezza (soglia = 50% del valore),
# per scartare prezzi palesemente sbagliati (accessori, rate mensili, ecc.).
PRODOTTI_APPLE = [
    {
        "nome": "MacBook Air M5",
        "url": "https://www.amazon.it/dp/B0GR1NGNSB",
        "prezzo_target": 1250.00,
        "prezzo_minimo_atteso": 1150.00
    },
    {
        "nome": "iPad A16",
        "url": "https://www.amazon.it/dp/B0DZ75RKZH",
        "prezzo_target": 350.00,
        "prezzo_minimo_atteso": 300.00
    },
    {
        "nome": "MacBook Pro M5 Pro",
        "url": "https://www.amazon.it/dp/B0GR1B65JZ",
        "prezzo_target": 2000.00,
        "prezzo_minimo_atteso": 1700.00
    },
    {
        "nome": "PS5 con 2 controller",
        "url": "https://www.amazon.it/dp/B0CLT54ZNZ",
        "prezzo_target": 650.00,
        "prezzo_minimo_atteso": 550.00
    }
]

# Selettori testuali (span.a-offscreen), in ordine di affidabilità.
# ":not(.a-text-price)" esclude il prezzo barrato / di listino.
SELETTORI_PREZZO = [
    "#corePriceDisplay_desktop_feature_div .priceToPay span.a-offscreen",
    "#corePrice_feature_div .priceToPay span.a-offscreen",
    "#apex_desktop .priceToPay span.a-offscreen",
    "#corePriceDisplay_desktop_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
    "#corePrice_feature_div span.a-price:not(.a-text-price) span.a-offscreen",
    "#apex_desktop span.a-price:not(.a-text-price) span.a-offscreen",
    "#desktop_buybox span.a-price:not(.a-text-price) span.a-offscreen",
    "#buybox span.a-price:not(.a-text-price) span.a-offscreen",
    "#tp_price_block_total_price_ww span.a-offscreen",
    "#price_inside_buybox",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
]

# Campi nascosti che contengono il prezzo come numero (value="1299.00")
SELETTORI_INPUT_PREZZO = [
    "#twister-plus-price-data-price",
    "input[name='items[0.base][customerVisiblePrice][amount]']",
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
    """Converte '1.299,00 €' o '1299.00' in float."""
    if not testo:
        return None
    t = re.sub(r'[^\d,.]', '', testo.strip())
    if not t:
        return None
    if ',' in t:
        # formato italiano: 1.299,00
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(\.\d{3})+', t):
        # '1.299' senza decimali -> migliaia
        t = t.replace('.', '')
    try:
        valore = float(t)
        return valore if valore > 0 else None
    except ValueError:
        return None


def estrai_prezzo(soup, html, prezzo_minimo_atteso):
    """Restituisce (prezzo, fonte) oppure (None, None)."""
    soglia = prezzo_minimo_atteso * 0.5

    # 1) Selettori principali
    for sel in SELETTORI_PREZZO:
        for el in soup.select(sel):
            valore = pulisci_prezzo(el.get_text())
            if valore and valore >= soglia:
                return valore, sel

    # 2) Input nascosti con il prezzo
    for sel in SELETTORI_INPUT_PREZZO:
        el = soup.select_one(sel)
        if el and el.get("value"):
            valore = pulisci_prezzo(el["value"])
            if valore and valore >= soglia:
                return valore, sel

    # 3) Ultima spiaggia: JSON incorporato nella pagina
    m = re.search(r'"priceAmount"\s*:\s*([\d.]+)', html)
    if m:
        valore = pulisci_prezzo(m.group(1))
        if valore and valore >= soglia:
            return valore, "json:priceAmount"

    return None, None


def pagina_bloccata(response, html):
    """Riconosce captcha / blocchi anti-bot di Amazon."""
    if response.status_code in (403, 429, 503):
        return True
    h = html.lower()
    return ("validatecaptcha" in h
            or "api-services-support@amazon.com" in h
            or "captcha" in h and "productTitle" not in html)


def scarica_pagina(session, url, headers, tentativi=3):
    response, html = None, ""
    for n in range(1, tentativi + 1):
        response = session.get(url, headers=headers, timeout=20)
        html = response.text
        if not pagina_bloccata(response, html):
            return response, html, False
        print(f"  Tentativo {n}/{tentativi}: pagina bloccata (HTTP {response.status_code})")
        time.sleep(random.uniform(6, 12))
    return response, html, True


def check_amazon_prices():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.it/"
    }

    with requests.Session(impersonate="chrome") as session:
        for i, prodotto in enumerate(PRODOTTI_APPLE):
            print(f"Controllo in corso per: {prodotto['nome']}...")
            try:
                response, html, bloccata = scarica_pagina(session, prodotto["url"], headers)
                soup = BeautifulSoup(html, "html.parser")

                if bloccata:
                    print(f"BLOCCATO da Amazon per {prodotto['nome']} (HTTP {response.status_code}).")
                else:
                    current_price, fonte = estrai_prezzo(soup, html, prodotto["prezzo_minimo_atteso"])

                    if current_price is not None:
                        print(f"[{time.strftime('%H:%M:%S')}] {prodotto['nome']}: {current_price}€ "
                              f"(Target: {prodotto['prezzo_target']}€) [fonte: {fonte}]")

                        if current_price <= prodotto["prezzo_target"]:
                            msg = (
                                f"🚨 <b>CALO DI PREZZO!</b> 🚨\n\n"
                                f"📦 <b>{prodotto['nome']}</b> è sceso a <b>{current_price}€</b> "
                                f"(il tuo target era {prodotto['prezzo_target']}€)!\n\n"
                                f"🛒 <a href='{prodotto['url']}'>Compra subito su Amazon</a>"
                            )
                            send_telegram_message(msg)
                    else:
                        titolo = soup.title.get_text(strip=True) if soup.title else "nessun titolo"
                        avail = soup.select_one("#availability")
                        avail_str = avail.get_text(" ", strip=True)[:80] if avail else "Box disponibilità assente"
                        print(f"Prezzo non trovato per {prodotto['nome']} | HTTP {response.status_code} | "
                              f"Titolo: '{titolo[:60]}' | Stato: '{avail_str}'")

                # Salva l'HTML per capire cosa riceve davvero lo script (utile su GitHub Actions)
                if bloccata or (not bloccata and current_price is None):
                    with open(f"debug_{i}.html", "w", encoding="utf-8") as f:
                        f.write(html)

            except Exception as e:
                print(f"Errore durante lo scraping di {prodotto['nome']}: {e}")

            time.sleep(random.uniform(5, 9))


if __name__ == "__main__":
    print("Avvio scansione singola prodotti per GitHub Actions...")
    check_amazon_prices()
    print("Scansione completata.")
