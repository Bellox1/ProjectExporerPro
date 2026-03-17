#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import platform
import subprocess
import zipfile
import json
import threading
import queue
import fnmatch
import shutil
import re
from datetime import datetime

def show_banner():
    """Affiche la bannière ASCII BELLOX en Bleu"""
    import sys
    if not sys.stdout.isatty():
        return
    BLUE = "\033[94m"
    RESET = "\033[0m"
    # Utilisation d'une chaîne brute (raw string) pour éviter les problèmes d'échappement
    banner = rf"""{BLUE}
  ____  _____ _     _     ___ __  __ 
 | __ )| ____| |   | |   / _ \ \/ / 
 |  _ \|  _| | |   | |  | | | |\  /  
 | |_) | |___| |___| |__| |_| |/  \  
 |____/|_____|_____|_____\___//_/\_\ 
                                     {RESET}"""
    print(banner)
    print("="*40)
    print(f"{'PROJECT EXPLORER PRO':^40}")
    print("="*40)

def check_and_install_dependencies(mode="full"):
    """Vérifie et installe les dépendances selon le mode choisi (core/full)"""
    import os, subprocess
    if mode == "none": return
    # ... rest of the logic ...
    core_deps = [("psutil", "psutil"), ("humanize", "humanize")]
    gui_deps = [("PIL", "Pillow"), ("tktooltip", "tkinter-tooltip")]
    dependencies = core_deps + (gui_deps if mode == "full" else [])
    
    missing = []
    for module_name, package_name in dependencies:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(package_name)
    
    if missing:
        if os.environ.get("INSTALL_ATTEMPTED") == "true":
            print(f"⚠️  Certaines dépendances ({', '.join(missing)}) manquent.")
            return

        print(f"📦 Installation des dépendances ({mode}): {', '.join(missing)}...")
        try:
            os.environ["INSTALL_ATTEMPTED"] = "true"
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user"] + missing)
            print("✅ Installation terminée. Redémarrage...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
        except Exception as e:
            print(f"❌ Erreur installation: {e}")

# Les imports seront fait à la demande dans les classes

class ProfessionalApp:
    def __init__(self):
        # Imports retardés pour ne pas bloquer le CLI
        try:
            global tk, ttk, filedialog, messagebox, Image, ImageTk, humanize, psutil
            import tkinter as tk
            from tkinter import ttk, filedialog, messagebox
            from PIL import Image, ImageTk
            import humanize
            import psutil
        except ImportError:
            print("❌ Erreur: Bibliothèques graphiques manquantes.")
            print("Lancez 'blx new' pour installer les dépendances nécessaires.")
            sys.exit(1)

        # Création de la fenêtre principale
        self.root = tk.Tk()
        self.root.title("Project Explorer Pro")
        self.root.geometry("1300x750")
        
        # Configuration des couleurs professionnelles
        self.colors = {
            'bg_primary': '#f5f5f5', 'bg_secondary': '#ffffff', 'bg_tertiary': '#e0e0e0',
            'bg_dark': '#2d2d2d', 'accent': '#0066cc', 'accent_light': '#4d94ff',
            'success': '#28a745', 'warning': '#ffc107', 'error': '#dc3545',
            'text_primary': '#212529', 'text_secondary': '#6c757d', 'text_light': '#ffffff'
        }
        
        self.root.configure(bg=self.colors['bg_primary'])
        self.os_type = platform.system()
        self.desktop_path = self.get_desktop_path()
        self.app_folder = os.path.join(os.path.expanduser("~"), "ProjectExplorer")
        os.makedirs(self.app_folder, exist_ok=True)
        self.main_script = os.path.abspath(__file__)
        self.script_dir = os.path.dirname(self.main_script)
        self.config_file = os.path.join(self.app_folder, "config.json")
        self.projects_db = os.path.join(self.app_folder, "projects.json")
        self.gitignore_overrides = {}
        self.is_processing = False
        self.cancel_export = False
        self.log_queue = queue.Queue()
        
        # Initialisation logique
        self.check_first_run()
        self.setup_global_command()
        self.load_config()
        self.load_projects()
        self.setup_fonts()
        self.setup_ui()
        self.process_log_queue()
    
    def check_first_run(self):
        """Vérifie si c'est la première exécution et installe sur le bureau"""
        first_run_file = os.path.join(self.app_folder, ".first_run_done")
        
        if not os.path.exists(first_run_file):
            # C'est la première exécution
            self.root.after(100, self.first_run_setup)
    
    def first_run_setup(self):
        """Configuration de la première exécution"""
        # Message de bienvenue
        welcome = """Bienvenue dans Project Explorer Pro ! 🚀

L'application va maintenant :
1. Créer une icône et un lanceur sur votre bureau
2. Configurer les dossiers nécessaires

Cliquez sur OK pour continuer."""
        
        messagebox.showinfo("Première exécution", welcome)
        
        # Créer l'icône
        self.create_icon()
        
        # Créer le raccourci bureau
        shortcut_path = self.create_desktop_shortcut()
        
        if shortcut_path:
            # Marquer la première exécution comme terminée
            with open(os.path.join(self.app_folder, ".first_run_done"), 'w') as f:
                f.write(datetime.now().isoformat())
            
            msg = f"Project Explorer Pro est prêt !\n\n" \
                  f"Un raccourci a été créé sur votre bureau :\n" \
                  f"{shortcut_path}\n\n"
            
            if self.os_type == "Linux":
                msg += "💡 NOTE IMPORTANTE (Linux) :\n" \
                       "Si l'icône ne s'affiche pas, faites clic-droit sur le fichier sur votre bureau\n" \
                       "et sélectionnez 'Autoriser le lancement' (Allow Launching).\n\n"
            
            msg += f"Vous pouvez aussi le lancer depuis n'importe quel terminal avec :\n" \
                   f"bellox pe"
            
            messagebox.showinfo("Configuration terminée", msg)
        else:
            messagebox.showerror("Erreur", 
                                "Impossible de créer le raccourci.\n"
                                "Vous pouvez toujours lancer l'application avec :\n"
                                f"python3 {self.main_script}")
    
    def create_icon(self):
        """Vérifie ou crée une icône pour l'application"""
        icon_path_png = os.path.join(self.script_dir, "icon.png")
        icon_path_xpm = os.path.join(self.script_dir, "icon.xpm")
        
        # Si le PNG existe déjà (généré par l'IA), on l'utilise
        if os.path.exists(icon_path_png):
            return icon_path_png
            
        # Sinon on crée le XPM basique de secours
        try:
            with open(icon_path_xpm, 'w') as f:
                f.write("""/* XPM */
static char * folder_xpm[] = {
"32 32 2 1",
" 	c None",
".	c #0066cc",
"                                ",
"                                ",
"        .............           ",
"       .             .          ",
"      .               .         ",
"     .                 .        ",
"    .                   .       ",
"   .                     .      ",
"  .                       .     ",
" ............................   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" .                          .   ",
" ............................   ",
"                                ",
"                                "};
""")
            return icon_path_xpm
        except Exception as e:
            print(f"❌ Erreur création icône: {e}")
            return None
    
    def setup_global_command(self):
        """Configure la commande globale 'blx p'"""
        try:
            home = os.path.expanduser("~")
            bin_dir = os.path.join(home, ".local", "bin")
            os.makedirs(bin_dir, exist_ok=True)
            
            blx_script = os.path.join(bin_dir, "blx")
            
            # Script qui gère les arguments 'p' et 'projet'
            if self.os_type != "Windows":
                content = f"""#!/bin/bash
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    "{sys.executable}" "{self.main_script}" --help
    exit 0
fi

if [ "$1" == "p" ] || [ "$1" == "projet" ]; then
    "{sys.executable}" "{self.main_script}" "${{@:2}}"
elif [ "$1" == "unpack" ]; then
    "{sys.executable}" "{self.main_script}" unpack "${{@:2}}"
elif [ "$1" == "new" ]; then
    "{sys.executable}" "{self.main_script}" --setup
elif [ "$1" == "uninstall" ]; then
    "{sys.executable}" "{self.main_script}" --uninstall
else
    echo "=== PROJECT EXPLORER PRO ==="
    echo "Usage: blx p [options]  (Mode Export)"
    echo "       blx p ls         (Historique)"
    echo "       blx unpack       (Désassembler un projet)"
    echo "       blx new          (Configuration/Installation)"
    echo "       blx uninstall    (Supprimer l'application)"
    echo "       blx --help       (Aide détaillée)"
fi
"""
                with open(blx_script, 'w') as f:
                    f.write(content)
                os.chmod(blx_script, 0o755)
            else:
                # Windows version
                blx_bat = os.path.join(bin_dir, "blx.bat")
                content = f"""@echo off
if "%~1"=="p" goto run
if "%~1"=="projet" goto run
echo Usage: blx p [options]
echo        blx p ls
goto end
:run
shift
"{sys.executable}" "{self.main_script}" %*
:end
"""
                with open(blx_bat, 'w') as f:
                    f.write(content)
                blx_script = blx_bat
            
            print(f"✅ Commande globale configurée: {blx_script}")
            
            # Vérifier si bin_dir est dans le PATH
            path_env = os.environ.get("PATH", "")
            if bin_dir.lower() not in path_env.lower():
                self.add_to_shell_path(bin_dir)
                
            print(f"✅ Commande globale configurée: {blx_script}")
            return True
        except Exception as e:
            print(f"❌ Erreur setup commande globale: {e}")
            return False

    def add_to_shell_path(self, path_to_add):
        """Ajoute un dossier au PATH"""
        if self.os_type == "Windows":
            try:
                # Sur Windows, on utilise setx pour ajouter au PATH utilisateur
                import subprocess
                # Récupérer le PATH actuel de l'utilisateur
                result = subprocess.run(['reg', 'query', 'HKCU\\Environment', '/v', 'Path'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.splitlines()
                    for line in lines:
                        if 'Path' in line:
                            current_path = line.split('REG_SZ')[-1].strip()
                            if path_to_add not in current_path:
                                new_path = f"{current_path};{path_to_add}"
                                subprocess.run(['setx', 'Path', new_path])
                                return True
                else:
                    # Si la clé n'existe pas, on la crée
                    subprocess.run(['setx', 'Path', path_to_add])
                    return True
            except:
                pass
            return False

        home = os.path.expanduser("~")
        shells = [".bashrc", ".zshrc", ".profile"]
        added = False
        
        export_line = f'\n# Project Explorer Pro\nexport PATH="$PATH:{path_to_add}"\n'
        
        for shell_file in shells:
            shell_path = os.path.join(home, shell_file)
            if os.path.exists(shell_path):
                try:
                    with open(shell_path, 'r') as f:
                        content = f.read()
                    
                    if path_to_add not in content:
                        with open(shell_path, 'a') as f:
                            f.write(export_line)
                        added = True
                except:
                    pass
        
        return added

    def create_desktop_shortcut(self):
        """Crée un raccourci fonctionnel sur le bureau"""
        import shutil, subprocess
        try:
            desktop = self.desktop_path
            if not os.path.exists(desktop):
                print(f"❌ Bureau non trouvé: {desktop}")
                return None
            
            icon_path = os.path.join(self.script_dir, "icon.xpm")
            if not os.path.exists(icon_path):
                icon_path = "system-file-manager"
            
            if self.os_type == "Windows":
                # Windows - Créer un fichier .bat
                bat_path = os.path.join(desktop, "ProjectExplorer.bat")
                with open(bat_path, 'w') as f:
                    f.write(f'''@echo off
echo Lancement de Project Explorer Pro...
cd /d "{self.script_dir}"
"{sys.executable}" "{self.main_script}"
if errorlevel 1 (
    echo.
    echo Erreur lors du lancement
    pause
)
''')
                print(f"✅ Raccourci créé: {bat_path}")
                return bat_path
                
            elif self.os_type == "Darwin":  # macOS
                # macOS - Créer un fichier .command
                command_path = os.path.join(desktop, "ProjectExplorer.command")
                with open(command_path, 'w') as f:
                    f.write(f'''#!/bin/bash
cd "{self.script_dir}"
"{sys.executable}" "{self.main_script}"
read -p "Appuyez sur Entrée pour quitter..."
''')
                os.chmod(command_path, 0o755)
                print(f"✅ Raccourci créé: {command_path}")
                return command_path
                
            else:  # Linux
                # Déterminer la meilleure icône
                icon_path_png = os.path.join(self.script_dir, "icon.png")
                icon_path_xpm = os.path.join(self.script_dir, "icon.xpm")
                
                # Copier l'icône dans le dossier standard pour Linux
                try:
                    local_icons = os.path.expanduser("~/.local/share/icons")
                    os.makedirs(local_icons, exist_ok=True)
                    if os.path.exists(icon_path_png):
                        shutil.copy2(icon_path_png, os.path.join(local_icons, "project-explorer.png"))
                        final_icon = "project-explorer"
                    else:
                        final_icon = icon_path_xpm
                except:
                    final_icon = icon_path_png if os.path.exists(icon_path_png) else icon_path_xpm
                
                # Créer le fichier .desktop sur le bureau
                desktop_file = os.path.join(desktop, "project-explorer.desktop")
                content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Project Explorer Pro
Comment=Outil d'export et d'analyse de projets
Exec="{sys.executable}" "{self.main_script}"
Icon={final_icon}
Terminal=false
X-GNOME-UsesTerminal=false
Categories=Development;Utility;
StartupNotify=true
"""
                with open(desktop_file, 'w') as f:
                    f.write(content)
                os.chmod(desktop_file, 0o755)
                
                # Essayer de marquer le fichier comme approuvé (GNOME/Ubuntu)
                try:
                    subprocess.run(["gio", "set", desktop_file, "metadata::trusted", "true"], check=False)
                except:
                    pass
                
                # Créer aussi dans .local/share/applications pour le menu système
                local_apps = os.path.expanduser("~/.local/share/applications")
                os.makedirs(local_apps, exist_ok=True)
                local_desktop = os.path.join(local_apps, "project-explorer.desktop")
                with open(local_desktop, 'w') as f:
                    f.write(content)
                os.chmod(local_desktop, 0o755)
                
                return desktop_file
                
        except Exception as e:
            print(f"❌ Erreur création raccourci: {e}")
            return None
    
    def get_desktop_path(self):
        """Récupère le chemin du bureau le plus probable"""
        if self.os_type == "Windows":
            return os.path.join(os.path.expanduser("~"), "Desktop")
            
        home = os.path.expanduser("~")
        
        # 1. Tenter via xdg-user-dir (standard Linux)
        try:
            import subprocess
            res = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != home:
                return res.stdout.strip()
        except:
            pass

        # 2. Chemins communs
        paths = [
            os.path.join(home, "Bureau"),
            os.path.join(home, "Desktop"),
            os.path.join(home, "Desktop.localized"),
            home  # Dernier recours
        ]
        
        for p in paths:
            if os.path.exists(p) and os.path.isdir(p):
                # Si on est dans HOME, on vérifie quand même si Bureau/Desktop existe
                if p == home:
                    continue
                return p
                
        return home
    
    def setup_fonts(self):
        """Configuration des polices"""
        if self.os_type == "Windows":
            self.fonts = {
                'heading': ('Segoe UI', 20, 'bold'),
                'subheading': ('Segoe UI', 14, 'bold'),
                'title': ('Segoe UI', 12, 'bold'),
                'normal': ('Segoe UI', 10),
                'small': ('Segoe UI', 9),
                'mono': ('Consolas', 10)
            }
        else:
            # Sur Linux, utiliser des noms génériques plus sûrs
            import tkinter.font as tkfont
            available = tkfont.families()
            
            # Déterminer la meilleure police sans-serif disponible
            sans_font = "Sans"
            for f in ["DejaVu Sans", "Ubuntu", "Liberation Sans", "Noto Sans", "Sans"]:
                if f in available:
                    sans_font = f
                    break
            
            mono_font = "Monospace"
            for f in ["DejaVu Sans Mono", "Ubuntu Mono", "Liberation Mono", "Monospace"]:
                if f in available:
                    mono_font = f
                    break

            self.fonts = {
                'heading': (sans_font, 20, 'bold'),
                'subheading': (sans_font, 14, 'bold'),
                'title': (sans_font, 12, 'bold'),
                'normal': (sans_font, 10),
                'small': (sans_font, 9),
                'mono': (mono_font, 10)
            }
    
    def load_config(self):
        """Charge la configuration"""
        self.config = {
            'exclude_patterns': ['__pycache__', '*.pyc', '.git', '.idea', '.vscode', '.DS_Store', 'node_modules'],
            'max_size_mb': 500,
            'unlimited_size': False,
            'use_gitignore': True,
            'gitignore_overrides': {},
            'merge_lines': True,
            'text_extensions': ['.txt', '.py', '.js', '.html', '.css', '.json', '.xml', 
                              '.md', '.yaml', '.yml', '.c', '.cpp', '.h', '.java', 
                              '.php', '.rb', '.go', '.rs', '.sh', '.bat', '.ps1', 
                              '.sql', '.csv', '.ini', '.cfg', '.conf', '.log',
                              '.jsx', '.ts', '.tsx', '.vue', '.scss', '.less'],
            'last_path': '',
            'recent_projects': []
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    saved = json.load(f)
                    self.config.update(saved)
                    self.gitignore_overrides = self.config.get('gitignore_overrides', {})
            except Exception as e:
                print(f"Erreur chargement config: {e}")
    
    def load_projects(self):
        """Charge la base de données des projets exportés"""
        self.projects = []
        if os.path.exists(self.projects_db):
            try:
                with open(self.projects_db, 'r') as f:
                    self.projects = json.load(f)
            except:
                self.projects = []
    
    def save_projects(self):
        """Sauvegarde la base de données des projets"""
        try:
            with open(self.projects_db, 'w') as f:
                json.dump(self.projects, f, indent=2)
        except:
            pass
    
    def save_config(self):
        """Sauvegarde la configuration"""
        self.config['gitignore_overrides'] = self.gitignore_overrides
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except:
            pass
    
    def setup_ui(self):
        """Configuration de l'interface principale"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Ouvrir projet", command=self.browse_folder)
        file_menu.add_command(label="Analyser", command=self.analyze_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.root.quit)
        
        # Menu Export
        export_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Export", menu=export_menu)
        export_menu.add_command(label="Exporter", command=self.start_export)
        export_menu.add_command(label="Ouvrir dossier exports", 
                               command=lambda: self.open_folder(self.app_folder))
        
        # Menu Aide
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Aide", menu=help_menu)
        help_menu.add_command(label="À propos", command=self.show_about)
        
        header = tk.Frame(self.root, bg=self.colors['bg_dark'], height=70)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        tk.Label(header, text="📁", font=('Arial', 30), 
                bg=self.colors['bg_dark'], fg='white').pack(side=tk.LEFT, padx=20)
        
        tk.Label(header, text="Project Explorer Pro", 
                font=self.fonts['heading'],
                bg=self.colors['bg_dark'], fg='white').pack(side=tk.LEFT)
        
        tk.Label(header, text="v3.0 - EVOLVED", font=self.fonts['small'],
                bg=self.colors['bg_dark'], fg='#4d94ff').pack(side=tk.RIGHT, padx=20)
        
        main_panel = tk.Frame(self.root, bg=self.colors['bg_primary'])
        main_panel.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.notebook = ttk.Notebook(main_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Création des onglets
        self.setup_main_tab()
        self.setup_ia_tab()
        self.setup_gitignore_tab()
        self.setup_projects_tab()
        self.setup_config_tab()
        
        status_frame = tk.Frame(self.root, bg=self.colors['bg_tertiary'], height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="✅ Prêt", 
                                     bg=self.colors['bg_tertiary'], 
                                     anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        self.progress = ttk.Progressbar(status_frame, mode='determinate', length=200)
        self.progress.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def setup_main_tab(self):
        """Onglet principal"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📦 Export principal")
        
        # Frame gauche - Infos projet
        left_frame = tk.Frame(tab, bg=self.colors['bg_secondary'], width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="PROJET ACTUEL", font=self.fonts['title'],
                bg=self.colors['bg_secondary'], fg=self.colors['accent']).pack(anchor=tk.W, pady=10, padx=10)
        
        tk.Label(left_frame, text="Chemin:", bg=self.colors['bg_secondary']).pack(anchor=tk.W, padx=10)
        
        self.path_var = tk.StringVar()
        tk.Entry(left_frame, textvariable=self.path_var).pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(left_frame, text="📂 Parcourir", command=self.browse_folder,
                 bg=self.colors['accent'], fg='white', padx=10).pack(padx=10, pady=5)
        
        tk.Button(left_frame, text="🔍 Analyser", command=self.analyze_folder,
                 bg=self.colors['bg_tertiary'], padx=10).pack(padx=10, pady=5)
        
        # Informations
        info_frame = tk.Frame(left_frame, bg=self.colors['bg_secondary'])
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.info_labels = {}
        info_items = [
            ('📊 Taille totale', 'Taille'),
            ('📄 Fichiers', 'Fichiers'),
            ('📁 Dossiers', 'Dossiers')
        ]
        
        for label, key in info_items:
            frame = tk.Frame(info_frame, bg=self.colors['bg_secondary'])
            frame.pack(fill=tk.X, pady=2)
            tk.Label(frame, text=label, bg=self.colors['bg_secondary'],
                    width=15, anchor=tk.W).pack(side=tk.LEFT)
            self.info_labels[key] = tk.Label(frame, text="-", bg=self.colors['bg_secondary'],
                                           anchor=tk.W)
            self.info_labels[key].pack(side=tk.LEFT)
        
        # Projets récents
        tk.Label(left_frame, text="PROJETS RÉCENTS", font=self.fonts['title'],
                bg=self.colors['bg_secondary'], fg=self.colors['accent']).pack(anchor=tk.W, pady=(20,10), padx=10)
        
        self.recent_listbox = tk.Listbox(left_frame, height=8,
                                        bg='white', selectbackground=self.colors['accent_light'])
        self.recent_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.recent_listbox.bind('<Double-Button-1>', self.load_recent_project)
        
        self.update_recent_projects()
        
        # Frame droit - Options
        right_frame = tk.Frame(tab, bg=self.colors['bg_primary'])
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Options d'export
        options_frame = tk.LabelFrame(right_frame, text="Options d'export", 
                                      font=self.fonts['title'], padx=15, pady=15)
        options_frame.pack(fill=tk.X, pady=5)
        
        # Nom du projet
        tk.Label(options_frame, text="Nom du projet:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.project_name_var = tk.StringVar()
        tk.Entry(options_frame, textvariable=self.project_name_var, width=40).grid(row=0, column=1, padx=10, pady=5)
        
        # Limite de taille
        tk.Label(options_frame, text="Limite de taille:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        size_frame = tk.Frame(options_frame)
        size_frame.grid(row=1, column=1, sticky=tk.W, padx=10, pady=5)
        
        self.unlimited_var = tk.BooleanVar(value=self.config.get('unlimited_size', False))
        tk.Radiobutton(size_frame, text="Illimité", variable=self.unlimited_var, value=True,
                      command=self.toggle_size_limit).pack(side=tk.LEFT, padx=(0,10))
        
        tk.Radiobutton(size_frame, text="Limitée à", variable=self.unlimited_var, value=False,
                      command=self.toggle_size_limit).pack(side=tk.LEFT)
        
        self.max_size_var = tk.StringVar(value=str(self.config['max_size_mb']))
        self.max_size_spinbox = tk.Spinbox(size_frame, from_=10, to=10000,
                                          textvariable=self.max_size_var, width=8)
        self.max_size_spinbox.pack(side=tk.LEFT, padx=5)
        tk.Label(size_frame, text="Mo").pack(side=tk.LEFT)
        
        # Options de format
        tk.Label(options_frame, text="Format:").grid(row=2, column=0, sticky=tk.W, pady=5)
        
        format_frame = tk.Frame(options_frame)
        format_frame.grid(row=2, column=1, sticky=tk.W, padx=10, pady=5)
        
        self.merge_lines_var = tk.BooleanVar(value=self.config.get('merge_lines', True))
        tk.Checkbutton(format_frame, text="Fusionner sur une ligne", 
                      variable=self.merge_lines_var).pack(anchor=tk.W)
        
        self.compress_var = tk.BooleanVar(value=True)
        tk.Checkbutton(format_frame, text="Créer une archive ZIP", 
                      variable=self.compress_var).pack(anchor=tk.W)
        
        # Utilisation .gitignore
        self.use_gitignore_var = tk.BooleanVar(value=self.config.get('use_gitignore', True))
        tk.Checkbutton(options_frame, text="Utiliser .gitignore", 
                      variable=self.use_gitignore_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        # Boutons d'action
        btn_frame = tk.Frame(right_frame)
        btn_frame.pack(pady=20)
        
        self.export_btn = tk.Button(btn_frame, text="🚀 LANCER L'EXPORT", 
                                   command=self.start_export,
                                   bg=self.colors['success'], fg='white',
                                   font=self.fonts['title'], padx=30, pady=10)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = tk.Button(btn_frame, text="⏹️ ANNULER", 
                                   command=self.cancel_current_export,
                                   bg=self.colors['error'], fg='white',
                                   font=self.fonts['title'], padx=30, pady=10,
                                   state='disabled')
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        # Journal en bas
        log_frame = tk.LabelFrame(right_frame, text="📋 Journal d'activité", 
                                   font=self.fonts['title'])
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        log_text_frame = tk.Frame(log_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        scrollbar = tk.Scrollbar(log_text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_text_frame, height=8,
                                yscrollcommand=scrollbar.set,
                                bg='white', font=self.fonts['small'],
                                wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=self.log_text.yview)
        
        # Tags pour les couleurs
        self.log_text.tag_config('info', foreground='black')
        self.log_text.tag_config('success', foreground=self.colors['success'])
        self.log_text.tag_config('warning', foreground=self.colors['warning'])
        self.log_text.tag_config('error', foreground=self.colors['error'])
        
        # Boutons journal
        log_btn_frame = tk.Frame(log_frame)
        log_btn_frame.pack(fill=tk.X, pady=5)
        
        tk.Button(log_btn_frame, text="🧹 Effacer", command=self.clear_log,
                 bg=self.colors['bg_tertiary']).pack(side=tk.LEFT, padx=5)
        
        tk.Button(log_btn_frame, text="💾 Sauvegarder", command=self.save_log,
                 bg=self.colors['bg_tertiary']).pack(side=tk.LEFT)
    
    def setup_gitignore_tab(self):
        """Onglet gestion .gitignore"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🔒 Gestion .gitignore")
        
        main_frame = tk.Frame(tab, bg=self.colors['bg_secondary'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        tk.Label(main_frame, text="Gestion des exceptions .gitignore", 
                font=self.fonts['subheading'],
                bg=self.colors['bg_secondary']).pack(anchor=tk.W, pady=10)
        
        tk.Label(main_frame, 
                text="Sélectionnez les fichiers/dossiers à inclure malgré le .gitignore",
                bg=self.colors['bg_secondary']).pack(anchor=tk.W, pady=(0,20))
        
        # Panneau des règles
        rules_frame = tk.Frame(main_frame)
        rules_frame.pack(fill=tk.BOTH, expand=True)
        
        # Règles .gitignore
        left_frame = tk.LabelFrame(rules_frame, text="Règles .gitignore actuelles")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,5))
        
        left_scroll = tk.Scrollbar(left_frame)
        left_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.gitignore_listbox = tk.Listbox(left_frame,
                                           yscrollcommand=left_scroll.set,
                                           bg='white',
                                           selectbackground=self.colors['accent_light'],
                                           font=self.fonts['mono'])
        self.gitignore_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        left_scroll.config(command=self.gitignore_listbox.yview)
        
        # Boutons de transfert
        center_frame = tk.Frame(rules_frame)
        center_frame.pack(side=tk.LEFT, padx=10)
        
        tk.Button(center_frame, text="→", command=self.add_override,
                 bg=self.colors['accent'], fg='white', width=3).pack(pady=5)
        
        tk.Button(center_frame, text="←", command=self.remove_override,
                 bg=self.colors['error'], fg='white', width=3).pack(pady=5)
        
        # Exceptions
        right_frame = tk.LabelFrame(rules_frame, text="Exceptions (fichiers inclus)")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5,0))
        
        right_scroll = tk.Scrollbar(right_frame)
        right_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.override_listbox = tk.Listbox(right_frame,
                                          yscrollcommand=right_scroll.set,
                                          bg='white',
                                          selectbackground=self.colors['accent_light'],
                                          font=self.fonts['mono'])
        self.override_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        right_scroll.config(command=self.override_listbox.yview)
        
        # Bouton sauvegarde
        tk.Button(main_frame, text="💾 Sauvegarder les exceptions", 
                 command=self.save_gitignore_overrides,
                 bg=self.colors['success'], fg='white',
                 font=self.fonts['title'], padx=30, pady=5).pack(pady=10)
    
    def setup_projects_tab(self):
        """Onglet historique des projets exportés"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📚 Projets exportés")
        
        main_frame = tk.Frame(tab, bg=self.colors['bg_secondary'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Statistiques
        stats_frame = tk.Frame(main_frame, bg=self.colors['bg_tertiary'])
        stats_frame.pack(fill=tk.X, pady=(0,10))
        
        self.stats_labels = {}
        stats = [
            ('📊 Total projets', 'total'),
            ('📦 Taille totale', 'total_size'),
            ('📄 Fichiers', 'total_files')
        ]
        
        for i, (label, key) in enumerate(stats):
            frame = tk.Frame(stats_frame, bg=self.colors['bg_tertiary'])
            frame.grid(row=0, column=i, padx=20, pady=10)
            
            tk.Label(frame, text=label, bg=self.colors['bg_tertiary']).pack()
            self.stats_labels[key] = tk.Label(frame, text="-", font=self.fonts['title'],
                                            bg=self.colors['bg_tertiary'], fg=self.colors['accent'])
            self.stats_labels[key].pack()
        
        # Liste des projets
        columns = ('Date', 'Projet', 'Source', 'Taille', 'Fichiers', 'Fichier exporté')
        self.projects_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.projects_tree.heading(col, text=col)
            if col == 'Fichier exporté':
                self.projects_tree.column(col, width=350)
            elif col == 'Source':
                self.projects_tree.column(col, width=150)
            elif col == 'Projet':
                self.projects_tree.column(col, width=130)
            else:
                self.projects_tree.column(col, width=80)
        
        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=scrollbar.set)
        
        self.projects_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Boutons
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(btn_frame, text="📂 Ouvrir", command=self.open_selected_project,
                 bg=self.colors['accent'], fg='white', padx=20).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🗑️ Supprimer", command=self.delete_selected_project,
                 bg=self.colors['error'], fg='white', padx=20).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="🔄 Actualiser", command=self.refresh_projects_list,
                 bg=self.colors['bg_tertiary'], padx=20).pack(side=tk.LEFT, padx=5)
        
        self.refresh_projects_list()
    
    def setup_config_tab(self):
        """Onglet configuration"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="⚙️ Configuration")
        
        main_frame = tk.Frame(tab, bg=self.colors['bg_secondary'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Extensions texte
        ext_frame = tk.LabelFrame(main_frame, text="Extensions de fichiers texte", padx=10, pady=10)
        ext_frame.pack(fill=tk.X, pady=5)
        
        tk.Label(ext_frame, text="Extensions (séparées par des virgules):").pack(anchor=tk.W)
        
        self.extensions_var = tk.StringVar(value=','.join(self.config['text_extensions']))
        tk.Entry(ext_frame, textvariable=self.extensions_var, width=60).pack(fill=tk.X, pady=5)
        
        tk.Label(ext_frame, 
                text="Exemple: .txt, .py, .js, .html, .css, .json, .xml, .md",
                font=self.fonts['small'], fg='gray').pack(anchor=tk.W)
        
        # Patterns d'exclusion
        excl_frame = tk.LabelFrame(main_frame, text="Patterns d'exclusion", padx=10, pady=10)
        excl_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        tk.Label(excl_frame, text="Un motif par ligne:").pack(anchor=tk.W)
        
        text_frame = tk.Frame(excl_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.exclude_text = tk.Text(text_frame, height=10,
                                    yscrollcommand=scrollbar.set,
                                    font=self.fonts['mono'])
        self.exclude_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.exclude_text.yview)
        
        self.exclude_text.insert('1.0', '\n'.join(self.config['exclude_patterns']))
        
        # Bouton sauvegarde
        tk.Button(main_frame, text="💾 Sauvegarder la configuration", 
                 command=self.save_config_from_ui,
                 bg=self.colors['success'], fg='white',
                 font=self.fonts['title'], padx=30, pady=5).pack(pady=10)
    
    def toggle_size_limit(self):
        """Active/désactive la limite de taille"""
        if self.unlimited_var.get():
            self.max_size_spinbox.config(state='disabled')
        else:
            self.max_size_spinbox.config(state='normal')
    
    def update_recent_projects(self):
        """Met à jour la liste des projets récents"""
        self.recent_listbox.delete(0, tk.END)
        for project in reversed(self.config.get('recent_projects', [])[-10:]):
            self.recent_listbox.insert(0, os.path.basename(project))
    
    def load_recent_project(self, event):
        """Charge un projet récent"""
        selection = self.recent_listbox.curselection()
        if selection:
            idx = selection[0]
            projects = self.config.get('recent_projects', [])
            if idx < len(projects):
                path = projects[-(idx+1)]
                self.path_var.set(path)
                self.project_name_var.set(os.path.basename(path))
                self.load_gitignore_rules(path)
                self.analyze_folder()
    
    def load_gitignore_rules(self, folder_path):
        """Charge les règles .gitignore"""
        self.gitignore_listbox.delete(0, tk.END)
        self.override_listbox.delete(0, tk.END)
        
        if not folder_path or not self.use_gitignore_var.get():
            return
        
        gitignore_path = os.path.join(folder_path, '.gitignore')
        if os.path.exists(gitignore_path):
            try:
                with open(gitignore_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.gitignore_listbox.insert(tk.END, line)
                
                if self.gitignore_listbox.size() > 0:
                    self.log(f"📋 {self.gitignore_listbox.size()} règles .gitignore chargées", "info")
                else:
                    self.log("📋 Fichier .gitignore vide", "info")
                    
            except Exception as e:
                self.log(f"❌ Erreur lecture .gitignore: {e}", "error")
        else:
            self.log("ℹ️ Aucun fichier .gitignore trouvé", "info")
        
        overrides = self.gitignore_overrides.get(folder_path, [])
        for override in overrides:
            self.override_listbox.insert(tk.END, override)
    
    def add_override(self):
        """Ajoute une règle aux exceptions"""
        selection = self.gitignore_listbox.curselection()
        if selection:
            rule = self.gitignore_listbox.get(selection[0])
            self.override_listbox.insert(tk.END, rule)
            self.log(f"✅ Exception ajoutée: {rule}", "success")
    
    def remove_override(self):
        """Retire une règle des exceptions"""
        selection = self.override_listbox.curselection()
        if selection:
            rule = self.override_listbox.get(selection[0])
            self.override_listbox.delete(selection[0])
            self.log(f"➖ Exception retirée: {rule}", "info")
    
    def save_gitignore_overrides(self):
        """Sauvegarde les exceptions"""
        folder = self.path_var.get()
        if folder:
            overrides = list(self.override_listbox.get(0, tk.END))
            self.gitignore_overrides[folder] = overrides
            self.save_config()
            self.log(f"✅ {len(overrides)} exceptions .gitignore sauvegardées", "success")
            messagebox.showinfo("Succès", f"{len(overrides)} exceptions sauvegardées")
    
    def browse_folder(self):
        """Sélectionne un dossier"""
        folder = filedialog.askdirectory(title="Sélectionner le dossier du projet")
        if folder:
            self.path_var.set(folder)
            self.project_name_var.set(os.path.basename(folder))
            
            recent = self.config.get('recent_projects', [])
            if folder in recent:
                recent.remove(folder)
            recent.append(folder)
            self.config['recent_projects'] = recent[-10:]
            self.save_config()
            self.update_recent_projects()
            
            self.load_gitignore_rules(folder)
            self.analyze_folder()
    
    def analyze_folder(self):
        """Analyse le dossier"""
        folder = self.path_var.get()
        if not folder or not os.path.exists(folder):
            return
        
        self.status_label.config(text="🔄 Analyse en cours...")
        self.root.update()
        
        try:
            total_size = 0
            file_count = 0
            dir_count = 0
            
            for root, dirs, files in os.walk(folder):
                dir_count += len(dirs)
                file_count += len(files)
                for file in files:
                    path = os.path.join(root, file)
                    if os.path.exists(path):
                        total_size += os.path.getsize(path)
            
            self.info_labels['Taille'].config(text=self.format_size(total_size))
            self.info_labels['Fichiers'].config(text=str(file_count))
            self.info_labels['Dossiers'].config(text=str(dir_count))
            
            self.log(f"📊 Analyse: {file_count} fichiers, {self.format_size(total_size)}", "success")
            self.status_label.config(text="✅ Analyse terminée")
            
        except Exception as e:
            self.log(f"❌ Erreur: {str(e)}", "error")
    
    def format_size(self, size):
        """Formate la taille"""
        for unit in ['o', 'Ko', 'Mo', 'Go']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} To"
    
    def start_export(self):
        """Démarre l'export"""
        if self.is_processing:
            messagebox.showwarning("Attention", "Un export est déjà en cours")
            return
        
        folder = self.path_var.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("Erreur", "Veuillez sélectionner un dossier valide")
            return
        
        self.is_processing = True
        self.cancel_export = False
        self.progress['value'] = 0
        self.export_btn.config(state='disabled')
        self.cancel_btn.config(state='normal')
        self.status_label.config(text="🔄 Export en cours...")
        
        thread = threading.Thread(target=self.export_structure)
        thread.daemon = True
        thread.start()
    
    def cancel_current_export(self):
        """Annule l'export en cours"""
        if self.is_processing:
            self.cancel_export = True
            self.log("⏹️ Annulation demandée...", "warning")
    
    def export_structure(self):
        """Exporte la structure"""
        try:
            folder = self.path_var.get()
            project_name = self.project_name_var.get() or os.path.basename(folder)
            
            overrides = self.gitignore_overrides.get(folder, [])
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            export_folder = os.path.join(self.app_folder, f"{project_name}_{timestamp}")
            os.makedirs(export_folder, exist_ok=True)
            
            txt_file = os.path.join(export_folder, f"{project_name}.txt")
            
            if self.unlimited_var.get():
                max_size = float('inf')
            else:
                max_size = int(self.max_size_var.get()) * 1024 * 1024
            
            current_size = 0
            processed_files = 0
            skipped_files = 0
            total_files = 0
            
            # Compter les fichiers
            for root, dirs, files in os.walk(folder):
                total_files += len(files)
            
            self.root.after(0, lambda: self.log(f"📦 Export de {total_files} fichiers...", "info"))
            
            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(f"PROJECT: {project_name}\n")
                f.write(f"SOURCE: {folder}\n")
                f.write(f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"MERGE_LINES: {'YES' if self.merge_lines_var.get() else 'NO'}\n")
                f.write("="*60 + "\n\n")
                
                for root, dirs, files in os.walk(folder):
                    if self.cancel_export:
                        break
                    
                    for file in files:
                        if self.cancel_export:
                            break
                        
                        file_path = os.path.join(root, file)
                        
                        if not self.should_include(file_path, folder, overrides):
                            skipped_files += 1
                            continue
                        
                        file_size = os.path.getsize(file_path)
                        if current_size + file_size > max_size:
                            self.root.after(0, lambda: self.log("⚠️ Limite de taille atteinte", "warning"))
                            break
                        
                        rel_path = os.path.relpath(file_path, folder)
                        f.write(f"\n[{rel_path}]\n")
                        
                        if self.is_text_file(file_path):
                            try:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as fc:
                                    content = fc.read()
                                    if self.merge_lines_var.get():
                                        content = ' '.join(content.split())
                                    f.write(content)
                            except Exception as e:
                                f.write(f"[ERREUR LECTURE: {str(e)}]")
                        else:
                            f.write("[FICHIER BINAIRE]")
                        
                        f.write("\n")
                        current_size += file_size
                        processed_files += 1
                        
                        if total_files > 0:
                            progress = (processed_files / total_files) * 100
                            self.root.after(0, lambda p=progress: self.progress.config(value=p))
                            self.root.after(0, lambda: self.status_label.config(
                                text=f"🔄 {processed_files}/{total_files} fichiers"))
            
            if self.cancel_export:
                self.root.after(0, self.export_cancelled)
                return
            
            if self.compress_var.get():
                self.create_zip(export_folder, txt_file)
            
            project_info = {
                'name': project_name,
                'source': folder,
                'date': timestamp,
                'path': export_folder,
                'size': current_size,
                'files': processed_files,
                'skipped': skipped_files,
                'zip': self.compress_var.get(),
                'merge_lines': self.merge_lines_var.get()
            }
            self.projects.append(project_info)
            self.save_projects()
            
            self.root.after(0, lambda: self.export_complete(export_folder, processed_files))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"❌ Erreur: {str(e)}", "error"))
        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.export_btn.config(state='normal'))
            self.root.after(0, lambda: self.cancel_btn.config(state='disabled'))
            self.root.after(0, self.refresh_projects_list)
    
    def export_cancelled(self):
        """Export annulé"""
        self.log("⏹️ Export annulé", "warning")
        self.status_label.config(text="⏹️ Annulé")
        self.progress.config(value=0)
    
    def should_include(self, path, base_folder, overrides):
        """Vérifie si un fichier doit être inclus"""
        rel_path = os.path.relpath(path, base_folder)
        
        for override in overrides:
            if fnmatch.fnmatch(rel_path, override) or override in rel_path:
                return True
        
        for pattern in self.config['exclude_patterns']:
            if fnmatch.fnmatch(rel_path, pattern) or pattern in rel_path:
                return False
        
        return True
    
    def is_text_file(self, file_path):
        """Vérifie si c'est un fichier texte"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.config['text_extensions']
    
    def create_zip(self, folder, txt_file):
        """Crée une archive ZIP"""
        try:
            zip_name = txt_file.replace('.txt', '.zip')
            with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(txt_file, os.path.basename(txt_file))
            self.log("📦 Archive ZIP créée", "success")
        except Exception as e:
            self.log(f"❌ Erreur ZIP: {str(e)}", "error")
    
    def export_complete(self, folder, files):
        """Fin de l'export"""
        self.log(f"✅ Export terminé: {files} fichiers", "success")
        self.status_label.config(text="✅ Terminé")
        self.progress.config(value=100)
        
        if messagebox.askyesno("Succès", f"Export terminé!\n{files} fichiers exportés.\nOuvrir le dossier?"):
            self.open_folder(folder)
    
    def open_folder(self, path):
        """Ouvre un dossier"""
        try:
            if self.os_type == "Windows":
                os.startfile(path)
            elif self.os_type == "Darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self.log(f"❌ Erreur ouverture: {str(e)}", "error")
    
    def refresh_projects_list(self):
        """Rafraîchit la liste des projets"""
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)
        
        if not self.projects:
            return
        
        total_size = 0
        total_files = 0
        
        for project in sorted(self.projects, key=lambda x: x['date'], reverse=True)[:50]:
            date = project['date']
            if len(date) >= 15:
                date = f"{date[6:8]}/{date[4:6]}/{date[0:4]} {date[9:11]}:{date[11:13]}"
            
            size_str = self.format_size(project['size'])
        
            # Chemin du fichier .txt exporté
            export_path = project.get('path', '')
            export_name = project.get('name', 'export')
            txt_file = os.path.join(export_path, f"{export_name}.txt") if export_path else 'Inconnu'
            
            self.projects_tree.insert('', tk.END,
                                     values=(date, project['name'],
                                            os.path.basename(project['source']),
                                            size_str, project['files'], txt_file),
                                     tags=(project['path'],))
            
            total_size += project['size']
            total_files += project['files']
        
        self.stats_labels['total'].config(text=str(len(self.projects)))
        self.stats_labels['total_size'].config(text=self.format_size(total_size))
        self.stats_labels['total_files'].config(text=str(total_files))
    
    def open_selected_project(self):
        """Ouvre le projet sélectionné"""
        selection = self.projects_tree.selection()
        if selection:
            path = self.projects_tree.item(selection[0])['tags'][0]
            self.open_folder(path)
    
    def delete_selected_project(self):
        """Supprime le projet sélectionné"""
        selection = self.projects_tree.selection()
        if selection and messagebox.askyesno("Confirmation", "Supprimer cet export définitivement?"):
            path = self.projects_tree.item(selection[0])['tags'][0]
            try:
                shutil.rmtree(path)
                self.projects = [p for p in self.projects if p['path'] != path]
                self.save_projects()
                self.refresh_projects_list()
                self.log("✅ Export supprimé", "success")
            except Exception as e:
                self.log(f"❌ Erreur: {str(e)}", "error")
    
    def save_config_from_ui(self):
        """Sauvegarde la configuration"""
        patterns = self.exclude_text.get('1.0', tk.END).strip().split('\n')
        self.config['exclude_patterns'] = [p.strip() for p in patterns if p.strip()]
        
        exts = self.extensions_var.get().split(',')
        self.config['text_extensions'] = [e.strip() for e in exts if e.strip()]
        
        self.config['merge_lines'] = self.merge_lines_var.get()
        self.config['use_gitignore'] = self.use_gitignore_var.get()
        self.config['max_size_mb'] = int(self.max_size_var.get())
        self.config['unlimited_size'] = self.unlimited_var.get()
        
        self.save_config()
        self.log("✅ Configuration sauvegardée", "success")
        messagebox.showinfo("Succès", "Configuration sauvegardée")
    
    def clear_log(self):
        """Efface le journal"""
        self.log_text.delete(1.0, tk.END)
        self.log("Journal effacé", "info")
    
    def save_log(self):
        """Sauvegarde le journal"""
        try:
            log_file = os.path.join(self.app_folder, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(self.log_text.get(1.0, tk.END))
            self.log(f"📝 Journal sauvegardé: {os.path.basename(log_file)}", "success")
        except Exception as e:
            self.log(f"❌ Erreur: {str(e)}", "error")
    
    def process_log_queue(self):
        """Traite la file d'attente des logs"""
        try:
            while True:
                msg, level = self.log_queue.get_nowait()
                self.log(msg, level)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.process_log_queue)
    
    def setup_ia_tab(self):
        """Onglet Assistant IA (v3.0)"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="🤖 Assistant IA")
        
        main_frame = tk.Frame(tab, bg=self.colors['bg_primary'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Section 1: Désassembleur (Unpacker)
        unpacker_frame = tk.LabelFrame(main_frame, text="📦 Désassembleur (Unpacker)", 
                                     bg=self.colors['bg_secondary'], font=self.fonts['title'], 
                                     padx=15, pady=15)
        unpacker_frame.pack(fill=tk.X, pady=(0, 20))
        
        tk.Label(unpacker_frame, text="Reconstruisez un projet à partir d'un fichier .txt exporté.", 
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary']).pack(anchor=tk.W)
        
        up_btn_frame = tk.Frame(unpacker_frame, bg=self.colors['bg_secondary'])
        up_btn_frame.pack(fill=tk.X, pady=10)
        
        tk.Button(up_btn_frame, text="📂 Sélectionner un Export .txt", 
                  command=self.run_unpacker,
                  bg=self.colors['accent'], fg='white', padx=15).pack(side=tk.LEFT)
        
        # Section 2: IA Patcher (Beta)
        patcher_frame = tk.LabelFrame(main_frame, text="🛠️ IA Patcher (Appliquer du code)", 
                                    bg=self.colors['bg_secondary'], font=self.fonts['title'], 
                                    padx=15, pady=15)
        patcher_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(patcher_frame, text="Collez ici le code suggéré par l'IA pour l'intégrer au projet actuel.", 
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary']).pack(anchor=tk.W)
        
        self.ia_code_input = tk.Text(patcher_frame, height=10, font=('Courier New', 10))
        self.ia_code_input.pack(fill=tk.BOTH, expand=True, pady=10)
        
        tk.Button(patcher_frame, text="⚡ Appliquer les correctifs au projet", 
                  command=self.apply_ia_patch,
                  bg=self.colors['success'], fg='white', font=self.fonts['title'], padx=20, pady=5).pack()

    def run_unpacker(self):
        """Logique du désassembleur"""
        import os, re
        file_path = filedialog.askopenfilename(filetypes=[("Fichiers Texte", "*.txt")])
        if not file_path: return
        
        dest_folder = filedialog.askdirectory(title="Choisir le dossier de destination pour la reconstruction")
        if not dest_folder: return
        
        try:
            self.log(f"🏗️ Reconstruction démarrée dans: {dest_folder}", "info")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Pattern pour trouver les fichiers [chemin/du/fichier.ext]
            # On cherche le début d'un fichier marqué par [chemin]
            parts = re.split(r'\n\[(.*?)\]\n', content)
            
            # La première partie est l'entête du dossier
            header = parts[0]
            files_data = parts[1:]
            
            file_count = 0
            for i in range(0, len(files_data), 2):
                rel_path = files_data[i]
                file_content = files_data[i+1] if i+1 < len(files_data) else ""
                
                # Nettoyer les sauts de ligne de début/fin ajoutés par le split
                if file_content.startswith('\n'): file_content = file_content[1:]
                
                full_dest = os.path.join(dest_folder, rel_path)
                os.makedirs(os.path.dirname(full_dest), exist_ok=True)
                
                with open(full_dest, 'w', encoding='utf-8') as df:
                    df.write(file_content.strip())
                file_count += 1
            
            messagebox.showinfo("Succès", f"🏗️ Projet reconstruit avec succès !\n{file_count} fichiers créés dans {dest_folder}")
            self.log(f"✅ Reconstruction terminée: {file_count} fichiers.", "success")
            self.open_folder(dest_folder)
            
        except Exception as e:
            messagebox.showerror("Erreur Unpacker", str(e))
            self.log(f"❌ Erreur Unpacker: {e}", "error")

    def apply_ia_patch(self):
        """Tente d'appliquer le code collé au projet actuel (Concept v3.0)"""
        code = self.ia_code_input.get("1.0", tk.END).strip()
        if not code:
            messagebox.showwarning("IA Patcher", "Veuillez d'abord coller du code.")
            return
            
        messagebox.showinfo("IA Patcher (Beta)", 
                          "Analyse du code IA... \n\nCette fonctionnalité va comparer votre code avec la suggestion IA. \n(Bientôt disponible en version automatique complète)")
        self.log("💡 IA Patcher: Analyse de la suggestion terminée.", "info")

    def log(self, message, level='info'):
        """Ajoute un message au journal"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = {'info': 'ℹ️', 'success': '✅', 'warning': '⚠️', 'error': '❌'}.get(level, 'ℹ️')
        formatted = f"[{timestamp}] {icon} {message}\n"
        
        self.log_text.insert(tk.END, formatted, level)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def show_about(self):
        """Affiche la boîte à propos"""
        about_text = """Project Explorer Pro v2.0

