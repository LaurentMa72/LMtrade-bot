import os, json, threading, time
import requests
from flask import Flask, request as freq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TWELVE_KEY = os.environ.get("TWELVE_KEY")
EXCHANGE = "XPAR"
portfolio = {}

WATCHLIST = {
    "KALRAY": "ALKAL", "2CRSI": "AL2SI", "SOITEC": "SOI",
    "RIBER": "ALRIB", "SEMCO": "ALSEM", "NEXANS": "NEX",
    "VUSION": "VU", "STM": "STMPA", "NANOBIOTIX": "NANO",
    "DBV": "DBV", "GENFIT": "GNFT", "VALLOUREC": "VK", "MAUREL": "MAU",
}

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Erreur Telegram: {e}", flush=True)

async def cmd_aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = """📱 *Commandes disponibles*

/cours — Cours en temps réel
/portefeuille — PV de tes positions
/achat VALEUR QTY PRIX — Ex: /achat KALRAY 10 7.50
/vente VALEUR — Ex: /vente KALRAY
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
    msg = "💼 *Portefeuille*\n\n"
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
            msg += f"{signe} {nom}: {pos[chr(39)+'qty'+chr(39)]} x {price:.2f}€ | PV: {pv:+.2f}€ ({pct:+.1f}%)\n"
        except:
            msg += f"• {nom}: erreur\n"
    msg += f"\n*PV total : {total_pv:+.2f} €*"
    await update.message.reply_markdown(msg)

async def cmd_achat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.split()
        valeur, qty, prix = parts[1].upper(), int(parts[2]), float(parts[3])
        portfolio[valeur] = {"qty": qty, "prix_achat": prix}
        await update.message.reply_text(f"✅ {qty} {valeur} @ {prix:.2f}€")
    except:
        await update.message.reply_text("Format : /achat KALRAY 10 7.50")

async def cmd_vente(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        valeur = update.message.text.split()[1].upper()
        if valeur in portfolio:
            portfolio.pop(valeur)
            await update.message.reply_text(f"✅ {valeur} clôturé")
        else:
            await update.message.reply_text(f"❌ {valeur} non trouvé")
    except:
        await update.message.reply_text("Format : /vente KALRAY")

if __name__ == "__main__":
    print("🤖 Bot Telegram démarré", flush=True)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("aide", cmd_aide))
    app.add_handler(CommandHandler("cours", cmd_cours))
    app.add_handler(CommandHandler("portefeuille", cmd_portefeuille))
    app.add_handler(CommandHandler("achat", cmd_achat))
    app.add_handler(CommandHandler("vente", cmd_vente))
    app.run_polling()
