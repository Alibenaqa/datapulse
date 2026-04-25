"""
DataPulse — Dashboard
Interface visuelle temps réel pour suivre les prédictions ML et les alertes de drift.
"""

import json
import time
from pathlib import Path

import requests
import streamlit as st

API_BASE = "http://localhost:8000"
ALERTS_FILE = Path("monitoring/reports/alerts.jsonl")

st.set_page_config(
    page_title="DataPulse Dashboard",
    page_icon="📈",
    layout="wide",
)

# ── CSS custom ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.big-metric { font-size: 2.5rem; font-weight: 700; }
.up   { color: #00c853; }
.down { color: #ff1744; }
.ok   { color: #00c853; }
.warn { color: #ff9800; }
.crit { color: #ff1744; }
.card { background: #1e1e2e; border-radius: 12px; padding: 1rem 1.5rem; margin-bottom: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📈 DataPulse — Tableau de bord temps réel")
st.caption("Prédictions ML sur les actions boursières · Surveillance de la qualité du modèle · Insights IA")
st.divider()


# ── Helpers ───────────────────────────────────────────────────────────────────
def get(endpoint: str):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=3)
        return r.json() if r.ok else None
    except Exception:
        return None


def load_alerts(n=50):
    if not ALERTS_FILE.exists():
        return []
    lines = ALERTS_FILE.read_text().strip().split("\n")
    alerts = [json.loads(l) for l in lines if l]
    return alerts[-n:]


def level_badge(level: str) -> str:
    colors = {"ok": "✅", "warning": "⚠️", "critical": "🔴"}
    return colors.get(level, "❓")


# ── Section 1 : Statut système ────────────────────────────────────────────────
st.subheader("🖥️ État du système")
health = get("/health")

col1, col2, col3, col4 = st.columns(4)
with col1:
    ok = health and health.get("status") == "ok"
    st.metric("API", "En ligne ✅" if ok else "Hors ligne ❌")
with col2:
    ok = health and health.get("model_production")
    st.metric("Modèle Production", "Chargé ✅" if ok else "Absent ❌")
with col3:
    ok = health and health.get("model_staging")
    st.metric("Modèle Staging", "Chargé ✅" if ok else "Absent ❌")
with col4:
    ok = health and health.get("redis_online")
    st.metric("Redis (features)", "Connecté ✅" if ok else "Déconnecté ❌")

st.divider()

# ── Section 2 : Prédictions temps réel ───────────────────────────────────────
st.subheader("🤖 Prédictions en temps réel")
st.caption("Le modèle ML prédit si chaque action va monter (UP) ou baisser (DOWN) dans les prochains ticks.")

symbols_data = get("/symbols")
symbols = symbols_data.get("symbols", []) if symbols_data else []

if not symbols:
    st.warning("Aucun symbole disponible — lance le feature pipeline d'abord.")
else:
    cols = st.columns(len(symbols))
    for col, symbol in zip(cols, symbols):
        pred_data = get(f"/predict/{symbol}")
        with col:
            if pred_data and "prediction" in pred_data:
                p = pred_data["prediction"]
                direction = p["direction"]
                prob = p["probability_up"]
                confidence = p["confidence"]
                arrow = "🟢 UP" if direction == "UP" else "🔴 DOWN"

                st.markdown(f"### {symbol}")
                st.markdown(f"<div class='big-metric {'up' if direction == 'UP' else 'down'}'>{arrow}</div>", unsafe_allow_html=True)
                st.progress(prob, text=f"Proba hausse : {prob:.0%}")
                st.caption(f"Confiance : {confidence}")
            else:
                st.markdown(f"### {symbol}")
                st.warning("Pas de données")

st.divider()

# ── Section 3 : Alertes de drift ─────────────────────────────────────────────
st.subheader("🔍 Surveillance du modèle (Data Drift)")
st.caption("On compare les données actuelles aux données d'entraînement. Si elles sont trop différentes, le modèle devient moins fiable.")

alerts = load_alerts()

if not alerts:
    st.info("Aucune alerte — lance d'abord : `python monitoring/run.py --simulate-drift`")
else:
    # Résumé compteurs
    ok_count   = sum(1 for a in alerts if a.get("level") == "ok")
    warn_count = sum(1 for a in alerts if a.get("level") == "warning")
    crit_count = sum(1 for a in alerts if a.get("level") == "critical")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total alertes", len(alerts))
    c2.metric("✅ Stable", ok_count)
    c3.metric("⚠️ Attention", warn_count)
    c4.metric("🔴 Critique", crit_count)

    st.markdown("#### Dernières alertes")
    for alert in reversed(alerts[-8:]):
        level = alert.get("level", "?")
        symbol = alert.get("symbol", "?")
        drift_share = alert.get("drift_share", 0)
        features = alert.get("features_drifted", [])
        ts = alert.get("timestamp", "")[:19].replace("T", " ")
        badge = level_badge(level)

        with st.expander(f"{badge} {symbol} — {ts} — Drift : {drift_share:.0%}"):
            if features:
                st.write(f"**Features impactées :** {', '.join(features)}")
            else:
                st.write("Aucune feature impactée — modèle stable.")
            st.write(f"**Message :** {alert.get('message', '')}")

st.divider()

# ── Section 4 : Insights IA ───────────────────────────────────────────────────
st.subheader("🧠 Analyse IA par Claude")
st.caption("Claude analyse les alertes de drift et génère des recommandations en langage naturel.")

selected = st.selectbox("Choisir un symbole à analyser", ["(tous)"] + symbols)

if st.button("🚀 Lancer l'analyse IA", type="primary"):
    sym = None if selected == "(tous)" else selected
    endpoint = f"/insights/{sym}" if sym else "/insights"

    with st.spinner("Claude analyse les alertes... (10-20 secondes)"):
        result = get(endpoint)

    if result and "insight" in result:
        n = result.get("n_alerts_analyzed", "?")
        st.success(f"Analyse terminée — {n} alertes examinées")
        st.markdown(result["insight"])
    elif result is None:
        st.error("Erreur — vérifie que l'API tourne et que ANTHROPIC_API_KEY est définie.")
    else:
        st.warning(result.get("detail", "Aucune donnée disponible."))

st.divider()

# ── Footer + auto-refresh ─────────────────────────────────────────────────────
st.caption("🔄 Page actualisée toutes les 10 secondes")
time.sleep(10)
st.rerun()
