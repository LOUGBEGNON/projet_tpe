import streamlit as st
import pandas as pd
import fitz  # PyMuPDF pour l'extraction de texte à partir de PDF
import os
import random
import uuid
import re
from datetime import datetime
from collections import defaultdict

# Variable globale pour stocker les données de rating
rating_data = pd.DataFrame()

# Liste des mots à exclure
EXCLUDED_WORDS = [
    "ID", "Nom", "Prénom", "Âge", "Sexe", "Nationalité", "Compétence", "Niveau de Maîtrise", "Diplôme",
    "Institution", "Année de Obtention", "Titre du Poste", "Entreprise", "Durée", "Projets Clés", "Activity",
    "Name", "Surname", "Age", "Gender", "Nationality", "Skills", "Mastery Level", "Degree", "Institution",
    "Year of Graduation", "Job Title", "Company", "Duration", "Key Projects", "Activity", "Education"
]

# Fonctions pour extraire le texte du CV avec PyMuPDF
def extract_text_from_pdf(pdf_path):
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        st.error(f"Erreur lors de l'extraction du texte du PDF : {e}")
        return None

# Fonctions pour extraire et nettoyer le texte du CV
def segment_text_into_sections(text):
    sections_regex = {
        re.compile(r"(nom[s]?|name)", re.IGNORECASE): "Nom",
        re.compile(r"(prénom[s]?|surname|first name)", re.IGNORECASE): "Prénom",
        re.compile(r"(date de naissance|birth date|dob)", re.IGNORECASE): "Date de Naissance",
        re.compile(r"(expérience[s]? professionnelle[s]?|professional experience)", re.IGNORECASE): "Expérience Professionnelle",
        re.compile(r"(éducation|education|formation[s]?|training|école|université|institut|centre de formation)", re.IGNORECASE): "Éducation",
        re.compile(r"(compétence[s]?|skills)", re.IGNORECASE): "Compétences",
        re.compile(r"(langue[s]?|languages)", re.IGNORECASE): "Langues",
        re.compile(r"(projet[s]?|projects)", re.IGNORECASE): "Projets",
        re.compile(r"(certificat[s]?|certificates)", re.IGNORECASE): "Certifications",
        re.compile(r"(publication[s]?|publications?)", re.IGNORECASE): "Publications",
        re.compile(r"(référence[s]?|references)", re.IGNORECASE): "Références",
        re.compile(r"(objectifs|objectives)", re.IGNORECASE): "Objectifs",
        re.compile(r"(réalisations|achievements)", re.IGNORECASE): "Réalisations",
        re.compile(r"(licence|master|diplôme|bachelor|degree)", re.IGNORECASE): "Diplôme"
    }
    sections_content = {value: "" for value in sections_regex.values()}
    unclassified_content = ""
    current_section = None

    for line in text.split('\n'):
        line = line.strip()
        if line:
            matched = False
            for regex, section_name in sections_regex.items():
                if regex.search(line):
                    current_section = section_name
                    matched = True
                    break
            if current_section and matched:
                sections_content[current_section] += line + " "
            elif not matched:
                unclassified_content += line + " "
    return sections_content, unclassified_content

# Nettoyage du texte extrait
def clean_text(text):
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\u2022\u00b7\u25cf]', '', text)
    text = re.sub(r'[^\w\s,]', '', text)
    words = text.split()
    text = " ".join(word for word in words if word.lower() not in [w.lower() for w in EXCLUDED_WORDS])
    text = text.strip()
    return text

# Nettoyage des sections
def clean_sections(sections):
    cleaned_sections = {}
    for section, content in sections.items():
        if content:
            lines = content.split(". ")
            keywords = [clean_text(line) for line in lines if line.strip()]
            cleaned_sections[section] = keywords
    return cleaned_sections

# Calcul de l'âge
def calculate_age(birth_date_str):
    try:
        birth_date = datetime.strptime(birth_date_str, "%d/%m/%Y")
        today = datetime.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except ValueError:
        return ""

# Extraction des détails de l'expérience
def extract_experience_details(experience_data):
    postes = re.findall(r"([\w\s]+)(?=\s\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})", experience_data)
    entreprises = re.findall(r"Entreprise\s*:\s*(\w+)", experience_data, re.IGNORECASE)
    dates = re.findall(r"(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})", experience_data)
    return postes, entreprises, dates

