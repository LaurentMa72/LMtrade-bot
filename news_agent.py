import os, time, requests
from datetime import datetime
import pytz

TOKEN = os.environ.get("TOKEN")
CHAT_ID_NEWS = "-1003947243575"  # Canal LMTrade Actualités
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")

PARIS_TZ = pytz.timezone("Europe/Paris")

WATCHLIST_NOMS = [
    "KALRAY", "2CRSI", "SOITEC", "RIBER", "SEMCO",
    "NEXANS", "VUSION", "STM", "NANOBIOTIX", "DBV",
    "GENFIT", "VALLOUREC", "MAUREL"
]

WATCHLIST_YAHOO = {
    "KALRAY": "ALKAL.PA", "2CRSI": "AL2SI.PA", "SOITEC": "SOI.PA",
    "RIBER": "ALRIB.PA", "SEMCO": "ALSEM.PA", "NEXANS": "NEX.PA",
    "VUSION": "VU.PA", "STM": "STMPA.PA", "NANOBIOTIX": "NANO.PA",
    "DBV": "DBV.PA", "GENFIT": "GNFT.PA", "VALLOUREC": "VK.PA",
    "MAUREL": "MAU.PA"
}

def envoyer_canal(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID_NEWS,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Erreur Telegram: {e}", flush=True)

def get_news_yahoo(ticker):
    try:
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={ticker}&newsCount=3&enableFuzzyQuery=false"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        news = r.get("news", [])
        return [{
            "titre": n.get("title", ""),
            "date": datetime.fromtimestamp(n.get("providerPublishTime", 0)).strftime("%d/%m %H:%M"),
            "source": n.get("publisher", "")
        } for n in news[:3]]
    except:
        return []

def get_earnings_calendar():
    try:
        tickers = ",".join(WATCHLIST_YAHOO.values())
        url = f"https://query1.finance.yahoo.com/v1/finance/search?q={tickers}&enableFuzzyQuery=false"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10).json()
        return r
    except:
        return {}

def analyser_news_avec_claude(nom, news_list):
    if not news_list:
        return None
    prompt = f"""Tu es un assistant de trading spéculatif PEA français.

Voici les dernières actualités pour {nom} :
{chr(10).join([f"- [{n['date']}] {n['titre']} ({n['source']})" for n in news_list])}

Analyse ces actualités et réponds en JSON :
{{"impact": "POSITIF" ou "NEGATIF" ou "NEUTRE", "urgence": "HAUTE" ou "NORMALE", "resume": "max 20 mots", "action": "SURVEILLER" ou "OPPORTUNITE" ou "RISQUE"}}

Critères : annonce contrat/partenariat/résultats positifs = POSITIF. Avertissement/perte/retard = NEGATIF."""

    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5",
        "max_tokens": 200,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=body, timeout=30)
        data = r.json()
        texte = data["content"][0]["text"].strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        import json
        return json.loads(texte)
    except:
        return None

def rapport_morning():
    maintenant = datetime.now(PARIS_TZ)
    if maintenant.weekday() >= 5:
        return
    if maintenant.hour != 8 or maintenant.minute > 15:
        return

    print(f"📰 Rapport morning lancé à {maintenant.strftime('%H:%M')}", flush=True)

    msg_header = f"📰 *ACTUALITÉS LMTrade — {maintenant.strftime('%d/%m/%Y')}*\n\n"
    alertes = []
    normales = []

    for nom in WATCHLIST_NOMS:
        ticker = WATCHLIST_YAHOO.get(nom)
        if not ticker:
            continue
        print(f"  -> News {nom}...", flush=True)
        news = get_news_yahoo(ticker)
        if not news:
            continue
        analyse = analyser_news_avec_claude(nom, news)
        if not analyse:
            continue

        impact = analyse.get("impact", "NEUTRE")
        urgence = analyse.get("urgence", "NORMALE")
        action = analyse.get("action", "SURVEILLER")
        resume = analyse.get("resume", "")

        emoji = "🟢" if impact == "POSITIF" else "🔴" if impact == "NEGATIF" else "⚪"
        ligne = f"{emoji} *{nom}* — {resume}\n   → _{action}_\n"

        if urgence == "HAUTE" or impact != "NEUTRE":
            alertes.append(ligne)
        else:
            normales.append(ligne)

        time.sleep(0.5)

    if not alertes and not normales:
        envoyer_canal(f"📰 *ACTUALITÉS — {maintenant.strftime('%d/%m/%Y')}*\n\n_Aucune actualité significative ce matin._")
        return

    msg = msg_header
    if alertes:
        msg += "🔔 *À surveiller en priorité :*\n\n"
        msg += "\n".join(alertes)
    if normales:
        msg += "\n📋 *Autres actualités :*\n\n"
        msg += "\n".join(normales[:5])

    msg += "\n_Source : Yahoo Finance_"
    envoyer_canal(msg)
    print("✅ Rapport morning envoyé", flush=True)

def surveiller_breaking_news():
    maintenant = datetime.now(PARIS_TZ)
    if maintenant.weekday() >= 5:
        return
    if not (8 <= maintenant.hour < 18):
        return

    for nom in WATCHLIST_NOMS:
        ticker = WATCHLIST_YAHOO.get(nom)
        if not ticker:
            continue
        news = get_news_yahoo(ticker)
        if not news:
            continue
        derniere = news[0]
        analyse = analyser_news_avec_claude(nom, [derniere])
        if not analyse:
            continue
        if analyse.get("urgence") == "HAUTE":
            emoji = "🟢" if analyse.get("impact") == "POSITIF" else "🔴"
            msg = f"""🚨 *BREAKING NEWS — {nom}*

{emoji} *{analyse.get('impact')}* — Urgence HAUTE
📰 {derniere['titre']}
💡 _{analyse.get('resume')}_
→ *{analyse.get('action')}*"""
            envoyer_canal(msg)
            print(f"  🚨 Breaking news {nom} envoyée", flush=True)
        time.sleep(0.3)

if __name__ == "__main__":
    print("📰 Agent Actualités LMTrade démarré", flush=True)
    envoyer_canal("📰 *Agent Actualités LMTrade démarré*\nRapport morning à 8h00, surveillance continue en séance.")
    
    derniere_breaking = 0
    
    while True:
        rapport_morning()
        
        maintenant = datetime.now(PARIS_TZ)
        if (maintenant.weekday() < 5 and 
            8 <= maintenant.hour < 18 and
            time.time() - derniere_breaking > 1800):
            surveiller_breaking_news()
            derniere_breaking = time.time()
        
        print(f"⏰ Prochaine vérification dans 15 min...", flush=True)
        time.sleep(900)
