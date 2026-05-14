import time
import json
import os
import requests
from datetime import datetime
import pytz

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")
TWELVE_KEY = os.environ.get("TWELVE_KEY")

EXCHANGE = "XPAR"
BUDGET_PAR_LIGNE = 150
PARIS_TZ = pytz.timezone("Europe/Paris")

INDICES_REF = {
    "KALRAY": "TNO", "2CRSI": "TNO", "SOITEC": "TNO",
    "RIBER": "TNO", "SEMCO": "TNO", "STM": "TNO",
    "NANOBIOTIX": "HLT", "DBV": "HLT", "GENFIT": "HLT",
    "NEXANS": "ENE", "VUSION": "ENE",
    "VALLOUREC": "ENE", "MAUREL": "ENE",
}

WATCHLIST = {
    "KALRAY": "ALKAL",
    "2CRSI": "AL2SI",
    "SOITEC": "SOI",
    "RIBER": "ALRIB",
    "SEMCO": "ALSEM",
    "NEXANS": "NEX",
    "VUSION": "VU",
    "STM": "STMPA",
    "NANOBIOTIX": "NANO",
    "DBV": "DBV",
    "GENFIT": "GNFT",
    "VALLOUREC": "VK",
    "MAUREL": "MAU",
}


def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(
            url,
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception as e:
        print(f"Erreur Telegram: {e}", flush=True)


def get_indice_ref(symbole="TNO"):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbole}&exchange=XPAR&interval=1day&outputsize=25&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=10).json()
        if r.get("status") == "error":
            return None
        return [float(v["close"]) for v in reversed(r["values"])]
    except Exception:
        return None


def get_indicateurs(nom, symbol, ref_closes=None):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&exchange={EXCHANGE}&interval=1day&outputsize=60&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=15).json()
        if r.get("status") == "error":
            return None
        valeurs = r["values"]
        if len(valeurs) < 21:
            return None
        closes = [float(v["close"]) for v in reversed(valeurs)]
        volumes = [float(v["volume"]) for v in reversed(valeurs)]
        prix = closes[-1]
        mm20 = sum(closes[-20:]) / 20
        mm50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        gains = []
        losses = []
        for i in range(-14, 0):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        rsi = round(100 - (100 / (1 + rs)), 1)
        tracking_error = None
        perf_20j = None
        if ref_closes and len(ref_closes) >= 20 and len(closes) >= 20:
            perf_valeur = (closes[-1] / closes[-20] - 1) * 100
            perf_indice = (ref_closes[-1] / ref_closes[-20] - 1) * 100
            tracking_error = round(perf_valeur - perf_indice, 2)
            perf_20j = round(perf_valeur, 2)
        return {
            "prix": round(prix, 2),
            "mm20": round(mm20, 2),
            "mm50": round(mm50, 2) if mm50 else None,
            "rsi": rsi,
            "volume": int(volumes[-1]),
            "volume_moyen": int(sum(volumes[-20:]) / 20),
            "croisement_haussier": bool(mm20 > mm50) if mm50 else None,
            "tracking_error": tracking_error,
            "perf_20j": perf_20j,
        }
    except Exception as e:
        print(f"Erreur indicateurs {symbol}: {e}", flush=True)
        return None


def get_carnet_ordres(symbol):
    try:
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&exchange={EXCHANGE}&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=15).json()
        if r.get("status") == "error":
            return None
        prix = float(r.get("close", 0) or 0)
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
        carnet_txt = (
            f"\nCarnet : Bid {carnet['bid']}€ / Ask {carnet['ask']}€"
            f" / Spread {carnet['spread_pct']}%"
            f"\nPrix limite achat : {carnet['prix_limite_achat']}€"
            f" / vente : {carnet['prix_limite_vente']}€"
        )
    te = indicateurs.get("tracking_error")
    perf = indicateurs.get("perf_20j")
    te_txt = f"{te:+.2f}%" if te is not None else "N/A"
    perf_txt = f"{perf:+.2f}%" if perf is not None else "N/A"
    prompt = (
        f"Tu es un assistant de trading speculatif PEA francais.\n\n"
        f"Valeur : {nom}\n"
        f"- Prix : {indicateurs['prix']}€ | RSI : {indicateurs['rsi']}\n"
        f"- MM20 : {indicateurs['mm20']}€ | MM50 : {indicateurs['mm50']}€\n"
        f"- Croisement MM20>MM50 : {indicateurs['croisement_haussier']}\n"
        f"- Volume : {indicateurs['volume']:,} / Moyen 20j : {indicateurs['volume_moyen']:,}\n"
        f"- Performance 20j : {perf_txt} | Tracking error vs CAC : {te_txt}\n"
        f"- Budget : {BUDGET_PAR_LIGNE}€ / Frais : 2.50€"
        f"{carnet_txt}\n\n"
        f"Reponds UNIQUEMENT avec ce JSON :\n"
        f'{{"action": "ACHETER" ou "VENDRE" ou "ATTENDRE", '
        f'"prix_entree": float ou null, "quantite": int ou null, '
        f'"stop_loss": float ou null, "objectif": float ou null, '
        f'"type_ordre": "LIMITE" ou "MARCHE", "raison": "max 20 mots"}}\n\n'
        f"Regles :\n"
        f"- ACHETER si RSI<35 ET volume>volume_moyen ET croisement haussier\n"
        f"- ACHETER aussi si tracking_error < -15 ET RSI<50\n"
        f"- VENDRE si RSI>70\n"
        f"- VENDRE aussi si tracking_error > +15 ET RSI>60\n"
        f"- ATTENDRE sinon\n"
        f"- Stop = prix*0.75 / Objectif = prix*1.50\n"
        f"- Quantite = floor(budget/prix), minimum 1"
    )
    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": "claude-haiku-4-5",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    }
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=body,
        timeout=30,
    )
    data = r.json()
    texte = data["content"][0]["text"].strip()
    texte = texte.replace("```json", "").replace("```", "").strip()
    return json.loads(texte)


