import os, json, time
import requests
from datetime import datetime

TOKEN = os.environ.get("TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")
TWELVE_KEY = os.environ.get("TWELVE_KEY")

# Liste de small/mid caps françaises éligibles PEA à scanner
# Source : Euronext Paris — compartiments B et C (small/mid caps)
UNIVERS_SCAN = {
    "ABEO": "ABEO", "ACTIA": "ACGC", "ADEUNIS": "ALDE",
    "ADOMOS": "ADOM", "ADT": "ADTH", "AGRIPOWER": "ALAGP",
    "AKWEL": "AKW", "ALCHIMIE": "ALCHI", "ALDEL": "ALDEL",
    "ALEXA": "ALEXA", "ALFEN": "ALFEN", "ALLIX": "ALLIX",
    "ALSTOM": "ALO", "ALTAREA": "ALTA", "ALTEN": "ATE",
    "AMPLITUDE": "AMPLI", "ANTIN": "ANTIN", "APERAM": "APAM",
    "ARGAN": "ARG", "ARKEMA": "AKE", "ASSYSTEM": "ASY",
    "ATEME": "ATEME", "ATLAND": "ATLD", "AUBAY": "AUB",
    "BALYO": "BALYO", "BASTIDE": "BLC", "BENETEAU": "BEN",
    "BIGBEN": "BIG", "BILENDI": "ALBLD", "BIOATLA": "BCAB",
    "BIOMERIEUX": "BIM", "BOIRON": "BOI", "BONDUELLE": "BON",
    "BPCE": "BPCE", "BUREAU VERITAS": "BVI", "CAPGEMINI": "CAP",
    "CARBIOS": "ALCRB", "CATANA": "CATG", "CLARANOVA": "CLA",
    "CLASQUIN": "ALCLA", "CLESTRA": "ALCLS", "CMG": "CMG",
    "CNP": "CNP", "COHERIS": "COH", "COLRUYT": "COLR",
    "CROSSWOOD": "ALCW", "CS GROUP": "CSF", "DALET": "DLT",
    "DBV": "DBV", "DELTA PLUS": "DLTA", "DEVOTEAM": "DEVO",
    "DIGIA": "DIGIA", "DLSI": "DLSI", "DNA SCRIPT": "ALNA",
    "DRONE VOLT": "ALDRV", "ECA": "ECASA", "ECOSLOPS": "ALECO",
    "EKINOPS": "EKI", "ELHYSSEN": "ALHY", "ELIOR": "ELIOR",
    "ENGIE": "ENGI", "ENTREPARTICULIERS": "ALETP", "EOL": "EOL",
    "EQUASENS": "EQS", "ESSO": "ES", "EUROAPI": "EAPI",
    "EUROBIO": "ALBIO", "EURONEXT": "ENX", "EUROPCAR": "EUCAR",
    "EUTELSAT": "ETL", "EXAIL": "EXA", "EXPANSCIENCE": "ALEXP",
    "FASHION3": "ALFAS", "FERMENTALG": "ALGAE", "FIGEAC": "FGA",
    "FOUNTAINE": "FPBF", "GECI": "GECI", "GENFIT": "GNFT",
    "GENOMIC": "ALGEN", "GETLINK": "GET", "GL EVENTS": "GLO",
    "GLOBAL BIOENERGIES": "ALGBE", "GUILLEMOT": "GUI",
    "HEXAOM": "HEX", "HIPAY": "HIPAY", "HORN": "ALHON",
    "HYDROGENE": "ALHYD", "ILS": "ALILS", "IMMERSION": "ALIMM",
    "INFOTEL": "INF", "INNATE PHARMA": "IPH", "INSIDE": "ALISB",
    "INTERPARFUMS": "ITP", "IPSEN": "IPN", "ITS GROUP": "ITS",
    "JACQUET": "JCQ", "KALRAY": "ALKAL", "KERLINK": "ALKLK",
    "KUMULUS VAPE": "ALKVP", "LACROIX": "LACR", "LANSON BCC": "LBCC",
    "LASER": "LSR", "LATECOERE": "LAT", "LECTRA": "LSS",
    "LEGRAND": "LR", "LISI": "FII", "LLEIDA": "ALLEI",
    "LUMIBIRD": "LBIRD", "MACOMPTA": "ALMAS", "MAGINATICS": "MAG",
    "MALTERIES": "MALT", "MANUTAN": "MAN", "MCPHY": "MCPHY",
    "MEDINCELL": "MEDIC", "MEMSCAP": "MEMS", "METABOLON": "ALMET",
    "METHANOR": "METHN", "MGI DIGITAL": "ALDVI", "MIKRO": "MIKR",
    "MLIPERVIDEO": "ALMLI", "MONCEY": "MONC", "MOULINVEST": "ALMOU",
    "MRM": "MRM", "MUNIC": "ALMUN", "NANOBIOTIX": "NANO",
    "NATUREX": "NRX", "NCI INFO": "ALNCI", "NEOEN": "NEOEN",
    "NETGEM": "NTG", "NEXANS": "NEX", "NEXTEDIA": "ALNXT",
    "NICOX": "COX", "NOGEN": "ALNOG", "OBIZ": "OBIZ",
    "OCTO TECHNOLOGY": "ALOC", "OENEO": "SBT", "ONCODESIGN": "ALONC",
    "OPENDATASOFT": "ALODS", "ORBITAL": "ALORD", "OSE IMMUNO": "OSE",
    "PAREF": "PAR", "PASSAT": "ALPAS", "PEOPLE AND BABY": "PAB",
    "PEUGEOT INVEST": "PEUG", "PHARMAGEST": "PGT", "PHARVARIS": "PHVS",
    "PIERRE ET VAC": "VAC", "PIXIUM VISION": "PIX", "PLUXEE": "PLX",
    "POUJOULAT": "ALPJT", "PRODWAYS": "PWG", "PRECIA": "PREC",
    "QUANTEL": "QT", "QUANTUM GENOMICS": "ALQGC", "RIBER": "ALRIB",
    "ROTHSCHILD": "ROTH", "S30": "ALSEI", "SAFE": "SAFE",
    "SAN MARCO": "ALSM", "SARTORIUS": "DIM", "SES IMAGOTAG": "SESL",
    "SHOWROOMPRIVE": "SRP", "SIDETRADE": "ALSD", "SIGNAUX GIROD": "SGIG",
    "SOLUTIONS30": "S30", "SOITEC": "SOI", "SOMFY": "SO",
    "SPINEWAY": "ALSPW", "STMICRO": "STMPA", "SWORD": "SWP",
    "SYNERGIE": "SDG", "TARKETT": "TKTT", "TECHNIP": "TE",
    "TESSI": "TES", "THERMADOR": "THEP", "TIKEHAU": "TKO",
    "TONNER DRONES": "ALTND", "TOTALENERGIES": "TTE", "トランZEO": "TRME",
    "TRIGANO": "TRI", "TXCOM": "ALTXC", "UFF": "UFF",
    "UMANIS": "ALUMS", "VALNEVA": "VLA", "VALLOUREC": "VK",
    "VERGNET": "ALVER", "VETOQUINOL": "VETO", "VICAT": "VCT",
    "VIDELIO": "EV", "VISIATIV": "ALVIV", "VOLUNTARY": "VOLTY",
    "VUSION": "VU", "WAVESTONE": "WAVE", "WITBE": "WITB",
    "XL AIRWAYS": "ALXLA", "XILAM": "XIL", "YMAGIS": "MAGIS",
}

