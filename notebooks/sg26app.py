from pathlib import Path

import pandas as pd
import streamlit as st

# --- Seite konfigurieren ---
st.set_page_config(
    page_title="Va'a Sprint WM 2026 - Timeschedule", page_icon="🚣", layout="wide"
)

# --- Titel und Beschreibung ---
# Schreibe im markdown anstelle von "Wähle einen **Namen** aus" "Dies sind die Startzeiten für den im Filter ausgewählten Namen. Wähle einen anderen Namen aus, um die Startzeiten für diesen Namen anzuzeigen."
st.title("Va'a Sprint WM 2026 - Timeschedule")
st.markdown("""
These are the start times for the selected name. Choose a different name to view the start times for that name.
""")

# Füge eine Auswahl mit Radio-Buttons hinzu, um zwischen Timeschedule April und June zu wechseln. Standardmäßig ist Timeschedule June ausgewählt.
timeschedule_option = st.radio(
    "Choose Timeschedule:",
    ("Timeschedule April 2026", "Timeschedule June 2026"),
    index=1,
)
# Wenn die Auswahl neu getroffen wird, sollen die Daten neu eingelesen werden


# --- CSV-Datei laden ---
# Wähle die CSV-Datei basierend auf der Auswahl im Radio-Button. Wenn "Timeschedule April 2026" ausgewählt ist, lade "SG26_timeschedule_with_names_april26.csv", andernfalls lade "SG26_timeschedule_with_names_june22.csv".


@st.cache_data  # Cache die Daten, um Ladezeiten zu reduzieren
def load_data(selected_timeschedule: str):
    # data_path = Path(__file__).resolve().parent / "SG26_timeschedule_with_names.csv"
    if selected_timeschedule == "Timeschedule April 2026":
        data_path = (
            Path(__file__).resolve().parent / "SG26_timeschedule_with_names_april26.csv"
        )
    else:
        data_path = (
            Path(__file__).resolve().parent / "SG26_timeschedule_with_names_june22.csv"
        )
    df = pd.read_csv(data_path, sep=";", engine="python", encoding="utf-8")

    # Datum in datetime umwandeln und Wochentag hinzufügen
    df["Datum"] = pd.to_datetime(df["DATE"], dayfirst=True, errors="coerce")

    # Uhrzeit extrahieren, falls START vorhanden ist
    if "START" in df.columns:
        start_times = pd.to_datetime(df["START"], format="%I:%M %p", errors="coerce")
        df["Uhrzeit"] = start_times.dt.strftime("%H:%M").fillna(df["START"].astype(str))

    # Kategorie und Runde aus vorhandenen Spalten erzeugen
    if "CLASS" in df.columns:
        df["Kategorie"] = df["CLASS"].astype(str)
        if "BOAT" in df.columns:
            df["Kategorie"] = (
                df["Kategorie"]
                + " "
                + df["BOAT"].astype(str)
                + " "
                + df["DISTANCE"].astype(str)
                + " m"
            )
    if "ROUND" in df.columns:
        df["Runde"] = df["ROUND"]

    # Namen normalisieren
    # Füge in der Spalte "Name" in jeder Zelle ", GER" hinzu, wenn "GER" nicht in der Spalte "NAME" vorkommt
    df["Name"] = df["NAME"] if "NAME" in df.columns else df.get("Name", pd.NA)
    df["Name"] = df["Name"].apply(
        lambda x: f"{x}, GER" if pd.notna(x) and "GER" not in str(x) else x
    )

    df["Wochentag"] = df["Datum"].dt.strftime("%A")  # z. B. "Montag"
    df["Tag"] = df["Datum"].dt.day  # Tag des Monats (20, 21, etc.)
    return df


df = load_data(timeschedule_option)

# --- Filter oben unter dem Titel ---
# Passe die Filteranzeige so an, dass als erste Option "GER" angezeigt wird, gefolgt von allen anderen Namen in alphabetischer Reihenfolge.
# Erlaube eine mehrfache Auswahl von Namen, damit die Startzeiten für mehrere Namen gleichzeitig angezeigt werden können.
# Die ausgewählten Namen sollen in der Anzeige fett dargestellt werden.

st.header("🔍 Filter")
all_names = sorted(
    {name.strip() for names in df["Name"].dropna() for name in str(names).split(",")}
)
all_names = ["GER"] + [name for name in all_names if name != "GER"]
selected_names = st.multiselect("Choose names:", all_names, default=["GER"])

