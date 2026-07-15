from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pyrebase  # pip install pyrebase4
import streamlit as st

DATA_FILE_NAMES = [
    "heizung_status_2026_all.log",
    "heizung_status_2026_all.csv",
]


@st.cache_data
def load_heating_data() -> pd.DataFrame:
    base_dir = Path(__file__).resolve().parent

    for file_name in DATA_FILE_NAMES:
        file_path = base_dir / file_name
        if not file_path.exists():
            continue

        if file_path.suffix.lower() in {".txt", ".csv", ".log"}:
            df = pd.read_csv(
                file_path,
                header=None,
                delim_whitespace=True,
                names=["timestamp", "status"],
            )
        elif file_path.suffix.lower() in {".xlsx", ".xls"}:
            df = pd.read_excel(file_path)
        else:
            continue

        if "timestamp" not in df.columns or "status" not in df.columns:
            df = df.iloc[:, :2]
            df.columns = ["timestamp", "status"]

        df = df.loc[:, ["timestamp", "status"]].copy()
        df["timestamp"] = df["timestamp"].astype(str).str.strip()
        df = df[df["timestamp"].notna()]
        df["datetime"] = pd.to_datetime(
            df["timestamp"], format="%Y%m%d_%H%M", errors="coerce"
        )
        df = df.dropna(subset=["datetime"])
        df["status"] = (
            pd.to_numeric(df["status"], errors="coerce").fillna(0).astype(int)
        )
        df["date"] = df["datetime"].dt.date
        df["year"] = df["datetime"].dt.year
        df["month"] = df["datetime"].dt.month
        df["day"] = df["datetime"].dt.day
        return df

    raise FileNotFoundError(
        "Keine Heizungsdaten gefunden. Bitte lege eine der Dateien im Verzeichnis `notebooks/` ab: "
        + ", ".join(DATA_FILE_NAMES)
    )


# Funktion um die Daten aus der Firebase-Datenbank zu laden und in ein DataFrame zu überführen.
def load_heating_data_from_firebase():
    config = {
        "apiKey": st.secrets["firebase_apiKey"],
        "authDomain": st.secrets["firebase_authDomain"],
        "databaseURL": st.secrets["firebase_databaseURL"],
        "storageBucket": st.secrets["firebase_storageBucket"],
    }

    firebase = pyrebase.initialize_app(config)
    db = firebase.database()
    # Daten aus der Firebase-Datenbank laden
    data = db.child("heating_status").get()
    # Lade Daten nur aus 2026
    # Startzeit ist der 01.01.2026 00:00 Uhr
    start_time = datetime(2026, 1, 1, 0, 0)
    start_ms = int(start_time.timestamp() * 1000)
    # Endzeit ist der aktuelle Zeitpunkt
    end_time = datetime.now()
    end_ms = int(end_time.timestamp() * 1000)
    # 2. Daten abfragen (wenn Timestamp als Schlüssel)
    # data = db.child("heating_status").start_at(str(start_ms)).end_at(str(end_ms)).get()

    # Daten in ein Pandas DataFrame überführen
    df = pd.DataFrame([item.val() for item in data.each()])
    # Erzeuge eine neue Spalte 'datetime' aus der 'timestamp'-Spalte. Datumsformat: YYYY-MM-DD HH:MM:SS
    # df['datetime'] = pd.to_datetime(df['timestamp'], format='%Y-%m-%d %H:%M:%S')
    df["datetime"] = pd.to_datetime(
        df["timestamp"], format="%Y%m%d_%H%M", errors="coerce"
    )

    df["status"] = pd.to_numeric(df["status"], errors="coerce").fillna(0).astype(int)
    df["date"] = df["datetime"].dt.date
    df["year"] = df["datetime"].dt.year
    df["month"] = df["datetime"].dt.month
    df["day"] = df["datetime"].dt.day

    return df


@st.cache_data
def aggregate_daily(df: pd.DataFrame) -> pd.DataFrame:
    daily = (
        df.groupby(["year", "month", "date"], as_index=False)["status"]
        .sum()
        .rename(columns={"status": "tagesminuten"})
    )
    daily["day"] = pd.to_datetime(daily["date"]).dt.day
    return daily


def format_month(month_number: int) -> str:
    month_names = {
        1: "Januar",
        2: "Februar",
        3: "März",
        4: "April",
        5: "Mai",
        6: "Juni",
        7: "Juli",
        8: "August",
        9: "September",
        10: "Oktober",
        11: "November",
        12: "Dezember",
    }
    return month_names.get(month_number, str(month_number))


def main() -> None:
    st.title("Heizungsdaten-Auswertung")
    st.markdown(
        "Diese App lädt die Heizungsdaten und zeigt eine Monatsübersicht in einem Balkendiagramm sowie die Tagessummen an."
    )

    try:
        # df = load_heating_data()
        df = load_heating_data_from_firebase()
    except FileNotFoundError as error:
        st.error(str(error))
        return

    daily = aggregate_daily(df)
    years = sorted(daily["year"].unique())

    if not years:
        st.warning("Es wurden keine gültigen Datensätze gefunden.")
        return

    selected_year = st.selectbox("Jahr wählen", years, index=len(years) - 1)
    months = sorted(daily.loc[daily["year"] == selected_year, "month"].unique())
    selected_month = st.selectbox(
        "Monat wählen",
        months,
        format_func=format_month,
        index=max(0, len(months) - 1),
    )

    month_data = daily[
        (daily["year"] == selected_year) & (daily["month"] == selected_month)
    ].sort_values("day")

    if month_data.empty:
        st.info("Für die gewählte Auswahl liegen keine Daten vor.")
        return

    month_name = format_month(selected_month)
    st.subheader(f"{month_name} {selected_year} — Tagesbetriebsminuten")

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(month_data["day"], month_data["tagesminuten"], color="#1f77b4")
    ax.set_xlabel("Tag im Monat")
    ax.set_ylabel("Tagesminuten")
    ax.set_title(f"Heizungsbetriebszeit für {month_name} {selected_year}")
    ax.set_xticks(month_data["day"])
    ax.grid(axis="y", alpha=0.3)
    st.pyplot(fig)

    st.markdown("### Tageswerte")
    display_table = month_data[["date", "tagesminuten"]].copy()
    display_table["date"] = display_table["date"].astype(str)
    display_table["Betriebszeit (Std:Min)"] = display_table["tagesminuten"].apply(
        lambda minutes: f"{minutes // 60:02d}:{minutes % 60:02d}"
    )
    display_table = display_table.rename(
        columns={"date": "Datum", "tagesminuten": "Tagesminuten"}
    )
    st.table(display_table.reset_index(drop=True))

    total_minutes = int(month_data["tagesminuten"].sum())
    hours = total_minutes // 60
    minutes = total_minutes % 60

    st.markdown(
        f"**Monatssumme:** {hours:02d}:{minutes:02d} Stunden ({total_minutes:,} Minuten) Heizungsbetrieb im {month_name} {selected_year}."
    )


if __name__ == "__main__":
    main()
