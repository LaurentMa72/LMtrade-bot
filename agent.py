import time, json
import yfinance as yf
import requests
from datetime import datetime

TOKEN = "8642872800:AAE4VeTrxAJ2m_i6IPtAzf-oJ7aY0l3Xnok"
CHAT_ID = "5866688042"
ANTHROPIC_KEY = "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"

WATCHLIST = {
    "KALRAY": "ALKAL.PA",
    "2CRSI":  "AL2SI.PA",
    "SOITEC": "SOI.PA",
    "RIBER":  "ALRIB.PA",
    "SEMCO":  "ALSEM.PA",
    "NEXANS": "NEX.PA",
    "VUSION": "VU.PA",
    "STM":    "STMPA.PA",
}

BUDGET_PAR_LIGNE = 100

def get_indicateurs(ticker):
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="3mo", interval="1d")
        if hist.empty or len(hist) < 21:
            return None
        close = hist["Close"]
        volume = hist["Volume"]
        mm20 = close.rolling(20).mean().iloc[-1]
        mm50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
        prix = close.iloc[-1]
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)
        vol_actuel = int(volume.iloc[-1])
        vol_moyen = int(volume.rolling(20).mean().iloc[-1])
        return {
            "prix": round(prix, 2),
            "mm20": round(mm20, 2),
            "mm50": round(mm50, 2) if mm50 else None,
            "rsi": rsi,
            "volume": vol_actuel,
            "volume_moyen": vol_moyen,
            "croisement_haussier": bool(mm20 > mm50) if mm50 else None
        }
    except Exception as e:
        print(f"     Erreur indicateurs {ticker}: {e}")
        return None

def get_carnet_ordres(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.fast_info
        bid = round(info.get("bid", 0), 2)
        ask = round(info.get("ask", 0), 2)
        bid_size = info.get("bidSize", 0)
        ask_size = info.get("askSize", 0)

        if not bid or not ask:
            # Fallback : estimer depuis le prix
            prix = info.get("last_price", 0)
            bid = round(prix * 0.998, 2)
            ask = round(prix * 1.002, 2)
            bid_size = 0
            ask_size = 0

        spread = round(ask - bid, 3)
        spread_pct = round((spread / bid) * 100, 2) if bid else 0

        total = (bid_size or 0) + (ask_size or 0)
        pression_acheteurs = round((bid_size / total) * 100) if total > 0 else 50

        # Prix limite optimal : entre bid et ask, côté acheteur
        prix_limite_achat = round(bid + spread * 0.3, 2)
        prix_limite_vente = round(ask - spread * 0.3, 2)

        return {
            "bid": bid,
            "ask": ask,
            "bid_size": bid_size,
            "ask_size": ask_size,
            "spread": spread,
            "spread_pct": spread_pct,
            "pression_acheteurs": pression_acheteurs,
            "prix_limite_achat": prix_limite_achat,
            "prix_limite_vente": prix_limite_vente,
        }
    except Exception as e:
        print(f"     Erreur carnet {ticker}: {e}")
        return None

def analyser_avec_claude(nom, indicateurs, carnet):
    carnet_txt = ""
    if carnet:
        pression_label = "🟢 Acheteurs dominants" if carnet["pression_acheteurs"] > 55 else \
                         "🔴 Vendeurs dominants" if carnet["pression_acheteurs"] < 45 else \
                         "⚖️ Équilibré"
        carnet_txt = f"""
Carnet d'ordres :
- Bid : {carnet['bid']}€ ({carnet['bid_size']} titres)
- Ask : {carnet['ask']}€ ({carnet['ask_size']} titres)
- Spread : {carnet['spread']}€ ({carnet['spread_pct']}%)
- Pression : {pression_label} ({carnet['pression_acheteurs']}% acheteurs)
- Prix limite achat optimal : {carnet['prix_limite_achat']}€
- Prix limite vente optimal : {carnet['prix_limite_vente']}€"""

    prompt = f"""Tu es un assistant de trading spéculatif pour un portefeuille PEA français.

Valeur : {nom}
Indicateurs techniques :
- Prix actuel : {indicateurs['prix']}€
- RSI (14) : {indicateurs['rsi']}
- MM20 : {indicateurs['mm20']}€ / MM50 : {indicateurs['mm50']}€
- Croisement MM20>MM50 : {indicateurs['croisement_haussier']}
- Volume actuel : {indicateurs['volume']:,} / Moyen 20j : {indicateurs['volume_moyen']:,}
- Budget max : {BUDGET_PAR_LIGNE}€ / Frais : 2,50€
{carnet_txt}

Réponds UNIQUEMENT avec ce JSON sans texte autour :
{{"action": "ACHETER" ou "VENDRE" ou "ATTENDRE", "prix_entree": float ou null, "quantite": int ou null, "stop_loss": float ou null, "objectif": float ou null, "type_ordre": "LIMITE" ou "MARCHE", "raison": "explication courte max 20 mots"}}

Règles strictes :
- ACHETER uniquement si RSI < 35 ET volume > volume_moyen ET croisement haussier
- VENDRE uniquement si RSI > 70 strictement
- ATTENDRE dans tous les autres cas
- Si spread > 1% : toujours ordre LIMITE
- Si spread < 0.5% : ordre MARCHE possible
- Prix entrée achat = prix_limite_achat du carnet si disponible, sinon cours actuel
- Prix entrée vente = prix_limite_vente du carnet si disponible, sinon cours actuel
- Quantité = floor(budget / prix_entree), minimum 1
- Stop = prix_entree * 0.75 / Objectif = prix_entree * 1.50"""

    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}]
    }
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers=headers, json=body, timeout=30)
    data = r.json()
    texte = data["content"][0]["text"].strip()
    texte = texte.replace("```json", "").replace("```", "").strip()
    return json.loads(texte)

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    })

