# Project Explorer Pro (blx) 🚀

Outil professionnel d'export et d'analyse de structure de projet pour l'IA et le développement.

## 📦 Installation rapide

1. Clonez le dépôt :
   ```bash
   git clone <url-du-repo>
   cd ProjectExplorer
   ```

2. Lancez l'assistant d'installation :
   ```bash
   python3 blx.py --setup
   ```
   *Note : Choisissez l'option 1 pour un usage uniquement Terminal (léger) ou 2 pour l'interface graphique complète.*

## 🚀 Utilisation

Une fois installé, vous pouvez utiliser la commande globale :

- **Exporter un projet** : `blx p .` (exporte le dossier courant)
- **Voir l'historique** : `blx p ls`
- **Interface graphique** : `blx p --gui`
- **Désinstaller** : `blx uninstall`

## 🛠️ Options CLI
- `-n "Nom"` : Spécifier un nom de projet
- `-e "pattern1,pattern2"` : Exclure des fichiers/dossiers
- `-i "pattern"` : Inclure (exception aux exclusions)
- `-cl` : Fusionner les lignes (compression de tokens pour l'IA)
- `-y` : Ouvrir le dossier de sortie après l'export
