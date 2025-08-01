import streamlit as st
import requests
import pandas as pd
import pydeck as pdk
import matplotlib.pyplot as plt
import matplotlib.cm as cm

# Configuration API
# API_BASE = "https://127.0.0.1:8000/"
API_BASE = "https://backend-v2-i0b9.onrender.com/"
UPLOAD_ENDPOINT = f"{API_BASE}upload/"
PROCESS_ENDPOINT = f"{API_BASE}process/"

st.title("Optimisation logistique")
st.markdown("📁 **Chargez vos deux fichiers Excel** (principal + BDD).")

# 🔁 Fonction de chargement générique
def charger_fichier_excel(label, uploader_key, session_key_id, session_key_df):
    uploaded_file = st.file_uploader(label, type=["xlsx"], key=uploader_key)
    if uploaded_file and session_key_id not in st.session_state:
        with st.spinner(f"Envoi de {label}..."):
            response = requests.post(UPLOAD_ENDPOINT, files={"file": uploaded_file})
            if response.status_code == 200:
                st.session_state[session_key_id] = response.json()["file_id"]
                st.session_state[session_key_df] = pd.read_excel(uploaded_file)
                st.success("✅ Fichier envoyé avec succès !")
            else:
                st.error("❌ Échec de l'envoi.")
    return uploaded_file

# 📂 Chargement des deux fichiers Excel
charger_fichier_excel("📄 Fichier principal (commandes)", "main_file_uploader", "file_id", "df_uploaded")
charger_fichier_excel("📄 Fichier BDD NUTS", "bdd_file_uploader", "file_id2", "bdd_df")

# ✔️ Si les deux fichiers sont chargés
if "df_uploaded" in st.session_state and "bdd_df" in st.session_state:
    df = st.session_state["df_uploaded"]
    st.subheader("Aperçu des données principales")
    st.dataframe(df.head())

    colonnes = df.columns.tolist()
    Col_NUTS = st.selectbox("Colonne ", colonnes)
    # Col_Code_postal = st.selectbox("Colonne Code postal", colonnes)
    Nb_entrepot = st.text_input("Nombre d'entrepôts", "1")
    maille = st.selectbox("Maille", ["Pays", "NUTS_1", "NUTS_2", "NUTS_3", "IRIS"])
    optimization = st.selectbox("Type d'optimisation", ["Aucune", "Opti_Solveur", "Entrepots multiples"])
    affichage_nuts = st.checkbox("Afficher les zones NUTS")
    ponderation = st.checkbox("Activer la pondération")

    param1 = param2 = param3 = poids1 = poids2 = poids3 = None
    if ponderation:
        st.subheader("Choix des colonnes pondératrices")
        nb_colonnes = st.selectbox("Nombre de colonnes", [1, 2, 3], index=2)

        if nb_colonnes >= 1:
            param1 = st.selectbox("Colonne 1", colonnes, key="param1")
            poids1 = st.number_input("% poids 1", 0, 100, 50, key="poids1")
        if nb_colonnes >= 2:
            param2 = st.selectbox("Colonne 2", colonnes, key="param2")
            poids2 = st.number_input("% poids 2", 0, 100, 50, key="poids2")
        if nb_colonnes == 3:
            param3 = st.selectbox("Colonne 3", colonnes, key="param3")
            poids3 = st.number_input("% poids 3", 0, 100, 0, key="poids3")

        if sum(filter(None, [poids1, poids2, poids3])) != 100:
            st.warning("⚠️ La somme des poids doit être égale à 100%.")

    # 🚀 Lancer l’optimisation
    if st.button("🚀 Lancer l’optimisation") and optimization != "Aucune":
        with st.spinner("Traitement en cours..."):
            params = {
                "file_id": st.session_state["file_id"],
                "file_id2": st.session_state["file_id2"],
                "optimization": optimization,
                "maille": maille,
                "Nb_entrepot": Nb_entrepot,
                "Col_NUTS": Col_NUTS,
                
            }

            # Pondération
            params.update({k: v for k, v in {
                "param1": param1,
                "param2": param2,
                "param3": param3,
                "poids1": poids1,
                "poids2": poids2,
                "poids3": poids3,
            }.items() if v is not None})

            response = requests.post(PROCESS_ENDPOINT, data=params)

        if response.status_code == 200:
            data = response.json()
            st.session_state.df_result = pd.DataFrame(data["entrepots"])
            st.session_state.df_affectation = pd.DataFrame(data["affectation"])
            st.success("🎉 Optimisation terminée !")
            st.experimental_rerun()
        else:
            st.error(f"❌ Erreur API : {response.status_code}")
            st.write("🔎 Détail de l'erreur :")
            st.code(response.text, language="json")

# 📈 Affichage des résultats
if "df_result" in st.session_state and "df_affectation" in st.session_state:
    df_result = st.session_state.df_result
    df_affectation = st.session_state.df_affectation

    st.download_button("📥 Télécharger entrepôts", df_result.to_csv(index=False), "entrepots.csv")
    st.download_button("📥 Télécharger affectations", df_affectation.to_csv(index=False), "affectation.csv")

    if "x" in df_result.columns and "y" in df_result.columns:
        lon_center = df_result["x"].mean()
        lat_center = df_result["y"].mean()

        layers = [
            pdk.Layer("ScatterplotLayer", data=df_result, get_position='[x, y]', get_color='[200, 30, 0, 160]', get_radius=10000)
        ]

        if affichage_nuts:
            cmap = plt.get_cmap("tab10")
            clusters = sorted(df_affectation["Cluster"].unique())
            colors = {cl: [int(c * 255) for c in cmap(i % 10)[:3]] + [160] for i, cl in enumerate(clusters)}
            df_affectation["fill_color"] = df_affectation["Cluster"].map(colors)
            df_affectation["geometry"] = df_affectation["geometry"].apply(lambda g: {"type": g["type"], "coordinates": g["coordinates"]})
            layers.insert(0, pdk.Layer("GeoJsonLayer", data=df_affectation.to_dict("records"), get_fill_color="fill_color", opacity=0.4))

        view_state = pdk.ViewState(latitude=lat_center, longitude=lon_center, zoom=4)
        st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view_state))

# 🔄 Réinitialisation
if st.button("🔁 Réinitialiser tout"):
    for key in ["file_id", "df_uploaded", "file_id2", "bdd_df", "df_result", "df_affectation"]:
        st.session_state.pop(key, None)
    st.experimental_rerun()