def run_agent():
    maintenant = datetime.now()
    heure = maintenant.hour
   # if maintenant.weekday() >= 5:
    #    print("Week-end, agent en pause.")
     #   return
    if not (9 <= heure < 18):
        print(f"Hors séance ({heure}h), agent en pause.")
        return

    print(f"\n🤖 Analyse lancée à {maintenant.strftime('%H:%M')}")

    for nom, ticker in WATCHLIST.items():
        print(f"  → Analyse {nom}...")
        indicateurs = get_indicateurs(ticker)
        if not indicateurs:
            print(f"     Données indisponibles pour {nom}")
            continue

        carnet = get_carnet_ordres(ticker)
        if carnet:
            print(f"     Carnet : Bid {carnet['bid']}€ / Ask {carnet['ask']}€ / Spread {carnet['spread_pct']}%")

        try:
            signal = analyser_avec_claude(nom, indicateurs, carnet)
        except Exception as e:
            print(f"     Erreur Claude pour {nom}: {e}")
            continue

        action = signal.get("action", "ATTENDRE")
        print(f"     → {action} — RSI {indicateurs['rsi']}")

        if action in ["ACHETER", "VENDRE"]:
            emoji = "📈" if action == "ACHETER" else "📉"
            type_ordre = signal.get("type_ordre", "LIMITE")

            # Infos carnet dans le message
            carnet_msg = ""
            if carnet:
                pression = "🟢 Acheteurs" if carnet["pression_acheteurs"] > 55 else \
                           "🔴 Vendeurs" if carnet["pression_acheteurs"] < 45 else "⚖️ Équilibré"
                carnet_msg = f"""
📋 *Carnet d'ordres*
Bid : {carnet['bid']}€ | Ask : {carnet['ask']}€
Spread : {carnet['spread_pct']}% | {pression}"""

            msg = f"""🤖 *SIGNAL {nom}*

{emoji} *Action : {action}*
📝 Type ordre : *{type_ordre}*
💶 Prix d'entrée : {signal.get('prix_entree', '—')}€
📦 Quantité : {signal.get('quantite', '—')} titres
🛑 Stop-loss : {signal.get('stop_loss', '—')}€
🎯 Objectif : {signal.get('objectif', '—')}€
📊 RSI : {indicateurs['rsi']}
{carnet_msg}
💡 _{signal.get('raison', '')}_"""

            envoyer_telegram(msg)
            print(f"     ✅ Signal {action} envoyé sur Telegram")

if __name__ == "__main__":
    print("🚀 Agent de trading démarré")
    envoyer_telegram("🚀 *Agent LMTrade v2 démarré*\nCarnet d'ordres activé. Analyse toutes les heures en séance.")
    while True:
        run_agent()
        print("⏰ Prochaine analyse dans 60 min...")
        time.sleep(3600)