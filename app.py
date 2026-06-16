"""
Cash Flow FF — tracker harian via HP (Streamlit + Google Sheet).
Catat pemasukan/pengeluaran/investasi, lihat dashboard per periode gajian.
"""
from datetime import date
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px

import core
from core import KATEGORI, TIPE, GROUPS, GROUP_DESC, TX_HEADERS, rp

st.set_page_config(page_title="Cash Flow FF", page_icon="\U0001F4B8", layout="centered")

# ----------------- koneksi Google Sheet -----------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]


@st.cache_resource
def _sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(st.secrets["sheet_id"])


def _ws():
    sh = _sheet()
    try:
        return sh.worksheet("transaksi")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title="transaksi", rows=2000, cols=len(TX_HEADERS))
        ws.append_row(TX_HEADERS)
        return ws


@st.cache_data(ttl=30)
def load_tx():
    rows = _ws().get_all_records()
    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(columns=TX_HEADERS)
    return df


def add_tx(tanggal, tipe, kategori, group, aktivitas, jumlah):
    _ws().append_row(
        [tanggal.isoformat(), tipe, kategori, group, aktivitas, float(jumlah)],
        value_input_option="USER_ENTERED")
    load_tx.clear()


# ----------------- pengaturan -----------------
with st.sidebar:
    st.header("\u2699\ufe0f Pengaturan")
    payday = st.number_input("Tanggal gajian", 1, 28, 25)
    saldo_awal = st.number_input("Saldo awal (Rp)", value=0, step=100000)
    target_invest = st.number_input("Target invest / periode (Rp)",
                                    value=6_000_000, step=500_000)
    st.caption("Tip HP: buka URL ini di browser \u2192 menu \u2192 "
               "\u201cAdd to Home Screen\u201d biar kayak app.")

# ----------------- data -----------------
try:
    raw = load_tx()
except Exception as e:
    st.error("Gagal konek ke Google Sheet. Cek `secrets` & sharing sheet.\n\n"
             f"Detail: {e}")
    st.stop()

df = core.prepare(raw, payday=payday, saldo_awal=saldo_awal)

st.title("\U0001F4B8 Cash Flow \u2014 Jalur FF")
if not df.empty:
    st.caption(f"Saldo sekarang: **{rp(df['saldo'].iloc[-1])}**  ·  "
               f"{len(df)} transaksi tercatat")

tab_catat, tab_dash = st.tabs(["\u2795 Catat", "\U0001F4CA Dashboard"])

# ======================= TAB CATAT =======================
with tab_catat:
    st.subheader("Catat transaksi")
    tipe = st.radio("Tipe", TIPE, horizontal=True)
    c1, c2 = st.columns(2)
    with c1:
        tanggal = st.date_input("Tanggal", value=date.today())
    with c2:
        kategori = st.selectbox("Kategori", KATEGORI[tipe])
    group = ""
    if tipe == "Pengeluaran":
        group = st.selectbox("Group", GROUPS,
                             help=" · ".join(f"{g}: {d}" for g, d in GROUP_DESC.items()))
        st.caption(f"_{GROUP_DESC[group]}_")
    aktivitas = st.text_input("Aktivitas / catatan", placeholder="mis. Galon + telur")
    jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000, value=0)

    if st.button("\U0001F4BE Simpan", type="primary", use_container_width=True):
        if jumlah <= 0:
            st.warning("Isi jumlah dulu.")
        else:
            add_tx(tanggal, tipe, kategori, group, aktivitas, jumlah)
            st.success(f"Tersimpan: {tipe} \u2013 {kategori} \u2013 {rp(jumlah)}")
            st.rerun()

    if not df.empty:
        st.divider()
        st.caption("Transaksi terakhir")
        recent = df.tail(8).iloc[::-1][
            ["tanggal", "tipe", "kategori", "group", "aktivitas", "jumlah"]].copy()
        recent["tanggal"] = recent["tanggal"].dt.strftime("%d %b")
        recent["jumlah"] = recent["jumlah"].apply(rp)
        st.dataframe(recent, hide_index=True, use_container_width=True)

# ======================= TAB DASHBOARD =======================
with tab_dash:
    if df.empty:
        st.info("Belum ada data. Catat transaksi dulu di tab \u201cCatat\u201d.")
    else:
        rk = core.rekap(df)
        keys = list(rk["periode"])
        labels = dict(zip(rk["periode"], rk["label"]))
        sel = st.selectbox("Periode", keys[::-1],
                           format_func=lambda k: labels[k], index=0)
        s = core.period_summary(df, sel)

        c1, c2, c3 = st.columns(3)
        c1.metric("Pemasukan", rp(s["pemasukan"]))
        c2.metric("Pengeluaran", rp(s["pengeluaran"]))
        c3.metric("Surplus", rp(s["surplus"]))
        c1, c2, c3 = st.columns(3)
        c1.metric("Savings Rate", f"{s['savings_rate']*100:.1f}%")
        c2.metric("Invest Rate", f"{s['invest_rate']*100:.1f}%")
        c3.metric("Side Income", rp(s["side"]))

        gap = s["investasi"] - target_invest
        st.progress(min(s["investasi"] / target_invest, 1.0) if target_invest else 0,
                    text=(f"Investasi {rp(s['investasi'])} / target {rp(target_invest)}  "
                          + ("\u2705 ON TRACK" if gap >= 0 else f"\u26a0\ufe0f kurang {rp(-gap)}")))

        st.divider()
        st.subheader("Group \u2014 kemana uang lo lari")
        gdf = s["group"].reset_index()
        gdf.columns = ["group", "jumlah"]
        gdf = gdf[gdf["jumlah"] > 0]
        if not gdf.empty:
            cmap = {"Wajib": "#2E7D6F", "Penting": "#1F3864",
                    "Fun": "#E0A458", "Error": "#C0504D"}
            fig = px.pie(gdf, names="group", values="jumlah", hole=0.45,
                         color="group", color_discrete_map=cmap)
            fig.update_traces(textinfo="label+percent")
            fig.update_layout(showlegend=False, height=300, margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            for _, r in gdf.iterrows():
                st.caption(f"**{r['group']}** {rp(r['jumlah'])} \u2014 _{GROUP_DESC[r['group']]}_")

        st.subheader("Pengeluaran per kategori")
        kdf = s["kategori"].reset_index()
        kdf.columns = ["kategori", "jumlah"]
        kdf = kdf[kdf["jumlah"] > 0]
        if not kdf.empty:
            fig2 = px.bar(kdf, x="jumlah", y="kategori", orientation="h")
            fig2.update_layout(height=max(280, 22 * len(kdf)),
                               yaxis=dict(autorange="reversed"),
                               margin=dict(t=10, b=10), xaxis_title=None, yaxis_title=None)
            st.plotly_chart(fig2, use_container_width=True)

        if len(rk) > 1:
            st.divider()
            st.subheader("Tren antar periode")
            trend = rk.set_index("label")
            st.caption("Savings rate & invest rate")
            st.line_chart(trend[["savings_rate", "invest_rate"]])
            if trend["side"].sum() > 0:
                st.caption("Side income")
                st.line_chart(trend[["side"]])
