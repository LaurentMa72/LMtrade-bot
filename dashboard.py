import os
import json
import requests
from flask import Flask, render_template_string, request, jsonify
import pytz
from datetime import datetime

app = Flask(__name__)

TWELVE_KEY = os.environ.get("TWELVE_KEY")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_KEY")
EXCHANGE = "XPAR"
PARIS_TZ = pytz.timezone("Europe/Paris")
BUDGET_PAR_LIGNE = 150

WATCHLIST = {
    "KALRAY": "ALKAL", "2CRSI": "AL2SI", "SOITEC": "SOI",
    "RIBER": "ALRIB", "SEMCO": "ALSEM", "NEXANS": "NEX",
    "VUSION": "VU", "STM": "STMPA", "NANOBIOTIX": "NANO",
    "DBV": "DBV", "GENFIT": "GNFT", "VALLOUREC": "VK", "MAUREL": "MAU",
}

INDICES_REF = {
    "KALRAY": "TNO", "2CRSI": "TNO", "SOITEC": "TNO",
    "RIBER": "TNO", "SEMCO": "TNO", "STM": "TNO",
    "NANOBIOTIX": "HLT", "DBV": "HLT", "GENFIT": "HLT",
    "NEXANS": "ENE", "VUSION": "ENE",
    "VALLOUREC": "ENE", "MAUREL": "ENE",
}

HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LMTrade Dashboard</title>
<style>
  body { font-family: Arial, sans-serif; background: #0f0f1a; color: #e0e0e0; margin: 0; padding: 20px; }
  h1 { color: #00d4aa; text-align: center; }
  .search-box { background: #1a1a2e; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: flex; gap: 10px; }
  .search-box input { flex: 1; padding: 10px; border-radius: 6px; border: 1px solid #333; background: #0f0f1a; color: #fff; font-size: 14px; }
  .search-box select { padding: 10px; border-radius: 6px; border: 1px solid #333; background: #0f0f1a; color: #fff; }
  .search-box button { padding: 10px 20px; background: #00d4aa; color: #000; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; }
  .result-box { background: #1a1a2e; padding: 20px; border-radius: 10px; margin-bottom: 20px; display: none; }
  table { width: 100%; border-collapse: collapse; background: #1a1a2e; border-radius: 10px; overflow: hidden; }
  th { background: #00d4aa; color: #000; padding: 10px; text-align: left; }
  td { padding: 10px; border-bottom: 1px solid #333; }
  tr:hover td { background: #252540; }
  .achat { color: #00d4aa; font-weight: bold; }
  .vente { color: #ff4444; font-weight: bold; }
  .attendre { color: #aaa; }
  .rsi-low { color: #00d4aa; }
  .rsi-high { color: #ff4444; }
  .loading { text-align: center; color: #00d4aa; padding: 20px; }
  .refresh-btn { background: #333; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; float: right; margin-bottom: 10px; }
</style>
</head>
<body>
<h1>📊 LMTrade Dashboard</h1>

<div class="search-box">
  <input type="text" id="ticker" placeholder="Ticker (ex: ALKAL, NEX, NANO...)" />
  <select id="exchange">
    <option value="XPAR">Euronext Paris</option>
    <option value="XNAS">NASDAQ</option>
    <option value="XNYS">NYSE</option>
  </select>
  <input type="text" id="nom" placeholder="Nom (ex: KALRAY)" />
  <button onclick="analyserValeur()">🔍 Analyser</button>
</div>

<div class="result-box" id="result-box">
  <h3 id="result-titre"></h3>
  <div id="result-content"></div>
</div>

<button class="refresh-btn" onclick="chargerWatchlist()">🔄 Actualiser</button>
<h2>📋 Watchlist</h2>
<div id="watchlist-loading" class="loading">Chargement...</div>
<table id="watchlist-table" style="display:none">
  <thead>
    <tr>
      <th>Valeur</th>
      <th>Prix</th>
      <th>RSI</th>
      <th>MM20</th>
      <th>Vol/Moy</th>
      <th>Tracking Error</th>
      <th>Perf 20j</th>
      <th>Signal</th>
    </tr>
  </thead>
  <tbody id="watchlist-body"></tbody>
</table>

<script>
async function chargerWatchlist() {
  document.getElementById('watchlist-loading').style.display = 'block';
  document.getElementById('watchlist-table').style.display = 'none';
  const resp = await fetch('/api/watchlist');
  const data = await resp.json();
  const tbody = document.getElementById('watchlist-body');
  tbody.innerHTML = '';
  data.forEach(v => {
    const rsiClass = v.rsi < 35 ? 'rsi-low' : v.rsi > 70 ? 'rsi-high' : '';
    const signalClass = v.signal === 'ACHETER' ? 'achat' : v.signal === 'VENDRE' ? 'vente' : 'attendre';
    const signalEmoji = v.signal === 'ACHETER' ? '🟢' : v.signal === 'VENDRE' ? '🔴' : '⏳';
    const te = v.tracking_error !== null ? (v.tracking_error > 0 ? '+' : '') + v.tracking_error + '%' : 'N/A';
    const perf = v.perf_20j !== null ? (v.perf_20j > 0 ? '+' : '') + v.perf_20j + '%' : 'N/A';
    const volRatio = v.volume_moyen > 0 ? Math.round(v.volume / v.volume_moyen * 100) + '%' : 'N/A';
    tbody.innerHTML += `<tr>
      <td><strong>${v.nom}</strong></td>
      <td>${v.prix}€</td>
      <td class="${rsiClass}">${v.rsi}</td>
      <td>${v.mm20}€</td>
      <td>${volRatio}</td>
      <td>${te}</td>
      <td>${perf}</td>
      <td class="${signalClass}">${signalEmoji} ${v.signal}</td>
    </tr>`;
  });
  document.getElementById('watchlist-loading').style.display = 'none';
  document.getElementById('watchlist-table').style.display = 'table';
}

async function analyserValeur() {
  const ticker = document.getElementById('ticker').value.trim();
  const exchange = document.getElementById('exchange').value;
  const nom = document.getElementById('nom').value.trim() || ticker;
  if (!ticker) return;
  document.getElementById('result-box').style.display = 'block';
  document.getElementById('result-titre').textContent = 'Analyse en cours...';
  document.getElementById('result-content').textContent = '';
  const resp = await fetch(`/api/analyser?ticker=${ticker}&exchange=${exchange}&nom=${nom}`);
  const data = await resp.json();
  document.getElementById('result-titre').textContent = `Analyse ${nom} (${ticker})`;
  if (data.error) {
    document.getElementById('result-content').innerHTML = `<p style="color:red">${data.error}</p>`;
    return;
  }
  const signalColor = data.signal === 'ACHETER' ? '#00d4aa' : data.signal === 'VENDRE' ? '#ff4444' : '#aaa';
  document.getElementById('result-content').innerHTML = `
    <table style="width:auto">
      <tr><td>Prix</td><td><strong>${data.prix}€</strong></td></tr>
      <tr><td>RSI (14)</td><td>${data.rsi}</td></tr>
      <tr><td>MM20</td><td>${data.mm20}€</td></tr>
      <tr><td>MM50</td><td>${data.mm50 || 'N/A'}€</td></tr>
      <tr><td>Volume</td><td>${data.volume?.toLocaleString()}</td></tr>
      <tr><td>Volume moyen</td><td>${data.volume_moyen?.toLocaleString()}</td></tr>
      <tr><td>Perf 20j</td><td>${data.perf_20j !== null ? (data.perf_20j > 0 ? '+' : '') + data.perf_20j + '%' : 'N/A'}</td></tr>
      <tr><td>Signal</td><td style="color:${signalColor}; font-weight:bold">${data.signal}</td></tr>
      <tr><td>Prix entrée</td><td>${data.prix_entree || '—'}€</td></tr>
      <tr><td>Stop-loss</td><td>${data.stop_loss || '—'}€</td></tr>
      <tr><td>Objectif</td><td>${data.objectif || '—'}€</td></tr>
      <tr><td>Avis</td><td><em>${data.raison || '—'}</em></td></tr>
    </table>`;
}

window.onload = chargerWatchlist;
</script>
</body>
</html>
"""

def get_indicateurs(nom, symbol, exchange=None, ref_closes=None):
    try:
        exch = exchange or EXCHANGE
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&exchange={exch}&interval=1day&outputsize=60&apikey={TWELVE_KEY}"
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
        gains, losses = [], []
        for i in range(-14, 0):
            diff = closes[i] - closes[i-1]
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
        return None

def get_indice_ref(symbole="TNO"):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={symbole}&exchange=XPAR&interval=1day&outputsize=25&apikey={TWELVE_KEY}"
        r = requests.get(url, timeout=10).json()
        if r.get("status") == "error":
            return None
        return [float(v["close"]) for v in reversed(r["values"])]
    except Exception:
        return None

def analyser_avec_claude(nom, indicateurs):
    te = indicateurs.get("tracking_error")
    perf = indicateurs.get("perf_20j")
    te_txt = f"{te:+.2f}%" if te is not None else "N/A"
    perf_txt = f"{perf:+.2f}%" if perf is not None else "N/A"
    prompt = (
        f"Tu es un assistant de trading speculatif.\n"
        f"Valeur : {nom}\n"
        f"Prix : {indicateurs['prix']}€ | RSI : {indicateurs['rsi']}\n"
        f"MM20 : {indicateurs['mm20']}€ | MM50 : {indicateurs['mm50']}€\n"
        f"Volume : {indicateurs['volume']:,} / Moyen 20j : {indicateurs['volume_moyen']:,}\n"
        f"Perf 20j : {perf_txt} | Tracking error : {te_txt}\n"
        f"Budget : {BUDGET_PAR_LIGNE}€ / Frais : 2.50€\n\n"
        f"Reponds UNIQUEMENT avec ce JSON :\n"
        f'{{"action": "ACHETER" ou "VENDRE" ou "ATTENDRE", '
        f'"prix_entree": float ou null, "quantite": int ou null, '
        f'"stop_loss": float ou null, "objectif": float ou null, '
        f'"raison": "max 20 mots"}}\n\n'
        f"Regles : ACHETER si RSI<35 ET volume>volume_moyen. "
        f"ACHETER si tracking_error<-15 ET RSI<50. "
        f"VENDRE si RSI>70. VENDRE si tracking_error>+15 ET RSI>60. "
        f"ATTENDRE sinon. Stop=prix*0.75. Objectif=prix*1.50."
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
    r = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=body, timeout=30)
    data = r.json()
    texte = data["content"][0]["text"].strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texte)

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/watchlist")
def api_watchlist():
    ref_cache = {}
    resultats = []
    for nom, symbol in WATCHLIST.items():
        etf = INDICES_REF.get(nom, "TNO")
        if etf not in ref_cache:
            ref_cache[etf] = get_indice_ref(etf)
        indicateurs = get_indicateurs(nom, symbol, ref_closes=ref_cache[etf])
        if not indicateurs:
            resultats.append({"nom": nom, "prix": "N/A", "rsi": "N/A", "mm20": "N/A",
                              "volume": 0, "volume_moyen": 1, "tracking_error": None,
                              "perf_20j": None, "signal": "ERREUR"})
            continue
        try:
            signal = analyser_avec_claude(nom, indicateurs)
            action = signal.get("action", "ATTENDRE")
        except Exception:
            action = "ERREUR"
        resultats.append({
            "nom": nom,
            "prix": indicateurs["prix"],
            "rsi": indicateurs["rsi"],
            "mm20": indicateurs["mm20"],
            "volume": indicateurs["volume"],
            "volume_moyen": indicateurs["volume_moyen"],
            "tracking_error": indicateurs["tracking_error"],
            "perf_20j": indicateurs["perf_20j"],
            "signal": action,
        })
    return jsonify(resultats)

@app.route("/api/analyser")
def api_analyser():
    ticker = request.args.get("ticker", "").upper()
    exchange = request.args.get("exchange", "XPAR")
    nom = request.args.get("nom", ticker)
    if not ticker:
        return jsonify({"error": "Ticker manquant"})
    ref_closes = get_indice_ref("TNO")
    indicateurs = get_indicateurs(nom, ticker, exchange=exchange, ref_closes=ref_closes)
    if not indicateurs:
        return jsonify({"error": f"Données introuvables pour {ticker} sur {exchange}"})
    try:
        signal = analyser_avec_claude(nom, indicateurs)
    except Exception as e:
        return jsonify({"error": f"Erreur analyse Claude: {str(e)}"})
    return jsonify({
        **indicateurs,
        "signal": signal.get("action", "ATTENDRE"),
        "prix_entree": signal.get("prix_entree"),
        "stop_loss": signal.get("stop_loss"),
        "objectif": signal.get("objectif"),
        "raison": signal.get("raison"),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)