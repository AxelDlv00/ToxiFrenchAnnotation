# ╔═══════════════════════════════════════════════════════════════════╗
# ║                           LIBRARIES                               ║
# ╚═══════════════════════════════════════════════════════════════════╝

import streamlit as st
import pandas as pd
import random
from pathlib import Path
from streamlit_extras.let_it_rain import rain
from utils.google_sheet_handler import GoogleSheetHandler
import markdown as md

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                          GLOBAL PATHS                             ║
# ╚═══════════════════════════════════════════════════════════════════╝

ROOT            = Path(".")
PATH_DATA       = ROOT      / "data"
PROXY_PATH      = PATH_DATA / "proxy.txt"
CONSIGNES_PATH  = PATH_DATA / "consignes_annotations.md"
DATA_PATH       = PATH_DATA / "auto_agreement_checking.csv" 

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                        GLOBAL VARIABLES                           ║
# ╚═══════════════════════════════════════════════════════════════════╝

# secrets
proxy       = PROXY_PATH.read_text().strip() if not st.secrets.get("on_streamlit_cloud") else None
sheet_url   = st.secrets["sheet_url"]
secrets     = st.secrets["gcp_service_account"]

# consignes
consignes = CONSIGNES_PATH.read_text(encoding="utf-8")

# Colors 
color_map = {
    "current_text": "#151515",  
    "important_text": "#B60000",  
    "warning": "#ffb700",  # yellow
    "background_box_1": "#fef3c7",  # light yellow
    "background_box_2": "#e0f2fe",  # light blue
    "background_box_3": "#fecfff",  # light purple
    "S": "#f86969",  # red
    "H": "#ffcc3e",  # yellow
    "V": "#93c5fd",  # blue
    "R": "#3de496",  # green
    "A": "#d8b4fe",  # purple
    "I": "#ffa04d",  # orange
    "note": "#fd7fff",  
    "categorie": "#fd7fff",  
}
# ╔═══════════════════════════════════════════════════════════════════╗
# ║                  GOOGLE SHEET AUTHENTIFICATION                    ║
# ╚═══════════════════════════════════════════════════════════════════╝

@st.cache_resource
def get_google_handler(proxy: str, sheet_url: str, _secrets: dict) -> GoogleSheetHandler:
    return GoogleSheetHandler(proxy=proxy, sheet_url=sheet_url, secrets=_secrets)

google_handler = get_google_handler(
    proxy=proxy,
    sheet_url=sheet_url,
    _secrets=secrets,  # Underscore ensures Streamlit skips hashing
)

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                          CONFIGURATION                            ║
# ╚═══════════════════════════════════════════════════════════════════╝