Application professionnelle d'export et d'analyse de projets

Fonctionnalités :
✅ Export avec fusion sur une ligne
✅ Gestion .gitignore avec exceptions
✅ Limite de taille configurable
✅ Annulation des exports
✅ Historique des projets
✅ Interface moderne

Créé pour répondre à tous vos besoins !"""
        
        messagebox.showinfo("À propos", about_text)
    
    def run(self):
        """Lance l'application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.root.destroy()
            sys.exit(0)


class CLIApp:
    def __init__(self, args):
        self.args = args
        self.os_type = platform.system()
        self.app_folder = os.path.join(os.path.expanduser("~"), "ProjectExplorer")
        os.makedirs(self.app_folder, exist_ok=True)
        self.config_file = os.path.join(self.app_folder, "config.json")
        try:
            global humanize, psutil
            import humanize, psutil
        except ImportError: pass
        self.load_config()
        
    def load_config(self):
        self.config = {
            'text_extensions': ['.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md', '.sql', '.go', '.rs', '.c', '.cpp', '.h', '.php'],
            'exclude_patterns': ['__pycache__', '.git', '.vscode', 'node_modules', '*.pyc', '.DS_Store', 'venv', 'env', '.env'],
            'max_size_mb': 100,
            'unlimited_size': False,
            'merge_lines': True,
            'compress': False,
            'recent_projects': []
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config.update(json.load(f))
            except: pass

    def list_history(self):
        """Affiche l'historique des projets exportés"""
        projects_db = os.path.join(self.app_folder, "projects.json")
        if not os.path.exists(projects_db):
            print("� Aucun projet exporté pour le moment.")
            return

        try:
            # Vérification que le fichier n'est pas vide
            if os.path.getsize(projects_db) == 0:
                print("💭 Aucun projet exporté pour le moment.")
                return
            with open(projects_db, 'r') as f:
                projects = json.load(f)
            
            if not projects or not isinstance(projects, list):
                print("📭 Aucun projet exporté pour le moment.")
                return

            print(f"\n{'#'*70}")
            print(f"{'HISTORIQUE DES EXPORTS':^70}")
            print(f"{'#'*70}\n")
            print(f"{'#':<4} {'Nom':<22} {'Date':<20} {'Taille':<10} Fichier exporté")
            print("-" * 70)
            
            for idx, p in enumerate(reversed(projects[-20:]), 1):
                size_str = f"{p.get('size', 0) / (1024*1024):.1f} Mo"
                date_str = p.get('date', 'Inconnu')
                name_str = str(p.get('name', 'Inconnu'))[:22]
                export_path = p.get('path', '')
                export_name = p.get('name', 'export')
                txt_file = os.path.join(export_path, f"{export_name}.txt") if export_path else 'Inconnu'
                print(f"{idx:<4} {name_str:<22} {date_str:<20} {size_str:<10} {txt_file}")
            print(f"\n{'#'*70}\n")
        except Exception as e:
            print(f"❌ Erreur lors de la lecture de l'historique: {e}")

    def run_unpacker(self, file_path=None, dest_folder=None):
        """Désassembleur en mode CLI"""
        if not file_path:
            file_path = input("📂 Chemin du fichier .txt à désassembler : ").strip()
        
        if not os.path.exists(file_path):
            print(f"❌ Erreur: Le fichier '{file_path}' n'existe pas.")
            return

        if not dest_folder:
            default_dest = os.path.join(os.getcwd(), "reconstructed_project")
            dest_folder = input(f"🏗️ Dossier de destination [{default_dest}] : ").strip() or default_dest
            
        try:
            print(f"🚀 Reconstruction dans: {dest_folder}")
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            parts = re.split(r'\n\[(.*?)\]\n', content)
            files_data = parts[1:]
            
            file_count = 0
            for i in range(0, len(files_data), 2):
                rel_path = files_data[i]
                file_content = files_data[i+1] if i+1 < len(files_data) else ""
                
                full_dest = os.path.join(dest_folder, rel_path)
                os.makedirs(os.path.dirname(full_dest), exist_ok=True)
                
                with open(full_dest, 'w', encoding='utf-8') as df:
                    df.write(file_content.strip())
                file_count += 1
                
            print(f"✅ Succès ! {file_count} fichiers créés dans {dest_folder}")
        except Exception as e:
            print(f"❌ Erreur: {e}")

    def run_interactive(self):
        """Mode terminal interactif (Option 2)"""
        print("\n--- CONFIGURATION DE L'EXPORT (TERMINAL) ---")
        
        default_path = os.getcwd()
        path = input(f"📁 Chemin du projet [{default_path}]: ").strip() or default_path
        self.args.path = path
        
        folder = os.path.abspath(path)
        if not os.path.exists(folder):
            print(f"❌ Erreur: Le dossier '{folder}' n'existe pas.")
            return

        name = input(f"🆔 Nom du projet [{os.path.basename(folder)}]: ").strip() or os.path.basename(folder)
        self.args.name = name
        
        # Gestion Gitignore
        gitignore_path = os.path.join(folder, ".gitignore")
        use_gitignore = False
        if os.path.exists(gitignore_path):
            ans = input("🔍 Fichier .gitignore détecté. L'utiliser pour les exclusions ? (O/n): ").lower()
            if ans != 'n':
                use_gitignore = True

        # Exclusions personnalisées
        print("\n� GESTION DES EXCLUSIONS")
        print("0. Aucune exclusion supplémentaire")
        
        patterns = self.config['exclude_patterns'].copy()
        if use_gitignore:
            try:
                with open(gitignore_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if line not in patterns:
                                patterns.append(line)
            except: pass

        for i, p in enumerate(patterns, 1):
            print(f"{i}. {p}")
            
        choices = input("\nSélectionnez les numéros à EXCLURE (ex: 1,3,5) ou tapez vos patterns personnalisés: ").strip()
        final_excludes = []
        if choices and choices != "0":
            for part in choices.split(','):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(patterns):
                        final_excludes.append(patterns[idx])
                else:
                    final_excludes.append(part)
        
        self.args.exclude = ",".join(final_excludes)
        
        # Options rapides
        self.args.cl = input("📏 Fusionner les lignes ? (O/n): ").lower() != 'n'
        self.args.yes = input("📂 Ouvrir le dossier à la fin ? (o/N): ").lower() == 'o'
        
        self.run()

    def run(self):
        # Vérification automatique des dépendances CLI
        check_and_install_dependencies(mode="core")
        # Commande spéciale 'ls'
        if self.args.path == 'ls' or getattr(self.args, 'command', None) == 'ls':
            self.list_history()
            return
            
        # Commande spéciale 'unpack' (v3.0)
        if self.args.path == 'unpack' or (hasattr(self.args, 'unpack') and self.args.unpack):
            # On récupère les arguments de la commande
            target_file = self.args.command if self.args.command else None
            # Le reste des arguments est complexe via argparse ici, 
            # on va simplifier si on est en CLI direct
            self.run_unpacker(target_file)
            return

        if not self.args.path:
            self.run_interactive()
            return

        folder = os.path.abspath(self.args.path)
        if not os.path.exists(folder):
            print(f"❌ Erreur: Le dossier '{folder}' n'existe pas.")
            return

        # Configuration logic
        project_name = self.args.name or os.path.basename(folder)
        merge_lines = getattr(self.args, 'cl', True)
        if hasattr(self.args, 'no_merge') and self.args.no_merge:
            merge_lines = False
            
        max_size = float('inf') if getattr(self.args, 'unlimited', False) else (self.args.max_size or self.config.get('max_size_mb', 100)) * 1024 * 1024
        
        # Patterns
        exclude_patterns = self.config['exclude_patterns'].copy()
        if self.args.exclude:
            exclude_patterns.extend([p.strip() for p in self.args.exclude.split(',')])
            
        include_overrides = []
        if self.args.include:
            include_overrides.extend([p.strip() for p in self.args.include.split(',')])

        print(f"🚀 Analyse: {folder}")
        print(f"📦 Nom: {project_name} | Fusion: {'OUI' if merge_lines else 'NON'}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_folder = os.path.join(self.app_folder, f"{project_name}_{timestamp}")
        os.makedirs(export_folder, exist_ok=True)
        txt_file = os.path.join(export_folder, f"{project_name}.txt")
        
        processed_files = 0
        current_size = 0
        
        # Counting files for progress
        total_files = 0
        for root, dirs, files in os.walk(folder):
            total_files += len(files)

        with open(txt_file, 'w', encoding='utf-8') as f:
            f.write(f"PROJECT: {project_name}\n")
            f.write(f"SOURCE: {folder}\n")
            f.write(f"DATE: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"MERGE_LINES: {'YES' if merge_lines else 'NO'}\n")
            f.write("="*60 + "\n\n")
            
            for root, dirs, files in os.walk(folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, folder)
                    
                    # Logic: Include if in overrides, else check excludes
                    should_include = True
                    is_override = False
                    for o in include_overrides:
                        if fnmatch.fnmatch(rel_path, o) or o in rel_path:
                            is_override = True; break
                    
                    if not is_override:
                        for pattern in exclude_patterns:
                            if fnmatch.fnmatch(rel_path, pattern) or pattern in rel_path:
                                should_include = False; break
                    
                    if not should_include: continue
                    
                    file_size = os.path.getsize(file_path)
                    if current_size + file_size > max_size:
                        print("\n⚠️ Limite de taille atteinte.")
                        break
                        
                    f.write(f"\n[{rel_path}]\n")
                    ext = os.path.splitext(file_path)[1].lower()
                    if ext in self.config['text_extensions']:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as fc:
                                content = fc.read()
                                if merge_lines:
                                    content = ' '.join(content.split())
                                f.write(content)
                        except: f.write("[ERREUR LECTURE]")
                    else:
                        f.write("[BINAIRE]")
                    
                    f.write("\n")
                    current_size += file_size
                    processed_files += 1
                    if processed_files % 5 == 0 or processed_files == total_files:
                        sys.stdout.write(f"\rProgression: {processed_files}/{total_files}...")
                        sys.stdout.flush()

        print(f"\n✅ Export terminé !")
        print(f"📍 Fichier: {txt_file}")
        
        # Save to database (history)
        history_db = os.path.join(self.app_folder, "projects.json")
        projects = []
        if os.path.exists(history_db):
            try:
                with open(history_db, 'r') as fh: projects = json.load(fh)
            except: pass
        
        if not isinstance(projects, list): projects = []
        projects.append({
            'name': project_name,
            'source': folder,
            'date': timestamp,
            'path': export_folder,
            'size': current_size,
            'files': processed_files
        })
        try:
            with open(history_db, 'w') as fh: json.dump(projects, fh, indent=2)
        except: pass

        # Open folder if requested
        if getattr(self.args, 'yes', False):
            print(f"📂 Ouverture du dossier: {export_folder}")
            if self.os_type == "Windows":
                os.startfile(export_folder)
            elif self.os_type == "Darwin":
                subprocess.run(["open", export_folder])
            else:
                subprocess.run(["xdg-open", export_folder])

def run_setup_wizard():
    """Assistant de configuration initiale (blx new)"""
    print(f"\n{'CONFIGURATION DE PROJECT EXPLORER PRO':^50}")
    print(f"{'='*50}\n")
    
    print("Choisissez le type d'installation :")
    print("1. ⌨️  Terminal uniquement (Léger, pas d'interface graphique)")
    print("2. 🖥️  Interface graphique complète (Recommandé)")
    print("3. 🔧 Configuration système seulement (Raccourcis/Path)")
    
    choice = input("\nVotre choix [2]: ").strip() or "2"
    
    if choice == "1":
        print("\n📦 Installation des dépendances Terminal...")
        check_and_install_dependencies(mode="core")
    elif choice == "2":
        print("\n📦 Installation complète (GUI + Terminal)...")
        check_and_install_dependencies(mode="full")
    else:
        print("\n⚙️  Vérification système...")

    # Classe utilitaire pour configurer la commande globale sans Tkinter
    class MinimalSetup:
        def __init__(self):
            self.os_type = platform.system()
            self.main_script = os.path.abspath(__file__)
            self.script_dir = os.path.dirname(self.main_script)
            self.app_folder = os.path.join(os.path.expanduser("~"), "ProjectExplorer")
            os.makedirs(self.app_folder, exist_ok=True)
            self.desktop_path = None

        def setup_global_command(self):
            ProfessionalApp.setup_global_command(self)

        def add_to_shell_path(self, path):
            ProfessionalApp.add_to_shell_path(self, path)

    try:
        if choice == "2":
            # Mode GUI : on utilise Tkinter pour créer le raccourci bureau
            try:
                import tkinter as tk
                dummy_root = tk.Tk()
                dummy_root.withdraw()

                class SetupApp(ProfessionalApp):
                    def __init__(self):
                        self.os_type = platform.system()
                        self.main_script = os.path.abspath(__file__)
                        self.script_dir = os.path.dirname(self.main_script)
                        self.app_folder = os.path.join(os.path.expanduser("~"), "ProjectExplorer")
                        os.makedirs(self.app_folder, exist_ok=True)
                        self.desktop_path = self.get_desktop_path()
                        self.setup_global_command()
                        try:
                            self.create_desktop_shortcut()
                        except Exception as e:
                            print(f"⚠️  Raccourci bureau : {e}")

                app_setup = SetupApp()
                # On retire la fenêtre Tk proprement SANS la détruire immédiatement
                # pour éviter l'erreur ThemeChanged
                dummy_root.after(100, dummy_root.destroy)
                dummy_root.mainloop()
            except Exception as e:
                print(f"⚠️  Mode graphique indisponible ({e}). Configuration Terminal seulement.")
                m = MinimalSetup()
                m.setup_global_command()
        else:
            # Modes 1 et 3 : pas besoin de Tkinter
            m = MinimalSetup()
            m.setup_global_command()

        print("\n✅ Configuration terminée avec succès !")
        print("\n🚀 Commandes disponibles :")
        print("   - blx p        : Lancer un export")
        print("   - blx p ls     : Voir l'historique")
        print("   - blx p --gui  : Lancer l'interface graphique")
        print("   - blx unpack   : Désassembler un projet")
        print("   - blx new      : Reconfigurer")

        # Action post-setup selon le choix
        print()
        if choice == "1":
            launch = input("▶️  Voulez-vous lancer un export maintenant ? (o/N): ").strip().lower()
            if launch == 'o':
                import argparse
                args = argparse.Namespace(
                    path=None, command=None, name=None, exclude=None, include=None,
                    max_size=None, unlimited=False, cl=True, yes=False,
                    gui=False, setup=False, uninstall=False, unpack=False, no_merge=False
                )
                app = CLIApp(args)
                app.run_interactive()
        elif choice == "2":
            launch = input("▶️  Voulez-vous lancer l'interface graphique maintenant ? (O/n): ").strip().lower()
            if launch != 'n':
                check_and_install_dependencies(mode="full")
                app = ProfessionalApp()
                app.run()
        else:
            print("✅ Configuration système terminée. Vous pouvez maintenant utiliser 'blx' depuis n'importe où.")
    except Exception as e:
        print(f"❌ Erreur durant le setup: {e}")

def run_uninstall():
    """Désinstalle proprement l'application du système"""
    print(f"\n{'!'*50}")
    print(f"{'DÉSINSTALLATION DE PROJECT EXPLORER PRO':^50}")
    print(f"{'!'*50}\n")
    
    confirm = input("Êtes-vous sûr de vouloir supprimer l'application et toutes ses données ? (o/N): ").lower()
    if confirm != 'o':
        print("Annulé.")
        return

    home = os.path.expanduser("~")
    app_folder = os.path.join(home, "ProjectExplorer")
    bin_dir = os.path.join(home, ".local", "bin")
    
    print("🗑️  Suppression des fichiers de données...")
    if os.path.exists(app_folder):
        shutil.rmtree(app_folder)
    
    print("🗑️  Suppression des commandes globales...")
    for cmd in ["blx", "blx.bat", "bellox", "bellox.bat"]:
        cmd_path = os.path.join(bin_dir, cmd)
        if os.path.exists(cmd_path):
            os.remove(cmd_path)
    
    print("🗑️  Suppression des raccourcis et icônes...")
    icon_path = os.path.join(home, ".local", "share", "icons", "project-explorer.png")
    if os.path.exists(icon_path): os.remove(icon_path)
    
    desktop_files = [
        os.path.join(home, ".local", "share", "applications", "project-explorer.desktop")
    ]
    # Chercher sur le bureau
    for d in ["Desktop", "Bureau", "Desktop.localized"]:
        d_path = os.path.join(home, d)
        if os.path.exists(d_path):
            desktop_files.append(os.path.join(d_path, "project-explorer.desktop"))
    
    for df in desktop_files:
        if os.path.exists(df):
            os.remove(df)
            
    print("🧹 Nettoyage du PATH dans les fichiers shell...")
    for shell_rc in [".bashrc", ".zshrc", ".profile"]:
        rc_path = os.path.join(home, shell_rc)
        if os.path.exists(rc_path):
            try:
                with open(rc_path, 'r') as f:
                    lines = f.readlines()
                
                with open(rc_path, 'w') as f:
                    skip = False
                    for line in lines:
                        if "# Ajout de Project Explorer Pro au PATH" in line:
                            skip = True
                            continue
                        if skip and 'export PATH="$PATH:' in line and bin_dir in line:
                            skip = False
                            continue
                        if not skip:
                            f.write(line)
            except: pass

    print("\n✅ Désinstallation terminée avec succès.")
    print("Note: Le dossier contenant le script source n'a pas été touché.")

def main():
    """Point d'entrée principal avec gestion CLI/GUI"""
    show_banner()
    import argparse
    parser = argparse.ArgumentParser(description="blx p - Project Explorer Pro CLI")
    
    # Subcommands simulator
    parser.add_argument('path', nargs='?', help='Chemin ou "ls" pour l\'historique')
    parser.add_argument('command', nargs='?', help='Commande additionnelle like ls')
    
    # Flags
    parser.add_argument('-n', '--name', help='Nom personnalisé du projet')
    parser.add_argument('-e', '--exclude', help='Patterns à exclure (séparés par virgules)')
    parser.add_argument('-i', '--include', help='Exceptions à inclure (séparés par virgules)')
    parser.add_argument('-m', '--max-size', type=int, help='Taille max en Mo')
    parser.add_argument('-u', '--unlimited', action='store_true', help='Taille illimitée')
    parser.add_argument('-cl', action='store_true', help='Compresser sur une ligne (fusion)')
    parser.add_argument('-y', '-yes', '--yes', action='store_true', help='Ouvrir le dossier de sortie')
    parser.add_argument('--gui', action='store_true', help='Forcer le mode graphique')
    parser.add_argument('--setup', action='store_true', help='Lancer l\'assistant de configuration')
    parser.add_argument('--uninstall', action='store_true', help='Désinstaller l\'application')
    parser.add_argument('--unpack', action='store_true', help='Désassembler un projet (v3.0)')
    
    # Compatibility
    parser.add_argument('--no-merge', action='store_true', help='Désactiver la fusion')

    args = parser.parse_args()

    try:
        # Mode Setup (blx new)
        if getattr(args, 'setup', False):
            run_setup_wizard()
            return

        # Mode Uninstall
        if getattr(args, 'uninstall', False):
            run_uninstall()
            return

        # Si commande 'ls' ou chemin fourni -> Mode CLI
        if args.path or args.command == 'ls':
            check_and_install_dependencies(mode="core")
            app = CLIApp(args)
            app.run()
        elif args.gui:
            check_and_install_dependencies(mode="full")
            app = ProfessionalApp()
            app.run()
        else:
            # Mode Interactif
            if sys.stdout.isatty():
                print("1. 🖥️  Interface Graphique (GUI)")
                print("2. ⌨️  Mode Terminal (Interactif)")
                print("3. 📜 Voir l'historique (ls)")
                print("4. ⚙️  Configuration / Installation (new)")
                print("5. 🗑️  Désinstaller l'application (uninstall)")
                print("q. Quitter")
                
                choice = input("\nVotre choix [1]: ").strip().lower() or "1"
                
                if choice == '1':
                    check_and_install_dependencies(mode="full")
                    app = ProfessionalApp()
                    app.run()
                elif choice == '2':
                    check_and_install_dependencies(mode="core")
                    app = CLIApp(args)
                    app.run_interactive()
                elif choice == '3' or choice == "ls":
                    app = CLIApp(args)
                    app.list_history()
                elif choice == '4' or choice == "new":
                    run_setup_wizard()
                elif choice == '5' or choice == "uninstall":
                    run_uninstall()
                else:
                    return
            else:
                check_and_install_dependencies(mode="full")
                app = ProfessionalApp()
                app.run()
    except Exception as e:
        print(f"ERREUR: {e}")
        if sys.stdout.isatty():
            input("Appuyez sur Entrée pour quitter...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Sortie rapide demandée. Au revoir !")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Erreur système Fatale: {e}")
        sys.exit(1)