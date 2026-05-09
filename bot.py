import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import os
TOKEN = os.environ.get("TOKEN")
TON_CHAT_ID = int(os.environ.get("CHAT_ID"))

WATCHLIST = {
    "KALRAY":  "ALKAL.PA",
    "2CRSI":   "AL2SI.PA",
    "SOITEC":  "SOI.PA",
    "RIBER":   "ALRIB.PA",
    "SEMCO":   "ALSEM.PA",
    "NEXANS":  "NEX.PA",
    "VUSION":  "VU.PA",
    "STM":     "STM.PA",
}

portfolio = {}

async def cours(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = "📊 *Cours en temps réel*\n\n"
    for nom, ticker in WATCHLIST.items():
        try:
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
            price = yf.Ticker(WATCHLIST[nom]).fast_info["last_price"]
            pv  = (price - pos["prix_achat"]) * pos["qty"]
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
        parts = update.message.text.split()
        valeur = parts[1].upper()
        if valeur in portfolio:
            pos = portfolio.pop(valeur)
            await update.message.reply_text(f"✅ Position {valeur} clôturée (était {pos['qty']} titres @ {pos['prix_achat']:.2f}€)")
        else:
            await update.message.reply_text(f"❌ {valeur} non trouvé dans le portefeuille")
    except:
        await update.message.reply_text("Format : /vente KALRAY")

async def alerte_auto(ctx: ContextTypes.DEFAULT_TYPE):
    SEUILS = {
        "KALRAY": {"stop": 0.75, "obj": 1.50},
        "2CRSI":  {"stop": 0.75, "obj": 1.50},
        "RIBER":  {"stop": 0.75, "obj": 2.00},
        "SOITEC": {"stop": 0.75, "obj": 1.40},
    }
    for nom, pos in portfolio.items():
        if nom not in SEUILS:
            continue
        try:
            price = yf.Ticker(WATCHLIST[nom]).fast_info["last_price"]
            ratio = price / pos["prix_achat"]
            if ratio <= SEUILS[nom]["stop"]:
                await ctx.bot.send_message(chat_id=TON_CHAT_ID,
                    text=f"🔴 STOP {nom} : {price:.2f}€ — Stop-loss -25% déclenché !")
            elif ratio >= SEUILS[nom]["obj"]:
                await ctx.bot.send_message(chat_id=TON_CHAT_ID,
                    text=f"🟢 OBJECTIF {nom} : {price:.2f}€ — Prise de profit conseillée !")
        except:
            pass

async def aide(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = """📱 *Commandes disponibles*

/cours — Cours en temps réel
/portefeuille — Valeur et PV de tes positions
/achat VALEUR QTY PRIX — Ex: /achat KALRAY 10 7.50
/vente VALEUR — Ex: /vente KALRAY
/aide — Ce message"""
    await update.message.reply_markdown(msg)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("cours", cours))
app.add_handler(CommandHandler("portefeuille", portefeuille))
app.add_handler(CommandHandler("achat", achat))
app.add_handler(CommandHandler("vente", vente))
app.add_handler(CommandHandler("aide", aide))
import asyncio

async def main():
    async with app:
        await app.initialize()
        app.job_queue.run_repeating(alerte_auto, interval=300, first=10)
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()

asyncio.run(main())