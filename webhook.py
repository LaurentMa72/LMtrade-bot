import os, json
import requests
from flask import Flask, request

app = Flask(__name__)
TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }, timeout=10)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        valeur = data.get("valeur", "?")
        action = data.get("action", "?")
        prix = data.get("prix", "?")
        raison = data.get("raison", "Alerte TradingView")
        emoji = "📈" if action == "ACHETER" else "📉" if action == "VENDRE" else "🔔"
        msg = f"""📡 *ALERTE TRADINGVIEW*

{emoji} *{action} — {valeur}*
💶 Prix : {prix}€
💡 _{raison}_"""
        envoyer_telegram(msg)
        return "OK", 200
    except Exception as e:
        return str(e), 500

@app.route("/")
def index():
    return "LMTrade Webhook actif", 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