margins = 10
st.markdown(
    f"""
    <style>
    .block-container {{
        padding-left: {margins}rem !important;
        padding-right:{margins}rem !important;
        max-width: 100% !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(f'<div style="background-color: {color_map["warning"]}; color: {color_map["current_text"]}; padding: 10px; border-radius: 5px; text-align: center;">⚠⚠⚠ <b>Avertissement</b> : certains contenus affichés peuvent être <span style="color:{color_map["important_text"]};"><b>très offensants</b></span> ou choquants. ⚠⚠⚠</div>', unsafe_allow_html=True)

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                             HELPERS                               ║
# ╚═══════════════════════════════════════════════════════════════════╝

@st.cache_data(show_spinner=False)
def load_dataset(path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8").dropna()
    df = df.drop_duplicates(subset=["msg_id"], keep="last")
    df.reset_index(drop=True, inplace=True)
    return df

def init_session(df_len: int) -> None:
    keys_defaults = {
        "current_annotations": [],
        "previous_annotations": [],
        "sample_indices": [],
        "index": 0,
        "pseudo": "",
        "n_elements": min(10, df_len),
        "do_rerun": False,
    }
    for k, v in keys_defaults.items():
        st.session_state.setdefault(k, v)

def pick_sample(population: list[int], k: int) -> list[int]:
    return random.sample(population, k)

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                               APP                                 ║
# ╚═══════════════════════════════════════════════════════════════════╝

df_messages = load_dataset(DATA_PATH)
init_session(len(df_messages))

if not st.session_state.index:
    # ───── Session config panel ──────────────────────────────────────────
    with st.expander("🔧 Configuration de session", expanded=not st.session_state.sample_indices):
        st.markdown(consignes, unsafe_allow_html=True)
        st.session_state.pseudo = st.text_input(
            "Entrez votre pseudo (sans espaces)",
            value=st.session_state.pseudo,
            max_chars=30,
        ).strip()
        st.session_state.n_elements = st.number_input(
            "Combien d’éléments voulez-vous annoter pendant cette session ? (Attention ! Pour rendre le site plus réactif, ils ne seront enregistrés qu'à la fin !)",
            min_value=1,
            max_value=len(df_messages),
            value=st.session_state.n_elements,
            step=1,
        )

        pseudo = st.session_state.pseudo
        already_ids = set()

        if pseudo and " " not in pseudo:
            try:
                df_sheet = google_handler.to_pandas(types={"msg_id": str, "score": float})
                df_sheet = df_sheet[df_sheet["user"] == pseudo]
                df_sheet = df_sheet.drop_duplicates(subset=["msg_id"], keep="last")
                df_inrange = df_sheet[df_sheet["msg_id"].astype(str).isin(df_messages["msg_id"].astype(str))]
                st.session_state.previous_annotations = df_inrange.to_dict("records")
                already_ids = set(df_inrange["msg_id"].astype(str).tolist())
                to_annotate = df_messages.copy()
                st.info(f"Vous avez déjà annoté **{len(df_inrange)}** sur un total de **{len(to_annotate)}** messages à annoter.")
            except Exception as e:
                st.error(f"Lecture Google Sheet impossible : {e}")

        if st.button("Démarrer / Continuer l’annotation"):
            if not pseudo or " " in pseudo:
                st.warning("Veuillez entrer un pseudo valide.")
                st.stop()

            if not st.session_state.sample_indices:
                available = to_annotate[
                    ~to_annotate["msg_id"].astype(str).isin(already_ids)
                ].index.tolist()

                if not available:
                    st.success("🎉 Vous avez déjà annoté tous les messages !")
                    st.stop()
                k = min(st.session_state.n_elements, len(available))
                st.session_state.sample_indices = pick_sample(available, k)
                st.session_state.index = 0
            st.rerun()

# ───── Annotation interface ──────────────────────────────────────────
if not st.session_state.sample_indices:
    st.stop()

if st.session_state.index >= len(st.session_state.sample_indices):
    rain(emoji="🎉", font_size=54, falling_speed=15, animation_length="infinite")
    st.title("🎉 Session terminée !")
    st.markdown(f"Merci {st.session_state.pseudo} !")
    st.markdown(f"Vous avez annoté **{len(st.session_state.current_annotations)}** messages lors de cette session.")
    try:
        google_handler.append_rows(st.session_state.current_annotations)
        st.success("Annotations enregistrées dans Google Sheets.")
    except Exception as e:
        st.error(f"Erreur lors de l’enregistrement : {e}")
    st.stop()

idx = st.session_state.sample_indices[st.session_state.index]
row = df_messages.loc[idx]

st.markdown('<a name="evaluation"></a>', unsafe_allow_html=True)
st.markdown(f"### Votre évaluation de l'analyse — {st.session_state.index + 1}e message sur {len(st.session_state.sample_indices)}")

# ───── Message displayed ─────────────────────────────────────────────
# st.markdown("---")
st.markdown(f"""
<div style="background-color:{color_map["background_box_2"]}; color: {color_map["current_text"]}; padding: 15px; border-radius: 5px; margin-bottom: 1rem;">
    <b style="color:{color_map["current_text"]};">Message original :</b><br>
    <div style="color:{color_map["current_text"]};">{row.get("content", "")}</div>
</div>
""", unsafe_allow_html=True)
st.markdown(f'Ce contenu est-il **toxique** ?')
# cols = st.columns(2)
RATING_CHOICES = {
    "oui": 1,
    "non": 0,
    "je ne sais pas, peut-être oui": 0.75,
    "je ne sais pas, peut-être non": 0.25,
}

# ───── Rating buttons ────────────────────────────────────────────────
def _submit(label):
    annotation = {
        "msg_id": row["msg_id"],
        "agree": label,
        "score": RATING_CHOICES[label],
        "user": st.session_state.pseudo,
    }
    st.session_state.current_annotations.append(annotation)
    st.session_state.index += 1
    st.session_state.do_rerun = True

# Buttons for rating displayed 
for i, (label, _) in enumerate(RATING_CHOICES.items()):
    # with cols[i]:
    st.button(label, on_click=_submit, args=(label,))

# ───── Explication displayed ─────────────────────────────────────────
st.markdown("**Explication générée automatiquement à titre indicatif**")
st.markdown(f"""
<div style="background-color:{color_map["background_box_3"]}; color: {color_map["current_text"]}; padding: 15px; border-radius: 5px; margin-bottom: 1rem;">
    <div style="color:{color_map["current_text"]};">{md.markdown(row.get("explication", ""))}</div>
</div>
""", unsafe_allow_html=True)

if st.session_state.get("do_rerun"):
    st.session_state.do_rerun = False
    st.rerun()