# Fonction principale
def main():
    st.title("Système de Recommandation d'Activités pour Employés")

    st.sidebar.header("Configuration des Poids")
    config = {
        'columns': {
            'employee': 'Nom',
            'skills': 'Compétence',
            'education': 'Institution',
            'training': 'Diplôme',
            'activity': 'Activity'
        },
        'weights': {
            'skills': st.sidebar.slider("Poids des Compétences", min_value=0.1, max_value=5.0, value=1.0),
            'education': st.sidebar.slider("Poids de l'Éducation", min_value=0.1, max_value=5.0, value=1.0),
            'training': st.sidebar.slider("Poids des Formations", min_value=0.1, max_value=5.0, value=1.0),
            'activity': st.sidebar.slider("Poids des Activités", min_value=0.1, max_value=5.0, value=1.0)
        }
    }

    # Section pour choisir le type de fichier à uploader
    st.header("Ajouter une nouvelle personne")
    file_type = st.radio("Sélectionnez le type de fichier à télécharger:", ("CV en PDF", "Fichier de données (CSV/Excel)"))

    new_person_data = None
    if file_type == "CV en PDF":
        new_person_file = st.file_uploader("Téléchargez un CV en format PDF", type=["pdf"], key='new_person_pdf')
        if new_person_file:
            # Sauvegarder le fichier CV temporairement
            session_id = str(uuid.uuid4())  # Utiliser un UUID pour éviter les conflits
            session_folder = os.path.join("data", session_id)
            os.makedirs(session_folder, exist_ok=True)
            pdf_path = os.path.join(session_folder, f"{new_person_file.name}")
            with open(pdf_path, "wb") as f:
                f.write(new_person_file.getbuffer())

            # Extraire et nettoyer le texte du CV en utilisant PyMuPDF
            cv_text = extract_text_from_pdf(pdf_path)
            if cv_text:
                cv_sections, unclassified_content = segment_text_into_sections(cv_text)
                cleaned_sections = clean_sections(cv_sections)

                # Calculer l'âge
                birth_date_str = " ".join(cleaned_sections.get("Date de Naissance", []))
                age = calculate_age(birth_date_str) if birth_date_str else ""

                # Extraire les détails d'expérience
                experience_data = " ".join(cleaned_sections.get("Expérience Professionnelle", []))
                postes, entreprises, dates = extract_experience_details(experience_data)

                # Créer un DataFrame à partir des informations extraites
                unique_id = random.randint(700, 900)
                row_data = {
                    "ID": unique_id,
                    "Nom": " ".join(cleaned_sections.get("Nom", [])),
                    "Prénom": " ".join(cleaned_sections.get("Prénom", [])),
                    "Âge": age,
                    "Sexe": "",
                    "Nationalité": "",
                    "Compétence": ", ".join(cleaned_sections.get("Compétences", [])),
                    "Niveau de Maîtrise": "",
                    "Diplôme": ", ".join(cleaned_sections.get("Diplôme", [])),
                    "Institution": ", ".join([inst for inst in cleaned_sections.get("Éducation", []) if
                                                      re.search(r'(\u00e9cole|université|institut|centre de formation)', inst,
                                                                re.IGNORECASE)]),
                    "Année de Obtention": "",
                    "Titre du Poste": ", ".join(postes),
                    "Entreprise": ", ".join(entreprises),
                    "Durée": ", ".join(dates),
                    "Projets Clés": ", ".join(cleaned_sections.get("Projets", [])),
                    "Activity": ""
                }

                new_person_data = pd.DataFrame([row_data])
                st.success("Nouvelle personne ajoutée aux données via CV!")
                st.dataframe(new_person_data)

    elif file_type == "Fichier de données (CSV/Excel)":
        new_person_file = st.file_uploader("Téléchargez un fichier de données en format CSV/Excel", type=["csv", "xlsx", "xls"], key='new_person_data')
        if new_person_file:
            # Charger le fichier de données directement
            file_extension = new_person_file.name.split('.')[-1].lower()
            try:
                if file_extension == 'csv':
                    new_person_data = pd.read_csv(new_person_file)
                elif file_extension in ['xlsx', 'xls']:
                    new_person_data = pd.read_excel(new_person_file)
                else:
                    st.error(f"Format de fichier non supporté: .{file_extension}")
                    return

                if new_person_data.empty:
                    st.error("Le fichier téléchargé est vide. Veuillez fournir un fichier valide.")
                    return
                st.success("Nouvelle personne ajoutée via fichier de données!")
                st.dataframe(new_person_data)
            except Exception as e:
                st.error(f"Erreur lors du chargement des données: {e}")
                return

    # Section pour télécharger le fichier principal (apparaît uniquement après l'ajout de la nouvelle personne)
    if new_person_data is not None:
        st.header("Ajouter les données des employés")
        uploaded_file = st.file_uploader("Téléchargez le fichier de données des employés", type=["csv", "xlsx", "xls"], key='employee_data')
        data = None
        if uploaded_file:
            file_extension = uploaded_file.name.split('.')[-1].lower()
            try:
                if file_extension == 'csv':
                    data = pd.read_csv(uploaded_file)
                elif file_extension in ['xlsx', 'xls']:
                    data = pd.read_excel(uploaded_file)
                else:
                    st.error(f"Format de fichier non supporté: .{file_extension}")
                    return

                if data.empty:
                    st.error("Le fichier téléchargé est vide. Veuillez fournir un fichier valide.")
                    return
                data = pd.concat([data, new_person_data], ignore_index=True)
            except Exception as e:
                st.error(f"Erreur lors du chargement des données: {e}")
                return
        else:
            data = new_person_data

        if data is not None:
            st.success("Données chargées avec succès!")
            st.dataframe(data.head())

            # Calcul des occurrences et normalisation des activités
            try:
                total_occurrences = data.groupby('Activity').size().rename('Total_Occurrences')
                person_activity_counts = data.groupby(['Nom', 'Activity']).size().rename('Person_Activity_Counts').reset_index()
                merged_data = person_activity_counts.merge(total_occurrences, left_on='Activity', right_index=True, how='left')
                merged_data['Activity_Ratio'] = merged_data['Person_Activity_Counts'] / merged_data['Total_Occurrences']
                max_ratios = merged_data.groupby('Activity')['Activity_Ratio'].transform('max')
                merged_data['Normalized_Rating'] = 0
                merged_data.loc[max_ratios > 0, 'Normalized_Rating'] = (
                    (merged_data['Activity_Ratio'] / max_ratios) * 5
                ).round().astype(int)

                # Stockage global pour les recommandations
                global rating_data
                rating_data = merged_data

                st.write("Données normalisées :")
                st.dataframe(rating_data)

                # Recommandation pour une nouvelle personne
                if 'Nom' in new_person_data.columns and not new_person_data.empty:
                    if new_person_data['Nom'].iloc[0]:
                        target_employee = new_person_data['Nom'].iloc[0]
                        top_n = st.slider("Nombre de recommandations", min_value=1, max_value=20, value=5)

                        if st.button("Calculer les recommandations"):
                            similarities = defaultdict(float)
                            target_data = data[data['Nom'] == target_employee].iloc[0]
                            for _, row in data.iterrows():
                                if row['Nom'] == target_employee:
                                    continue
                                score = 0.0
                                target_skills = set(str(target_data[config['columns']['skills']]).split(',')) if not pd.isna(target_data[config['columns']['skills']]) else set()
                                row_skills = set(str(row[config['columns']['skills']]).split(',')) if not pd.isna(row[config['columns']['skills']]) else set()
                                skill_similarity = len(target_skills & row_skills) / len(target_skills | row_skills) if (target_skills | row_skills) else 0
                                score += skill_similarity * config['weights']['skills']

                                education_similarity = 1 if target_data[config['columns']['education']] == row[config['columns']['education']] else 0
                                score += education_similarity * config['weights']['education']

                                target_training = set(str(target_data[config['columns']['training']]).split(',')) if not pd.isna(target_data[config['columns']['training']]) else set()
                                row_training = set(str(row[config['columns']['training']]).split(',')) if not pd.isna(row[config['columns']['training']]) else set()
                                training_similarity = len(target_training & row_training) / len(target_training | row_training) if (target_training | row_training) else 0
                                score += training_similarity * config['weights']['training']

                                target_activities = set(str(target_data[config['columns']['activity']]).split(',')) if not pd.isna(target_data[config['columns']['activity']]) else set()
                                row_activities = set(str(row[config['columns']['activity']]).split(',')) if not pd.isna(row[config['columns']['activity']]) else set()
                                activity_similarity = len(target_activities & row_activities) / len(target_activities | row_activities) if (target_activities | row_activities) else 0
                                score += activity_similarity * config['weights']['activity']

                                if score > 0:
                                    similarities[row['Nom']] = score

                            if not similarities:
                                st.warning("Aucun employé similaire trouvé. Veuillez vérifier les données disponibles.")
                            else:
                                sorted_similarities = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:top_n]
                                st.write(f"Employés similaires à '{target_employee}' :")
                                for employee, similarity in sorted_similarities:
                                    st.write(f"{employee}, Similarité : {similarity:.4f}")

                                recommended_activities = defaultdict(float)
                                for employee, similarity in sorted_similarities:
                                    employee_data = rating_data[rating_data['Nom'] == employee]
                                    for _, row in employee_data.iterrows():
                                        activity = row['Activity']
                                        rating = row['Normalized_Rating']
                                        recommended_activities[activity] += rating * similarity

                                recommended_activities = sorted(recommended_activities.items(), key=lambda x: x[1], reverse=True)[:top_n]
                                st.write("Activités recommandées :")
                                st.write(pd.DataFrame(recommended_activities, columns=['Activité', 'Score']))
            except Exception as e:
                st.error(f"Erreur lors du calcul des recommandations : {e}")

if __name__ == "__main__":
    main()
