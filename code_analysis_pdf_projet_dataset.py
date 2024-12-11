import streamlit as st
import pandas as pd
import re
import fitz  # PyMuPDF
import os

# Fonction pour extraire le texte d'un fichier PDF avec PyMuPDF en français
def extract_text_from_pdf_with_pymupdf(pdf_path):
    try:
        text = ""
        with fitz.open(pdf_path) as doc:
            for page_num in range(len(doc)):
                text += doc.load_page(page_num).get_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Erreur lors de l'extraction du texte du PDF avec PyMuPDF : {e}")
        return ""

# Fonction pour extraire les informations clés de la description du projet
def extract_key_information(project_description):
    key_information = {}
    sections = [
        ("Nom du projet", r"(?i)nom du projet[:\s]*(.*?)(?=objectifs|compétences|détails|$)"),
        ("Objectifs", r"(?i)objectifs[:\s]*(.*?)(?=compétences|détails|$)"),
        ("Compétences requises", r"(?i)compétences requises[:\s]*(.*?)(?=détails|$)"),
        ("Détails supplémentaires", r"(?i)détails supplémentaires[:\s]*(.*?)(?=$)")
    ]

    for section, pattern in sections:
        match = re.search(pattern, project_description, re.DOTALL)
        if match:
            key_information[section] = match.group(1).strip()

    return key_information

# Fonction pour charger les données employés
def load_data(filepath):
    """
    Charge les données depuis un fichier Excel, CSV ou TSV en fonction de son extension.
    Nettoie les valeurs manquantes.
    """
    file_extension = os.path.splitext(filepath)[1].lower()

    if file_extension == '.csv':
        data = pd.read_csv(filepath)
    elif file_extension == '.tsv':
        data = pd.read_csv(filepath, sep='\t')
    elif file_extension == '.xlsx' or file_extension == '.xls':
        data = pd.read_excel(filepath)
    else:
        raise ValueError(f"Format de fichier non supporté: {file_extension}")

    # Suppression des lignes avec des valeurs manquantes
    data = data.dropna()
    return data

# Fonction pour recommander des employés basés sur les compétences requises
def recommend_employees(data, required_keywords, top_n=5):
    required_keywords = [word.strip().lower() for word in required_keywords.split()]
    employee_scores = []

    # Pondérations des différentes catégories
    weights = {
        'skills': 3,
        'activities': 2,
        'education': 1,
        'training': 1
    }

    for index, row in data.iterrows():
        employee = row['Nom']
        employee_characteristics = {
            'skills': str(row['Compétence']).lower(),
            'activities': str(row['Activity']).lower(),
            'education': str(row['Institution']).lower(),
            'training': str(row['Diplôme']).lower()
        }

        # Calcul du score de correspondance avec des critères supplémentaires
        score = 0
        keyword_count = len(required_keywords)

        # Comparaison des mots-clés requis avec les caractéristiques de l'employé
        for keyword in required_keywords:
            for category, characteristics in employee_characteristics.items():
                if keyword in characteristics:
                    # Augmenter le score selon la pondération de la catégorie
                    score += weights[category]

        # Ajuster le score pour la correspondance des technologies (technologies spécifiques ont plus de poids)
        tech_keywords = ['python', 'java', 'c++', 'sql', 'machine learning', 'django']
        tech_score = sum(weights['skills'] for tech in tech_keywords if tech in employee_characteristics['skills'])
        score += tech_score

        # Normaliser le score pour éviter des scores trop élevés ou négatifs
        normalized_score = max(score / max(keyword_count, 1), 0)

        employee_scores.append((employee, normalized_score, row))

    # Trier les employés par score décroissant
    employee_scores = sorted(employee_scores, key=lambda x: x[1], reverse=True)[:top_n]

    st.subheader("Employés recommandés pour travailler sur le projet basé sur les mots-clés extraits de la description :")
    for employee, score, details in employee_scores:
        with st.expander(f"Employé : {employee}, Score de correspondance : {score:.2f}"):
            for column in data.columns:
                st.write(f"{column} : {details[column]}")

    return employee_scores

# Fonction principale pour orchestrer toutes les étapes
def main():
    st.title("Analyse de Projet et de Ressources")
    st.write("Soumettez une description de projet (texte ou PDF via PyMuPDF) pour extraire les informations clés.")

    # Utiliser l'état de Streamlit pour conserver les informations extraites
    if 'extracted_info' not in st.session_state:
        st.session_state.extracted_info = None

    # Choisir entre zone de texte ou fichier PDF
    input_option = st.radio("Choisissez le mode de soumission de la description du projet :", ["Écrire la description", "Soumettre un fichier PDF"])

    project_description = ""
    if input_option == "Écrire la description":
        # Zone de texte pour la description du projet
        project_description = st.text_area("Description du Projet", placeholder="Entrez ici la description du projet...")
    else:
        # Téléchargement du fichier PDF
        uploaded_pdf = st.file_uploader("Téléchargez le fichier PDF contenant la description du projet", type=["pdf"])
        if uploaded_pdf:
            pdf_path = f"/tmp/{uploaded_pdf.name}"
            with open(pdf_path, "wb") as f:
                f.write(uploaded_pdf.getbuffer())
            project_description = extract_text_from_pdf_with_pymupdf(pdf_path)

    if st.button("Analyser la description du projet") and project_description.strip():
        # Extraire les informations du projet
        st.session_state.extracted_info = extract_key_information(project_description)

    # Si les informations du projet ont été extraites, continuer
    if st.session_state.extracted_info:
        # Afficher les informations clés extraites
        st.subheader("Informations Clés Extraites du Projet")
        for key, value in st.session_state.extracted_info.items():
            st.write(f"**{key}**: {value}")

        # Étape suivante : Téléchargement du fichier des employés
        uploaded_file = st.file_uploader("Étape Suivante : Téléchargez le fichier des employés (format CSV ou Excel)", type=["csv", "xlsx"])

        if uploaded_file:
            # Charger les données des employés
            try:
                if uploaded_file.name.endswith(".csv"):
                    employee_df = pd.read_csv(uploaded_file)
                elif uploaded_file.name.endswith(".xlsx"):
                    employee_df = pd.read_excel(uploaded_file)
                else:
                    st.error("Format de fichier non pris en charge. Veuillez télécharger un fichier CSV ou Excel.")
                    return
                st.success("Fichier des employés chargé avec succès.")
            except Exception as e:
                st.error(f"Erreur lors du chargement du fichier : {e}")
                return

            # Vérifier les colonnes requises
            required_columns = ["Nom", "Compétence", "Activity", "Institution", "Diplôme"]
            if not all(col in employee_df.columns for col in required_columns):
                st.error(f"Le fichier doit contenir les colonnes suivantes : {', '.join(required_columns)}")
                return

            # Sélection du nombre d'employés à recommander
            top_n = st.slider("Nombre d'employés à recommander", min_value=1, max_value=20, value=5)

            # Recommander des employés en fonction des mots-clés extraits
            if 'extracted_info' in st.session_state and st.session_state.extracted_info:
                recommend_employees(employee_df, st.session_state.extracted_info.get("Compétences requises", ""), top_n)
            else:
                st.error("Aucun mot-clé requis spécifié dans la description du projet.")

if __name__ == "__main__":
    main()
