import os
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
        print("Errore: TELEGRAM_TOKEN o CHAT_ID non impostati nelle variabili d'ambiente.")
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

def estrai_prezzo(soup):
    # Metodo 1: Struttura standard a-price-whole + a-price-fraction
    price_element = soup.find("span", {"class": "a-price-whole"})
    fraction_element = soup.find("span", {"class": "a-price-fraction"})

    if price_element:
        price_str = price_element.text.replace('.', '').replace(',', '').strip()
        fraction_str = fraction_element.text.strip() if fraction_element else "00"
        if price_str.isdigit():
            return float(f"{price_str}.{fraction_str}")

    # Metodo 2: Fallback su span.a-offscreen (usato spesso da Amazon nelle varianti mobile/desktop)
    offscreen_element = soup.select_one("#corePrice_feature_div span.a-offscreen, #corePriceDisplay_desktop_feature_div span.a-offscreen")
    if offscreen_element:
        raw_text = offscreen_element.text.replace('€', '').replace('.', '').replace(',', '.').strip()
        try:
            return float(raw_text)
        except ValueError:
            pass

    return None

def check_amazon_prices():
    # Non forziamo User-Agent o Accept-Encoding per lasciare che impersonate="chrome" li gestisca in modo coerente
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.it/",
        "Upgrade-Insecure-Requests": "1"
    }

    # Usiamo una Sessione per mantenere i cookie tra una richiesta e l'altra come un browser reale
    with requests.Session(impersonate="chrome") as session:
        # Visita preliminare alla homepage per ottenere i cookie di sessione base
        try:
            session.get("https://www.amazon.it/", headers=headers, timeout=15)
            time.sleep(random.uniform(2, 4))
        except Exception:
            pass

        for prodotto in PRODOTTI_APPLE:
            print(f"Controllo in corso per: {prodotto['nome']}...")
            
            try:
                response = session.get(prodotto["url"], headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, "html.parser")
                
                current_price = estrai_prezzo(soup)

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
                    # Controlla se è presente esplicitamente la parola captcha nel titolo o nel testo
                    page_title = soup.title.string.strip() if soup.title and soup.title.string else "Senza titolo"
                    print(f"Prezzo non trovato per {prodotto['nome']} (HTTP {response.status_code} - Titolo pagina: {page_title}).")
                    
            except Exception as e:
                print(f"Errore durante lo scraping di {prodotto['nome']}: {e}")
            
            # Breve pausa casuale tra una richiesta e l'altra
            time.sleep(random.uniform(5, 10))

if __name__ == "__main__":
    print("Avvio scansione singola prodotti per GitHub Actions...")
    check_amazon_prices()
    print("Scansione completata.")
