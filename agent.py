import time, json, os
import requests
from datetime import datetime

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")
TWELVE_KEY = os.environ.get("TWELVE_KEY")

WATCHLIST = {
    # IA / Semi
    "KALRAY":  "ALKAL",
    "2CRSI":   "AL2SI",
    "SOITEC":  "SOI",
    "RIBER":   "ALRIB",
    "SEMCO":   "ALSEM",
    "NEXANS":  "NEX",
    "VUSION":  "VU",
    "STM":     "STMPA",
    # Biotech spéculatif
    "NANOBIOTIX": "NANO",
    "DBV":        "DBV",
    "GENFIT":     "GNFT",
    "VALLOUREC":  "VK",
    "MAUREL":     "MAU",
}
EXCHANGE = "XPAR"
BUDGET_PAR_LIGNE = 100

def get_indicateurs(symbol):
    try:
        # Données historiques pour RSI et MM
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&exchange={EXCHANGE}&interval=1day&outputsize=60&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=15).json()
        if r.get("status") == "error":
            print(f"     Erreur Twelve Data: {r.get('message')}")
            return None

        valeurs = r["values"]
        closes = [float(v["close"]) for v in reversed(valeurs)]
        volumes = [float(v["volume"]) for v in reversed(valeurs)]

        if len(closes) < 21:
            return None

        prix = closes[-1]
        mm20 = sum(closes[-20:]) / 20
        mm50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None

        # RSI 14
        gains, losses = [], []
        for i in range(-14, 0):
            diff = closes[i] - closes[i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)

        vol_actuel = int(volumes[-1])
        vol_moyen = int(sum(volumes[-20:]) / 20)

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
        print(f"     Erreur indicateurs {symbol}: {e}")
        return None

def get_carnet_ordres(symbol):
    try:
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&exchange={EXCHANGE}&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=15).json()
        if r.get("status") == "error":
            return None

        bid = float(r.get("fifty_two_week", {}).get("low", 0) or 0)
        ask = float(r.get("fifty_two_week", {}).get("high", 0) or 0)
        prix = float(r.get("close", 0) or 0)

        # Estimation bid/ask depuis le prix
        bid = round(prix * 0.998, 2)
        ask = round(prix * 1.002, 2)
        spread = round(ask - bid, 3)
        spread_pct = round((spread / bid) * 100, 2) if bid else 0
        prix_limite_achat = round(bid + spread * 0.3, 2)
        prix_limite_vente = round(ask - spread * 0.3, 2)

        return {
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spread_pct": spread_pct,
            "pression_acheteurs": 50,
            "prix_limite_achat": prix_limite_achat,
            "prix_limite_vente": prix_limite_vente,
        }
    except Exception as e:
        print(f"     Erreur carnet {symbol}: {e}")
        return None

def analyser_avec_claude(nom, indicateurs, carnet):
    carnet_txt = ""
    if carnet:
        carnet_txt = f"""
Carnet d'ordres :
- Bid estimé : {carnet['bid']}€ / Ask estimé : {carnet['ask']}€
- Spread : {carnet['spread_pct']}%
- Prix limite achat optimal : {carnet['prix_limite_achat']}€
- Prix limite vente optimal : {carnet['prix_limite_vente']}€"""

    prompt = f"""Tu es un assistant de trading spéculatif pour un portefeuille PEA français.

Valeur : {nom}
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
- Prix entrée achat = prix_limite_achat / vente = prix_limite_vente
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
def run_agent():
    print(f"run_agent appelé à {datetime.now().strftime('%H:%M:%S')}", flush=True)
    maintenant = datetime.now()
   # maintenant = datetime.now()
    heure = maintenant.hour
    if maintenant.weekday() >= 5:
        print("Week-end, agent en pause.")
        return
    if not (9 <= heure < 18):
        print(f"Hors séance ({heure}h), agent en pause.")
        return

    print(f"\n🤖 Analyse lancée à {maintenant.strftime('%H:%M')}")

    for nom, symbol in WATCHLIST.items():
        print(f"  → Analyse {nom}...")
        indicateurs = get_indicateurs(symbol)
        if not indicateurs:
            print(f"     Données indisponibles pour {nom}")
            continue

        carnet = get_carnet_ordres(symbol)
        if carnet:
            print(f"     Prix : {indicateurs['prix']}€ | Bid {carnet['bid']}€ / Ask {carnet['ask']}€ | Spread {carnet['spread_pct']}%")

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
            carnet_msg = ""
            if carnet:
                carnet_msg = f"\n📋 Bid {carnet['bid']}€ | Ask {carnet['ask']}€ | Spread {carnet['spread_pct']}%"

            msg = f"""🤖 *SIGNAL {nom}*

