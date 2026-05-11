import time, json, os, threading
import requests
from datetime import datetime
import pytz
PARIS_TZ = pytz.timezone('Europe/Paris')

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")

BUDGET_PAR_LIGNE = 100
portfolio = {}

WATCHLIST = {
    "KALRAY":     "ALKAL.PA",
    "2CRSI":      "AL2SI.PA",
    "SOITEC":     "SOI.PA",
    "RIBER":      "ALRIB.PA",
    "SEMCO":      "ALSEM.PA",
    "NEXANS":     "NEX.PA",
    "VUSION":     "VU.PA",
    "STM":        "STMPA.PA",
    "NANOBIOTIX": "NANO.PA",
    "DBV":        "DBV.PA",
    "GENFIT":     "GNFT.PA",
    "VALLOUREC":  "VK.PA",
    "MAUREL":     "MAU.PA",
}

YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Erreur Telegram: {e}", flush=True)

def get_indicateurs(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo"
        r = requests.get(url, headers=YAHOO_HEADERS, timeout=15).json()
        result = r["chart"]["result"][0]
        closes = result["indicators"]["quote"][0]["close"]
        volumes = result["indicators"]["quote"][0]["volume"]
        closes = [c for c in closes if c is not None]
        volumes = [v for v in volumes if v is not None]
        if len(closes) < 21:
            return None
        prix = closes[-1]
        mm20 = sum(closes[-20:]) / 20
        mm50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        gains, losses = [], []
        for i in range(-14, 0):
            diff = closes[i] - closes[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)
        return {
            "prix": round(prix, 2),
            "mm20": round(mm20, 2),
            "mm50": round(mm50, 2) if mm50 else None,
            "rsi": rsi,
            "volume": int(volumes[-1]),
            "volume_moyen": int(sum(volumes[-20:]) / 20),
            "croisement_haussier": bool(mm20 > mm50) if mm50 else None
        }
    except Exception as e:
        print(f"Erreur indicateurs {symbol}: {e}", flush=True)
        return None

def get_carnet_ordres(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        r = requests.get(url, headers=YAHOO_HEADERS, timeout=15).json()
        meta = r["chart"]["result"][0]["meta"]
        prix = float(meta.get("regularMarketPrice", 0))
        bid = round(prix * 0.998, 2)
        ask = round(prix * 1.002, 2)
        spread = round(ask - bid, 3)
        spread_pct = round((spread / bid) * 100, 2) if bid else 0
        return {
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spread_pct": spread_pct,
            "prix_limite_achat": round(bid + spread * 0.3, 2),
            "prix_limite_vente": round(ask - spread * 0.3, 2),
        }
    except Exception as e:
        print(f"Erreur carnet {symbol}: {e}", flush=True)
        return None

def analyser_avec_claude(nom, indicateurs, carnet):
    carnet_txt = ""
    if carnet:
        carnet_txt = f"""
Carnet : Bid {carnet["bid"]}€ / Ask {carnet["ask"]}€ / Spread {carnet["spread_pct"]}%
Prix limite achat : {carnet["prix_limite_achat"]}€ / vente : {carnet["prix_limite_vente"]}€"""
    prompt = f"""Tu es un assistant de trading spéculatif PEA français.
Valeur : {nom}
Prix : {indicateurs["prix"]}€ | RSI : {indicateurs["rsi"]} | MM20 : {indicateurs["mm20"]}€ | MM50 : {indicateurs["mm50"]}€
Croisement MM20>MM50 : {indicateurs["croisement_haussier"]}
Volume : {indicateurs["volume"]:,} / Moyen 20j : {indicateurs["volume_moyen"]:,}
Budget : {BUDGET_PAR_LIGNE}€ / Frais : 2.50€{carnet_txt}

Réponds UNIQUEMENT avec ce JSON :
{{"action": "ACHETER" ou "VENDRE" ou "ATTENDRE", "prix_entree": float ou null, "quantite": int ou null, "stop_loss": float ou null, "objectif": float ou null, "type_ordre": "LIMITE" ou "MARCHE", "raison": "max 20 mots"}}

Règles : ACHETER si RSI<35 ET volume>volume_moyen ET croisement haussier. VENDRE si RSI>70. Sinon ATTENDRE.
Stop = prix*0.75. Objectif = prix*1.50. Quantite = floor(budget/prix)."""
    headers = {"x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    body = {"model": "claude-haiku-4-5", "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=30)
    data = r.json()
    texte = data["content"][0]["text"].strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texte)

def run_agent():
    print(f"run_agent appelé à {datetime.now().strftime('%H:%M:%S')}", flush=True)
    maintenant = datetime.now(PARIS_TZ)
    if maintenant.weekday() >= 5:
        print("Week-end, pause.", flush=True)
        return
    if not (9 <= maintenant.hour < 18):
        print(f"Hors séance ({maintenant.hour}h).", flush=True)
        return
    print(f"Analyse lancée à {maintenant.strftime('%H:%M')}", flush=True)
    for nom, symbol in WATCHLIST.items():
        print(f"  -> {nom}...", flush=True)
        indicateurs = get_indicateurs(symbol)
        if not indicateurs:
            continue
        carnet = get_carnet_ordres(symbol)
        try:
            signal = analyser_avec_claude(nom, indicateurs, carnet)
        except Exception as e:
            print(f"  Erreur Claude {nom}: {e}", flush=True)
            continue
        action = signal.get("action", "ATTENDRE")
        print(f"  {nom}: {action} RSI={indicateurs['rsi']}", flush=True)
        if action in ["ACHETER", "VENDRE"]:
            emoji = "📈" if action == "ACHETER" else "📉"
            carnet_msg = f"\nBid {carnet['bid']}€ | Ask {carnet['ask']}€ | Spread {carnet['spread_pct']}%" if carnet else ""
            msg = f"""🤖 *SIGNAL {nom}*

{emoji} *{action}* | {signal.get("type_ordre","LIMITE")}
💶 Prix : {signal.get("prix_entree","—")}€
📦 Quantité : {signal.get("quantite","—")} titres
🛑 Stop : {signal.get("stop_loss","—")}€
🎯 Objectif : {signal.get("objectif","—")}€
📊 RSI : {indicateurs["rsi"]}{carnet_msg}
💡 _{signal.get("raison","")}_"""
            envoyer_telegram(msg)

def lancer_agent():
    print("🚀 Agent démarré", flush=True)
    envoyer_telegram("🚀 *Agent LMTrade v4 démarré*\nTwelve Data + commandes Telegram actives.")
    while True:
        run_agent()
        print("⏰ Pause 60 min...", flush=True)
        time.sleep(3600)

if __name__ == "__main__":
    lancer_agent()