EXCHANGE = "XPAR"

def get_data_scan(symbol):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&exchange={EXCHANGE}&interval=1day&outputsize=25&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=10).json()
        if r.get("status") == "error":
            return None
        valeurs = r["values"]
        if len(valeurs) < 22:
            return None
        closes = [float(v["close"]) for v in reversed(valeurs)]
        volumes = [float(v["volume"]) for v in reversed(valeurs)]

        prix = closes[-1]
        variation = round((closes[-1] / closes[-2] - 1) * 100, 2)
        vol_actuel = volumes[-1]
        vol_moyen = sum(volumes[-20:]) / 20
        vol_ratio = round(vol_actuel / vol_moyen * 100) if vol_moyen else 0

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

        return {
            "prix": round(prix, 2),
            "variation": variation,
            "rsi": rsi,
            "vol_ratio": vol_ratio,
        }
    except:
        return None

def scanner_marche():
    maintenant = datetime.now()
    if maintenant.weekday() >= 5:
        return
    if maintenant.hour != 9 or maintenant.minute > 45:
        return

    print("\n🔍 Scanner de marché lancé...")
    opportunites = []

    for nom, symbol in UNIVERS_SCAN.items():
        data = get_data_scan(symbol)
        if not data:
            continue
        # Critères : RSI survendu + volume en hausse + prix > 1€
        if (data["rsi"] < 40 and
            data["vol_ratio"] > 150 and
            data["prix"] > 1.0 and
            data["variation"] > -5):
            opportunites.append({
                "nom": nom,
                "symbol": symbol,
                **data
            })
        time.sleep(0.5)  # Respecter les limites API

    if not opportunites:
        print("     Aucune opportunité détectée ce matin.")
        return

    # Trier par RSI le plus bas (plus survendu = meilleure opportunité)
    opportunites.sort(key=lambda x: x["rsi"])
    top = opportunites[:5]  # Top 5

    # Analyser avec Claude
    prompt = f"""Tu es un expert en trading spéculatif PEA français.

Voici les valeurs détectées ce matin par le scanner (RSI bas + volume en hausse) :

{json.dumps(top, indent=2, ensure_ascii=False)}

Pour chaque valeur, donne une recommandation concise en JSON :
[{{"nom": str, "symbol": str, "prix": float, "rsi": float, "vol_ratio": int, "verdict": "FORT INTERET" ou "INTERET MODERE" ou "PASSER", "raison": "max 15 mots", "action": "ACHETER" ou "SURVEILLER"}}]

Critères : favorise RSI < 35, volume > 200%, prix accessible < 20€ pour budget 100€/ligne."""

    headers = {
        "x-api-key": ANTHROPIC_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    body = {
        "model": "claude-haiku-4-5",
        "max_tokens": 800,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers=headers, json=body, timeout=30)
        data = r.json()
        texte = data["content"][0]["text"].strip()
        texte = texte.replace("```json", "").replace("```", "").strip()
        resultats = json.loads(texte)
    except Exception as e:
        print(f"     Erreur Claude scanner: {e}")
        resultats = top

    # Message Telegram
    msg = f"🔍 *SCANNER MARCHÉ — {maintenant.strftime('%d/%m/%Y')}*\n\n"
    msg += f"_{len(opportunites)} opportunités détectées, top {len(top)} analysées_\n\n"

    for i, v in enumerate(resultats, 1):
        emoji = "🔥" if v.get("verdict") == "FORT INTERET" else "👀"
        action = v.get("action", "SURVEILLER")
        msg += f"{emoji} *{v['nom']}* ({v['symbol']})\n"
        msg += f"   Prix : {v['prix']}€ | RSI : {v['rsi']} | Vol : +{v.get('vol_ratio', 0)}%\n"
        msg += f"   → {action} — _{v.get('raison', '')}_\n\n"

    msg += "💡 _Pour ajouter une valeur : modifie ta watchlist dans agent.py_"
    envoyer_telegram(msg)
    print(f"     ✅ Rapport scanner envoyé — {len(top)} opportunités")

def envoyer_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }, timeout=10)

if __name__ == "__main__":
    print("🔍 Scanner de marché démarré")
    while True:
        scanner_marche()
        time.sleep(300)  # Vérifie toutes les 5 min