{emoji} *Action : {action}*
📝 Type ordre : *{type_ordre}*
💶 Prix d'entrée : {signal.get('prix_entree', '—')}€
📦 Quantité : {signal.get('quantite', '—')} titres
🛑 Stop-loss : {signal.get('stop_loss', '—')}€
🎯 Objectif : {signal.get('objectif', '—')}€
📊 RSI : {indicateurs['rsi']}{carnet_msg}
💡 _{signal.get('raison', '')}_"""

            envoyer_telegram(msg)
            print(f"     ✅ Signal {action} envoyé sur Telegram")

# Import scanner
from scanner import scanner_marche, UNIVERS_SCAN


if __name__ == "__main__":
    import threading
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

    portfolio = {}

    async def cmd_aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        msg = """📱 *Commandes disponibles*

/cours — Cours en temps réel
/portefeuille — Valeur et PV de tes positions
/achat VALEUR QTY PRIX — Ex: /achat KALRAY 10 7.50
/vente VALEUR — Ex: /vente KALRAY
/signal — Déclencher une analyse immédiate
/aide — Ce message"""
        await update.message.reply_markdown(msg)

    async def cmd_cours(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        msg = "📊 *Cours en temps réel*\n\n"
        for nom, symbol in WATCHLIST.items():
            try:
                url = f"https://api.twelvedata.com/price?symbol={symbol}&exchange={EXCHANGE}&apikey={TWELVE_KEY}"
                r = requests.get(url, timeout=10).json()
                price = float(r["price"])
                msg += f"• {nom}: *{price:.2f} €*\n"
            except:
                msg += f"• {nom}: indisponible\n"
        await update.message.reply_markdown(msg)

    async def cmd_portefeuille(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not portfolio:
            await update.message.reply_text("Portefeuille vide. Utilise /achat KALRAY 10 7.50")
            return
        msg = "💼 *Mon portefeuille*\n\n"
        total_pv = 0
        for nom, pos in portfolio.items():
            try:
                url = f"https://api.twelvedata.com/price?symbol={WATCHLIST[nom]}&exchange={EXCHANGE}&apikey={TWELVE_KEY}"
                r = requests.get(url, timeout=10).json()
                price = float(r["price"])
                pv = (price - pos["prix_achat"]) * pos["qty"]
                pct = (price / pos["prix_achat"] - 1) * 100
                total_pv += pv
                signe = "🟢" if pv >= 0 else "🔴"
                msg += f"{signe} {nom}: {pos['qty']} x {price:.2f}€ | PV: {pv:+.2f}€ ({pct:+.1f}%)\n"
            except:
                msg += f"• {nom}: calcul impossible\n"
        msg += f"\n*PV total : {total_pv:+.2f} €*"
        await update.message.reply_markdown(msg)

    async def cmd_achat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            parts = update.message.text.split()
            valeur, qty, prix = parts[1].upper(), int(parts[2]), float(parts[3])
            portfolio[valeur] = {"qty": qty, "prix_achat": prix}
            await update.message.reply_text(f"✅ Enregistré : {qty} {valeur} @ {prix:.2f}€")
        except:
            await update.message.reply_text("Format : /achat KALRAY 10 7.50")

    async def cmd_vente(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        try:
            valeur = update.message.text.split()[1].upper()
            if valeur in portfolio:
                pos = portfolio.pop(valeur)
                await update.message.reply_text(f"✅ {valeur} clôturé ({pos['qty']} titres @ {pos['prix_achat']:.2f}€)")
            else:
                await update.message.reply_text(f"❌ {valeur} non trouvé")
        except:
            await update.message.reply_text("Format : /vente KALRAY")

    async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔄 Analyse en cours...")
        run_agent()
        await update.message.reply_text("✅ Analyse terminée.")

    def lancer_agent_en_fond():
        print("🚀 Agent de trading LMTrade v3 démarré — Twelve Data activé")
        envoyer_telegram("🚀 *Agent LMTrade v4 démarré*\nCommandes Telegram actives.")
        while True:
            run_agent()
            print("⏰ Prochaine analyse dans 60 min...")
            time.sleep(3600)

    # Lance l'agent dans un thread séparé
    t = threading.Thread(target=lancer_agent_en_fond, daemon=True)
    t.start()

    # Lance le bot Telegram dans le thread principal
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("aide", cmd_aide))
    app.add_handler(CommandHandler("cours", cmd_cours))
    app.add_handler(CommandHandler("portefeuille", cmd_portefeuille))
    app.add_handler(CommandHandler("achat", cmd_achat))
    app.add_handler(CommandHandler("vente", cmd_vente))
    app.add_handler(CommandHandler("signal", cmd_signal))
    app.run_polling()