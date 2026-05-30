#!/usr/bin/env python3
"""
Twitter/X → Telegram Bot
Monitora perfis do Twitter e envia novos tweets via Telegram
"""

import time
import json
import os
import sys
import requests
from datetime import datetime
from ntscraper import Nitter

# ============================================================
#  ⚙️  CONFIGURAÇÕES
#  No Railway: defina as variáveis de ambiente no painel.
#  Localmente: edite os valores padrão entre aspas.
# ============================================================

PROFILES_TO_MONITOR = [
    "MonThreat",           # ThreatMon
    "TMRansomMon",         # ThreatMon Ransomware Monitoring
    "VECERTRadar",         # VECERT Analyzer
    "sansforensics",       # SANS DFIR
    "fastfire",            # fastfire
    "FalconFeedsio",       # FalconFeeds.io
    "AuditG63247",         # Audit Général
    "vxunderground",       # vx-underground
    "Dinosn",              # Nicolas Krassas
    "DailyDarkWeb",        # Dark Web Intelligence
    "ahmedmekki",          # Ahmed Mekki
    "rahultyagihacks",     # Rahul Tyagi
    "ido_cohen2",          # DarkFeed
    "cyb3rops",            # Florian Roth
    "BlackHatEvents",      # Black Hat
    "TheDFIRReport",       # The DFIR Report
    "Hacker0x01",          # HackerOne
]

# Lê credenciais das variáveis de ambiente (Railway) ou usa valor padrão (local)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "SEU_TOKEN_AQUI")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "SEU_CHAT_ID_AQUI")
CHECK_INTERVAL     = int(os.environ.get("CHECK_INTERVAL", "300"))
STATE_FILE         = "seen_tweets.json"

# Validação na inicialização
if "SEU_TOKEN" in TELEGRAM_BOT_TOKEN or "SEU_CHAT" in TELEGRAM_CHAT_ID:
    print("ERRO: Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes de rodar.")
    print("   No Railway: va em Variables e adicione as duas variaveis.")
    sys.exit(1)

# ============================================================

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def load_seen_ids() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(ids: set):
    with open(STATE_FILE, "w") as f:
        json.dump(list(ids), f)


def fetch_latest_tweets(username: str, scraper: Nitter) -> list:
    try:
        result = scraper.get_tweets(username, mode="user", number=5)
        return result.get("tweets", [])
    except Exception as e:
        print(f"[ERRO] Falha ao buscar tweets de @{username}: {e}")
        return []


def get_tweet_id(tweet: dict) -> str:
    link = tweet.get("link", "")
    return link.split("/")[-1].split("#")[0]


def get_tweet_link(tweet: dict, username: str) -> str:
    tweet_id = get_tweet_id(tweet)
    return f"https://twitter.com/{username}/status/{tweet_id}"


def get_tweet_image(tweet: dict):
    photos = tweet.get("photos", [])
    if photos:
        return photos[0]
    return None


def format_date(tweet: dict) -> str:
    date_str = tweet.get("date", "")
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%d/%m/%Y às %H:%M")
    except Exception:
        return date_str


def send_telegram_text(message: str):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=15)
    if not resp.ok:
        print(f"  Erro ao enviar texto: {resp.text}")
    return resp.ok


def send_telegram_photo(image_url: str, caption: str):
    url = f"{TELEGRAM_API}/sendPhoto"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": image_url,
        "caption": caption,
        "parse_mode": "HTML",
    }
    resp = requests.post(url, json=payload, timeout=15)
    if not resp.ok:
        print(f"  Imagem falhou ({resp.status_code}), enviando so texto...")
        return send_telegram_text(caption)
    return resp.ok


def build_caption(tweet: dict, username: str) -> str:
    text = tweet.get("text", "").strip()
    link = get_tweet_link(tweet, username)
    date = format_date(tweet)
    return (
        f"🐦 <b>@{username}</b> publicou:\n\n"
        f"{text}\n\n"
        f"📅 {date}\n"
        f"🔗 <a href='{link}'>Ver no Twitter/X</a>"
    )


def process_tweet(tweet: dict, username: str):
    caption   = build_caption(tweet, username)
    image_url = get_tweet_image(tweet)
    if image_url:
        ok = send_telegram_photo(image_url, caption)
    else:
        ok = send_telegram_text(caption)
    if ok:
        print(f"  Enviado para o Telegram!")
    time.sleep(1)


def main():
    print("=" * 55)
    print("  Twitter -> Telegram Bot")
    print("=" * 55)
    print(f"  Monitorando: {len(PROFILES_TO_MONITOR)} perfis")
    print(f"  Intervalo:   {CHECK_INTERVAL}s ({CHECK_INTERVAL // 60} min)")
    print("=" * 55)

    scraper   = Nitter(log_level=0, skip_instance_check=False)
    seen_ids  = load_seen_ids()
    first_run = len(seen_ids) == 0

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] Verificando tweets...")

        for username in PROFILES_TO_MONITOR:
            tweets = fetch_latest_tweets(username, scraper)
            print(f"  @{username}: {len(tweets)} tweet(s)")

            for tweet in tweets:
                tweet_id = get_tweet_id(tweet)
                if not tweet_id or tweet_id in seen_ids:
                    continue

                seen_ids.add(tweet_id)

                if first_run:
                    print(f"    [1a execucao] Mapeando: {tweet_id}")
                    continue

                print(f"    Novo tweet: {tweet_id}")
                process_tweet(tweet, username)

        save_seen_ids(seen_ids)

        if first_run:
            first_run = False
            print("\n  Primeira execucao concluida. Tweets existentes mapeados.")
            print("  Aguardando novos tweets a partir de agora...")

        print(f"  Proxima verificacao em {CHECK_INTERVAL}s...")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
