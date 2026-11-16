import os
import requests
from bs4 import BeautifulSoup
import time
import random

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

def check_amazon_prices():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive"
    }

    for prodotto in PRODOTTI_APPLE:
        print(f"Controllo in corso per: {prodotto['nome']}...")
        
        try:
            response = requests.get(prodotto["url"], headers=headers, timeout=15)
            soup = BeautifulSoup(response.content, "html.parser")
            
            price_element = soup.find("span", {"class": "a-price-whole"})
            fraction_element = soup.find("span", {"class": "a-price-fraction"})

            if price_element:
                price_str = price_element.text.replace('.', '').replace(',', '').strip()
                fraction_str = fraction_element.text.strip() if fraction_element else "00"
                
                current_price = float(f"{price_str}.{fraction_str}")
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
                print(f"Prezzo non trovato per {prodotto['nome']}. Possibile blocco CAPTCHA o pagina non disponibile.")
                
        except Exception as e:
            print(f"Errore durante lo scraping di {prodotto['nome']}: {e}")
        
        # Breve pausa casuale tra una richiesta e l'altra
        time.sleep(random.randint(5, 10))

if __name__ == "__main__":
    print("Avvio scansione singola prodotti per GitHub Actions...")
    check_amazon_prices()
    print("Scansione completata.")