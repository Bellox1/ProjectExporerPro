# 🚀 Project Explorer Pro (blx)

> [!WARNING]
> **Statut du Projet : Version BETA** ⚠️
> Cet outil est actuellement en phase de développement intensif. Certaines fonctionnalités peuvent être incomplètes ou sujettes à des changements majeurs. Projet **Open Source** développé avec passion par **BELLOX**.

**Project Explorer Pro** (connu sous la commande `blx`) est un outil professionnel conçu pour les développeurs modernes et les utilisateurs d'IA. Il simplifie l'exportation, l'analyse et la préparation de vos bases de code pour une interaction optimale avec les LLM (Claude, GPT-4, Gemini).

---

## 🌟 Pourquoi Project Explorer Pro ?

*   **🤖 Optimisé pour l'IA** : Compressez vos fichiers et fusionnez les lignes pour réduire la consommation de tokens tout en conservant la structure.
*   **💻 Interface Hybride** : Basculez instantanément entre une **CLI ultra-rapide** pour les experts et une **GUI moderne (Tkinter)** pour un contrôle visuel total.
*   **📂 Export Intelligent** : Respect automatique des `.gitignore`, exclusion de dossiers lourds (node_modules, venv) et gestion des inclusions personnalisées.
*   **🌍 Multi-Plateforme** : Fonctionne nativement sur Linux, macOS et Windows avec installation automatique dans le PATH.
*   **📊 Analyse de Structure** : Générez des arbres de projet clairs pour documenter votre architecture en un clic.

---

## 🚀 Installation Express

### 1. Cloner et Lancer
```bash
git clone https://github.com/Bellox1/ProjectExporerPro.git
cd ProjectExporerPro
python3 blx.py --setup
```

### 2. Configuration automatique
L'assistant vous proposera deux modes :
*   **Option 1 (Lite)** : Usage Terminal uniquement (léger).
*   **Option 2 (Full)** : Interface graphique complète avec support des icônes et prévisualisation.

---

## 📖 Guide d'Utilisation

Une fois installé, la commande globale `blx` est disponible partout dans votre terminal.

### 🔌 Commandes Terminal (CLI)
*   `blx p .` : Exporte le dossier actuel vers votre dossier de sortie par défaut.
*   `blx p -n "MonProjet" -y` : Exporte avec un nom spécifique et ouvre le résultat.
*   `blx p ls` : Affiche l'historique de vos derniers exports.
*   `blx unpack <fichier.zip>` : Désassemble un projet exporté pour analyse.

---

## 🛠️ Options Avancées

| Option | Description |
| :--- | :--- |
| `-cl` | **Compression de tokens** : Fusionne les lignes pour économiser du contexte LLM. |
| `-e "pattern"` | **Exclusions** : Exclut des fichiers ou dossiers spécifiques. |
| `-i "pattern"` | **Inclusions** : Ignore les règles d'exclusion pour certains fichiers vitaux. |
| `-y` | **Auto-Open** : Ouvre le dossier de sortie immédiatement après le traitement. |

---

## 📦 Stack Technique

*   **Langage** : Python 3.10+
*   **Interface** : Tkinter avec thèmes personnalisés.
*   **Dépendances** : `psutil`, `Pillow`, `humanize`.
*   **Statut** : Open Source / Beta Development.

---

## 📄 Licence & Crédits
Ce projet est sous licence MIT. Développé par **BELLOX**.