def run_agent():
    print(f"run_agent a {datetime.now(PARIS_TZ).strftime('%H:%M:%S')}", flush=True)
    maintenant = datetime.now(PARIS_TZ)
    if maintenant.weekday() >= 5:
        print("Week-end, pause.", flush=True)
        return
    if not (9 <= maintenant.hour < 18):
        print(f"Hors seance ({maintenant.hour}h).", flush=True)
        return
    print(f"Analyse a {maintenant.strftime('%H:%M')}", flush=True)
    ref_cache = {}

    for nom, symbol in WATCHLIST.items():
        print(f"  -> {nom}...", flush=True)
        etf = INDICES_REF.get(nom, "TNO")
        if etf not in ref_cache:
            ref_cache[etf] = get_indice_ref(etf)
            print(f"  ETF {etf} charge : {'OK' if ref_cache[etf] else 'KO'}", flush=True)
        indicateurs = get_indicateurs(nom, symbol, ref_cache[etf])
        time.sleep(8)
        if not indicateurs:
            continue
        carnet = get_carnet_ordres(symbol)
        try:
            signal = analyser_avec_claude(nom, indicateurs, carnet)
        except Exception as e:
            print(f"  Erreur Claude {nom}: {e}", flush=True)
            continue
        action = signal.get("action", "ATTENDRE")
        te = indicateurs.get("tracking_error")
        te_txt = f"{te:+.2f}%" if te is not None else "N/A"
        print(f"  {nom}: {action} RSI={indicateurs['rsi']} TE={te_txt}", flush=True)
        if action in ["ACHETER", "VENDRE"]:
            emoji = "📈" if action == "ACHETER" else "📉"
            carnet_msg = ""
            if carnet:
                carnet_msg = (
                    f"\nBid {carnet['bid']}€ | Ask {carnet['ask']}€"
                    f" | Spread {carnet['spread_pct']}%"
                )
            perf_txt2 = (
                f"{indicateurs['perf_20j']:+.2f}%"
                if indicateurs.get("perf_20j") is not None
                else "N/A"
            )
            msg = (
                f"🤖 *SIGNAL {nom}*\n\n"
                f"{emoji} *{action}* | {signal.get('type_ordre', 'LIMITE')}\n"
                f"💶 Prix : {signal.get('prix_entree', '—')}€\n"
                f"📦 Quantite : {signal.get('quantite', '—')} titres\n"
                f"🛑 Stop : {signal.get('stop_loss', '—')}€\n"
                f"🎯 Objectif : {signal.get('objectif', '—')}€\n"
                f"📊 RSI : {indicateurs['rsi']}\n"
                f"📉 Tracking error : {te_txt} | Perf 20j : {perf_txt2}"
                f"{carnet_msg}\n"
                f"💡 _{signal.get('raison', '')}_"
            )
            envoyer_telegram(msg)


if __name__ == "__main__":
    import sys
    print("Demarrage agent v5...", flush=True)
    if not TOKEN:
        print("ERREUR: TOKEN manquant", flush=True)
        sys.exit(1)
    if not TWELVE_KEY:
        print("ERREUR: TWELVE_KEY manquant", flush=True)
        sys.exit(1)
    if not ANTHROPIC_KEY:
        print("ERREUR: ANTHROPIC_KEY manquant", flush=True)
        sys.exit(1)
    print("Variables OK", flush=True)
    envoyer_telegram("Agent LMTrade v5 demarre - RSI + Tracking Error actifs")
    while True:
        run_agent()
        print("Pause 60 min...", flush=True)
        time.sleep(3600)