if selected_names:
    filter_condition = df["Name"].apply(
        lambda x: (
            any(
                selected in [name.strip() for name in str(x).split(",")]
                for selected in selected_names
            )
            if pd.notna(x)
            else False
        )
    )
else:
    filter_condition = pd.Series(False, index=df.index)

# --- Daten filtern und sortieren ---
filtered_df = df[filter_condition].sort_values(["Datum", "Uhrzeit"])

# --- Ergebnisse anzeigen ---
# if not filtered_df.empty:
#    st.subheader(f"📅 Startzeiten für: **{selected}**")
#    st.dataframe(
#        filtered_df[['Tag', 'Datum', 'Uhrzeit', 'Kategorie', 'Runde']],
#        hide_index=True,
#        use_container_width=True,
#        height=400
#    )
# else:
#    st.warning("Keine Daten für die gewählte Auswahl gefunden.")
#
## --- Option: Alle Daten anzeigen ---
# if st.checkbox("Alle Daten anzeigen"):
#    st.dataframe(df, hide_index=True, use_container_width=True)

# --- Alle einzigartigen Tage zwischen 20.08. und 30.08. extrahieren ---
all_dates = pd.date_range(start="2026-08-20", end="2026-08-30", freq="D")
all_dates_names = [date.strftime("%d.%m.%Y") for date in all_dates]
all_dates_weekdays = [date.strftime("%A") for date in all_dates]

# --- Für jeden Tag die Rennen anzeigen ---
# Schreibe jede Zeile, die in der Spalte "Kategorie" den Text "Women" enthält in roter Farbe und wenn "Men" enthalten ist in blauer Farbe
for date, date_name, weekday in zip(all_dates, all_dates_names, all_dates_weekdays):
    # Filtere Rennen für diesen Tag
    day_df = filtered_df[filtered_df["Datum"].dt.strftime("%d.%m.%Y") == date_name]

    # Überschrift für den Tag
    st.markdown("---")
    st.subheader(f"📅 **Day {date.day} – {date_name} ({weekday})**")

    if day_df.empty:
        st.info("No Race! :-)")
    else:
        # Tabelle für die Rennen dieses Tages
        # In der Anzeige soll das Datum nicht angezeigt werden, sondern nur die Uhrzeit, Kategorie, Runde und Name.
        # Die Spaltennamen sollen nicht angezeigt werden, sondern nur die Werte.
        # Die Zeilen, die in der Spalte "Kategorie" den Text "Women" enthalten, sollen in roter Farbe angezeigt werden,
        # wenn "Men" enthalten ist, dann in blauer Farbe.

        day_df_display = day_df[["Uhrzeit", "Kategorie", "Runde", "Name"]].copy()

        # Erzeuge HTML-Tabelle ohne Header
        rows = []
        for _, row in day_df_display.iterrows():
            category = str(row["Kategorie"])
            row_style = ""
            if "Women" in category:
                row_style = "background-color:#ffe6e6;"
            elif "Men" in category:
                row_style = "background-color:#e6f0ff;"

            name_value = str(row["Name"])
            name_parts = [part.strip() for part in name_value.split(",")]
            formatted_name = ", ".join(
                f"<strong>{part}</strong>" if part in selected_names else part
                for part in name_parts
            )

            row_cells = "".join(
                f"<td style='padding:6px; border:none; text-align:left;'>{str(row[col]) if col != 'Name' else formatted_name}</td>"
                for col in ["Uhrzeit", "Kategorie", "Runde", "Name"]
            )
            rows.append(f"<tr style='{row_style}'>{row_cells}</tr>")

        table_html = (
            "<table style='border-collapse:collapse; width:100%;'>"
            + "".join(rows)
            + "</table>"
        )
        st.markdown(table_html, unsafe_allow_html=True)

# --- Footer ---
st.markdown("---")
st.caption("IVF Va'a World Elite and Club Sprint Championship 2026 | Singapore")
st.caption("Data Source: Event Schedule 26 April 2026 - from IVF Website")
st.caption("Data Source: Event Schedule 22 June 2026 - from IVF Website")
# Write Website as link to https://www.kanu.de/-Vaa-World-Sprint-Championships-2026-Nationalteam-ist-komplett-94564.html
st.caption(
    "Data Source: DKV National Team Nominations - from [DKV Website...](https://www.kanu.de/-Vaa-World-Sprint-Championships-2026-Nationalteam-ist-komplett-94564.html)"
)
st.caption("Florian Späth - 2026")
