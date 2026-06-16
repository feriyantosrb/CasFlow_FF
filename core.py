"""Logika murni cash-flow (tanpa Streamlit) — dipakai app.py & bisa dites sendiri."""
import pandas as pd

# Kategori per tipe (dari sistem lo, ditambah opsi FF)
KATEGORI = {
    "Pengeluaran": [
        "F&B", "F&B Stuff", "F&B Clean", "Skincare", "Body Wear", "Internet",
        "Book", "Subscription", "Bank", "Family", "Room Decor", "Rental Room",
        "Transportation", "Laundry", "Work Stuff", "Electricity", "Medicine",
        "Sport", "Pengeluaran Lain",
    ],
    "Pemasukan": ["Salary", "Side Income", "Bonus/THR", "Pemasukan Lain"],
    "Investasi": ["Saving", "Reksadana", "Saham", "Emas", "Dana Darurat"],
}
TIPE = ["Pengeluaran", "Pemasukan", "Investasi"]
GROUPS = ["Wajib", "Penting", "Fun", "Error"]
GROUP_DESC = {
    "Wajib": "Dicabut = hidup langsung bermasalah fisik/fungsi",
    "Penting": "Bikin hidup lebih kuat/bermakna jangka panjang",
    "Fun": "Bikin senang, tapi kalau dicabut hidup tetap jalan",
    "Error": "Ceroboh — pengeluaran yang harusnya gak perlu",
}
TX_HEADERS = ["tanggal", "tipe", "kategori", "group", "aktivitas", "jumlah"]
_MON = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]


def periode_key(d, payday=25):
    """Tanggal -> kunci periode 'YYYY-MM' mengikuti siklus gajian."""
    d = pd.Timestamp(d)
    base = d if d.day >= payday else d - pd.DateOffset(months=1)
    return base.strftime("%Y-%m")


def periode_label(key):
    y, m = key.split("-")
    m, y = int(m), int(y)
    nxt = m % 12 + 1
    return f"{_MON[m - 1]}\u2013{_MON[nxt - 1]} {str(y)[2:]}"


def prepare(df, payday=25, saldo_awal=0):
    """Bersihin + tambah kolom periode & saldo berjalan."""
    cols = TX_HEADERS + ["periode", "saldo"]
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=cols)
    df = df.copy()
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")
    df["jumlah"] = pd.to_numeric(df["jumlah"], errors="coerce").fillna(0)
    df = df.dropna(subset=["tanggal"]).sort_values("tanggal").reset_index(drop=True)
    df["periode"] = df["tanggal"].apply(lambda d: periode_key(d, payday))
    signed = df.apply(lambda r: r["jumlah"] if r["tipe"] == "Pemasukan" else -r["jumlah"], axis=1)
    df["saldo"] = saldo_awal + signed.cumsum()
    return df


def rekap(df):
    """Ringkasan per periode."""
    if df is None or len(df) == 0:
        return pd.DataFrame()
    out = []
    for key, s in df.groupby("periode"):
        pem = s.loc[s.tipe == "Pemasukan", "jumlah"].sum()
        peng = s.loc[s.tipe == "Pengeluaran", "jumlah"].sum()
        inv = s.loc[s.tipe == "Investasi", "jumlah"].sum()
        row = {
            "periode": key, "label": periode_label(key),
            "salary": s.loc[(s.tipe == "Pemasukan") & (s.kategori == "Salary"), "jumlah"].sum(),
            "side": s.loc[(s.tipe == "Pemasukan") & (s.kategori == "Side Income"), "jumlah"].sum(),
            "pemasukan": pem, "pengeluaran": peng, "investasi": inv,
            "surplus": pem - peng - inv,
            "savings_rate": (pem - peng) / pem if pem else 0.0,
            "invest_rate": inv / pem if pem else 0.0,
        }
        for grp in GROUPS:
            row[grp] = s.loc[s.group == grp, "jumlah"].sum()
        out.append(row)
    return pd.DataFrame(out).sort_values("periode").reset_index(drop=True)


def period_summary(df, key):
    """Detail satu periode: total, breakdown group & kategori."""
    s = df[df.periode == key]
    pem = s.loc[s.tipe == "Pemasukan", "jumlah"].sum()
    peng = s.loc[s.tipe == "Pengeluaran", "jumlah"].sum()
    inv = s.loc[s.tipe == "Investasi", "jumlah"].sum()
    grp = (s[s.tipe == "Pengeluaran"].groupby("group")["jumlah"].sum()
           .reindex(GROUPS).fillna(0))
    kat = (s[s.tipe == "Pengeluaran"].groupby("kategori")["jumlah"].sum()
           .sort_values(ascending=False))
    return {
        "pemasukan": pem, "pengeluaran": peng, "investasi": inv,
        "surplus": pem - peng - inv,
        "savings_rate": (pem - peng) / pem if pem else 0.0,
        "invest_rate": inv / pem if pem else 0.0,
        "salary": s.loc[(s.tipe == "Pemasukan") & (s.kategori == "Salary"), "jumlah"].sum(),
        "side": s.loc[(s.tipe == "Pemasukan") & (s.kategori == "Side Income"), "jumlah"].sum(),
        "group": grp, "kategori": kat,
    }


def rp(x):
    try:
        return "Rp" + f"{float(x):,.0f}".replace(",", ".")
    except Exception:
        return "Rp0"
