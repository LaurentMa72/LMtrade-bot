import os, json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

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

portfolio = {}

# ─── Webhook TradingView ───────────────────────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body)

            valeur = data.get("valeur", "?")
            action = data.get("action", "?")
            prix = data.get("prix", "?")
            raison = data.get("raison", "Alerte TradingView")

            emoji = "📈" if action == "ACHETER" else "📉" if action == "VENDRE" else "🔔"
            msg = f"""📡 *ALERTE TRADINGVIEW*

{emoji} *{action} — {valeur}*
💶 Prix : {prix}€
💡 _{raison}_

⚡ Signal temps réel"""

            envoyer_telegram(msg)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            print(f"Webhook error: {e}")
            self.send_response(500)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silence les logs HTTP

def demarrer_webhook():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    print(f"🌐 Webhook actif sur port {port}")
    server.serve_forever()

# ─── Commandes Telegram ────────────────────────────────────────────────────────

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }, timeout=10)

async def cours(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = "📊 *Cours en temps réel*\n\n"
    for nom, ticker in WATCHLIST.items():
        try:
            import yfinance as yf
            price = yf.Ticker(ticker).fast_info["last_price"]
            msg += f"• {nom}: *{price:.2f} €*\n"
        except:
            msg += f"• {nom}: indisponible\n"
    await update.message.reply_markdown(msg)

async def portefeuille(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not portfolio:
        await update.message.reply_text("Portefeuille vide. Utilise /achat KALRAY 10 7.50")
        return
    msg = "💼 *Mon portefeuille*\n\n"
    total_pv = 0
    for nom, pos in portfolio.items():
        try:
            import yfinance as yf
            price = yf.Ticker(WATCHLIST[nom]).fast_info["last_price"]
            pv = (price - pos["prix_achat"]) * pos["qty"]
            pct = (price / pos["prix_achat"] - 1) * 100
            total_pv += pv
            signe = "🟢" if pv >= 0 else "🔴"
            msg += f"{signe} {nom}: {pos['qty']} x {price:.2f}€ | PV: {pv:+.2f}€ ({pct:+.1f}%)\n"
        except:
            msg += f"• {nom}: calcul impossible\n"
    msg += f"\n*PV total : {total_pv:+.2f} €*"
    await update.message.reply_markdown(msg)

async def achat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        valeur, qty, prix = parts[1].upper(), int(parts[2]), float(parts[3])
        portfolio[valeur] = {"qty": qty, "prix_achat": prix}
        await update.message.reply_text(f"✅ Enregistré : {qty} {valeur} @ {prix:.2f}€")
    except:
        await update.message.reply_text("Format : /achat KALRAY 10 7.50")

async def vente(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        valeur = update.message.text.split()[1].upper()
        if valeur in portfolio:
            pos = portfolio.pop(valeur)
            await update.message.reply_text(f"✅ {valeur} clôturé ({pos['qty']} titres @ {pos['prix_achat']:.2f}€)")
        else:
            await update.message.reply_text(f"❌ {valeur} non trouvé")
    except:
        await update.message.reply_text("Format : /vente KALRAY")

async def aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = """📱 *Commandes disponibles*

/cours — Cours en temps réel
/portefeuille — Valeur et PV de tes positions
/achat VALEUR QTY PRIX — Ex: /achat KALRAY 10 7.50
/vente VALEUR — Ex: /vente KALRAY
/aide — Ce message"""
    await update.message.reply_markdown(msg)

# ─── Lancement ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Démarre le webhook dans un thread séparé
    t = Thread(target=demarrer_webhook, daemon=True)
    t.start()

    print("🤖 Bot Telegram démarré")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("cours", cours))
    app.add_handler(CommandHandler("portefeuille", portefeuille))
    app.add_handler(CommandHandler("achat", achat))
    app.add_handler(CommandHandler("vente", vente))
    app.add_handler(CommandHandler("aide", aide))
    app.run_polling()