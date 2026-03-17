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

# Imports graphiques de base (tkinter - pas PIL qui crashe si importé sans fenêtre Tk)
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    tk = None
    ttk = None

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
    if mode == "none": return
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
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user"] + missing,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✅ Installation terminée.")
        except Exception as e:
            print(f"❌ Erreur installation: {e}")


def _silent_setup():
    """Configure PATH et raccourci bureau silencieusement au premier lancement."""
    home = os.path.expanduser("~")
    done_flag = os.path.join(home, "ProjectExplorer", ".first_run_done")
    if os.path.exists(done_flag):
        return  # Déjà configuré
    # Appliquer la configuration sans GUI
    class _Mini:
        def __init__(self):
            self.os_type = platform.system()
            self.main_script = os.path.abspath(__file__)
            self.script_dir = os.path.dirname(self.main_script)
            self.app_folder = os.path.join(home, "ProjectExplorer")
            os.makedirs(self.app_folder, exist_ok=True)
            self.desktop_path = self._get_desktop()
        def _get_desktop(self):
            try:
                res = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True)
                if res.returncode == 0 and res.stdout.strip() and res.stdout.strip() != home:
                    return res.stdout.strip()
            except: pass
            for d in ["Bureau", "Desktop"]:
                p = os.path.join(home, d)
                if os.path.exists(p):
                    return p
            return home
        def setup_global_command(self):
            ProfessionalApp.setup_global_command(self)
        def add_to_shell_path(self, path):
            ProfessionalApp.add_to_shell_path(self, path)
    try:
        m = _Mini()
        m.setup_global_command()
        # Marquer comme fait
        with open(done_flag, 'w') as _f:
            _f.write(datetime.now().isoformat())
        print("✅ Configuration initiale du PATH effectuée.")
        print("💡 Rechargez votre terminal ou tapez: source ~/.bashrc")
    except Exception as e:
        print(f"⚠️  Setup silencieux échoué: {e}")

# Les imports seront fait à la demande dans les classes

class ModalNavigator(tk.Toplevel if tk else object):
    """Un explorateur de fichiers moderne et large pour remplacer les boîtes système trop petites."""
    def __init__(self, parent, mode="directory", title="Sélectionner", filetypes=None,
                 colors_override=None, fonts_override=None):
        if not tk:
            raise ImportError("Tkinter n'est pas installé sur ce système.")
        super().__init__(parent)
        self.title(title)
        self.geometry("900x600")
        self.resizable(True, True)
        # NE PAS appeler transient() ni grab_set() : cause segfault sur Ubuntu/Python3.10
        
        self.mode = mode # "directory" ou "file"
        self.filetypes = filetypes
        self.result = None
        self.current_path = os.path.expanduser("~")
        
        # Style - utilise les couleurs de l'app ou des valeurs par défaut complètes
        full_default_colors = {
            'bg_primary': '#f5f5f5', 'bg_secondary': '#ffffff',
            'bg_tertiary': '#e0e0e0', 'bg_dark': '#2d2d2d',
            'accent': '#0066cc', 'accent_light': '#4d94ff',
            'success': '#28a745', 'error': '#dc3545',
            'text_primary': '#212529', 'text_secondary': '#6c757d', 'text_light': '#ffffff'
        }
        self.colors = colors_override or (parent.colors if hasattr(parent, 'colors') else full_default_colors)
        full_default_fonts = {
            'normal': ('DejaVu Sans', 10), 'title': ('DejaVu Sans', 11, 'bold'),
            'small': ('DejaVu Sans', 9), 'mono': ('Monospace', 10)
        }
        self.fonts = fonts_override or (parent.fonts if hasattr(parent, 'fonts') else full_default_fonts)
        
        self.configure(bg=self.colors['bg_primary'])
        try:
            self.setup_ui()
            self.refresh_list()
        except Exception as e:
            print(f'[Navigator] Erreur UI: {e}')
            self.destroy()
            return
        
        # Centrer sans grab_set (pour éviter le segfault sur Ubuntu/Python3.10)
        self.update_idletasks()
        px = parent.winfo_rootx() + max(0, (parent.winfo_width() - 900) // 2)
        py = parent.winfo_rooty() + max(0, (parent.winfo_height() - 600) // 2)
        self.geometry(f"+{px}+{py}")
        self.lift()
        self.focus_force()

    def setup_ui(self):
        # Barre d'adresse
        path_frame = tk.Frame(self, bg=self.colors['bg_secondary'], padx=10, pady=10)
        path_frame.pack(fill=tk.X)
        
        tk.Button(path_frame, text="⬅️", command=self.go_up, relief=tk.FLAT).pack(side=tk.LEFT, padx=5)
        self.path_entry = tk.Entry(path_frame, font=self.fonts['normal'])
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.path_entry.insert(0, self.current_path)
        self.path_entry.bind("<Return>", lambda e: self.set_path(self.path_entry.get()))
        
        tk.Button(path_frame, text="📁+ Nouveau Dossier", command=self.create_dir, 
                  bg=self.colors['bg_tertiary'], font=('', 8)).pack(side=tk.RIGHT, padx=5)
        
        # Corps principal (Favoris + Liste)
        body = tk.Frame(self, bg=self.colors['bg_primary'])
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Favoris à gauche
        fav_frame = tk.Frame(body, bg=self.colors['bg_secondary'], width=150)
        fav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        fav_frame.pack_propagate(False)
        
        tk.Label(fav_frame, text="FAVORIS", font=('', 10, 'bold'), bg=self.colors['bg_secondary'], fg='gray').pack(pady=10)
        
        favs = [
            ("🏠 Home", os.path.expanduser("~")),
            ("🖥️ Bureau", self.get_fav_path("Bureau")),
            ("📂 Documents", self.get_fav_path("Documents")),
            ("📁 Downloads", self.get_fav_path("Downloads")),
            ("⚙️ ProjectExplorer", os.path.join(os.path.expanduser("~"), "ProjectExplorer"))
        ]
        
        for name, path in favs:
            if os.path.exists(path):
                btn = tk.Button(fav_frame, text=name, anchor="w", relief=tk.FLAT, bg=self.colors['bg_secondary'],
                              command=lambda p=path: self.set_path(p))
                btn.pack(fill=tk.X, padx=5, pady=2)
                btn.bind("<Enter>", lambda e, b=btn: b.config(bg=self.colors['bg_primary']))
                btn.bind("<Leave>", lambda e, b=btn: b.config(bg=self.colors['bg_secondary']))

        # Liste des fichiers à droite
        list_frame = tk.Frame(body, bg=self.colors['bg_secondary'])
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        cols = ("Nom", "Taille", "Modifié")
        self.tree = ttk.Treeview(list_frame, columns=cols, show='headings', selectmode='browse')
        for col in cols: 
            self.tree.heading(col, text=col)
            self.tree.column(col, width=100)
        self.tree.column("Nom", width=400)
        
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        # Footer
        footer = tk.Frame(self, bg=self.colors['bg_primary'], pady=10)
        footer.pack(fill=tk.X)
        
        self.selection_var = tk.StringVar(value="Aucune sélection")
        tk.Label(footer, textvariable=self.selection_var, bg=self.colors['bg_primary'], fg='gray').pack(side=tk.LEFT, padx=20)
        
        tk.Button(footer, text="Annuler", command=self.destroy, width=12).pack(side=tk.RIGHT, padx=10)
        self.ok_btn = tk.Button(footer, text="SÉLECTIONNER", command=self.confirm, 
                                 bg=self.colors['accent'], fg='white', width=20, font=self.fonts['title'])
        self.ok_btn.pack(side=tk.RIGHT, padx=5)

    def get_fav_path(self, name):
        p = os.path.join(os.path.expanduser("~"), name)
        if not os.path.exists(p):
            p = os.path.join(os.path.expanduser("~"), name.title()) # Backup case
        return p

    def set_path(self, path):
        if os.path.isdir(path):
            self.current_path = os.path.abspath(path)
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, self.current_path)
            self.refresh_list()
            self.selection_var.set(self.current_path if self.mode == "directory" else "Aucune sélection")

    def go_up(self):
        self.set_path(os.path.dirname(self.current_path))

    def refresh_list(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        
        try:
            items = os.listdir(self.current_path)
            # Trier : Dossiers d'abord, puis fichiers
            dirs = sorted([d for d in items if os.path.isdir(os.path.join(self.current_path, d))], key=lambda s: s.lower())
            files = sorted([f for f in items if os.path.isfile(os.path.join(self.current_path, f))], key=lambda s: s.lower())
            
            for d in dirs:
                if d.startswith('.') and d != '.gitignore': continue
                stats = os.stat(os.path.join(self.current_path, d))
                date = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                self.tree.insert('', tk.END, text=os.path.join(self.current_path, d), values=("📁 " + d, "--", date), tags=('dir',))
            
            for f in files:
                if f.startswith('.'): continue
                # Filtre extension
                if self.filetypes:
                    ext = os.path.splitext(f)[1].lower()
                    allowed = [t[1].replace("*", "").lower() for t in self.filetypes]
                    if not any(e in ext for e in allowed): continue
                
                stats = os.stat(os.path.join(self.current_path, f))
                size = f"{stats.st_size / 1024:.1f} KB"
                date = datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M')
                self.tree.insert('', tk.END, text=os.path.join(self.current_path, f), values=("📄 " + f, size, date), tags=('file',))
                
            self.tree.tag_configure('dir', foreground='black', font=('', 10, 'bold')) # Dossiers en noir et gras
        except Exception as e:
            print(f"Error listing {self.current_path}: {e}")

    def on_select(self, event):
        item = self.tree.selection()
        if item:
            full_path = self.tree.item(item, 'text')
            is_dir = os.path.isdir(full_path)
            
            if self.mode == "directory" and is_dir:
                self.selection_var.set(full_path)
            elif self.mode == "file" and not is_dir:
                self.selection_var.set(os.path.basename(full_path))
            else:
                self.selection_var.set("Sélection invalide")

    def on_double_click(self, event):
        item = self.tree.selection()
        if item:
            full_path = self.tree.item(item, 'text')
            if os.path.isdir(full_path):
                self.set_path(full_path)
            elif self.mode == "file":
                self.confirm()

    def create_dir(self):
        from tkinter import simpledialog
        name = simpledialog.askstring("Nouveau dossier", "Nom du dossier:", parent=self)
        if name:
            try:
                os.makedirs(os.path.join(self.current_path, name), exist_ok=True)
                self.refresh_list()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))

    def confirm(self):
        item = self.tree.selection()
        if not item and self.mode == "directory":
            self.result = self.current_path
            self.destroy()
            return
            
        if item:
            full_path = self.tree.item(item, 'text')
            if self.mode == "directory" and not os.path.isdir(full_path):
                return
            if self.mode == "file" and os.path.isdir(full_path):
                self.set_path(full_path)
                return
            self.result = full_path
            self.destroy()

def ask_modern_directory(parent, title="Choisir un dossier", colors=None, fonts=None):
    try:
        nav = ModalNavigator(parent, mode="directory", title=title,
                            colors_override=colors, fonts_override=fonts)
        parent.wait_window(nav)
        return nav.result
    except Exception as e:
        print(f'[Navigator] Fallback système: {e}')
        from tkinter import filedialog
        return filedialog.askdirectory(title=title)

def ask_modern_file(parent, title="Ouvrir un fichier", filetypes=None, colors=None, fonts=None):
    try:
        nav = ModalNavigator(parent, mode="file", title=title, filetypes=filetypes,
                            colors_override=colors, fonts_override=fonts)
        parent.wait_window(nav)
        return nav.result
    except Exception as e:
        print(f'[Navigator] Fallback système: {e}')
        from tkinter import filedialog
        return filedialog.askopenfilename(title=title, filetypes=filetypes or [])

class ProfessionalApp:
    def __init__(self):
        # Vérification des bibliothèques graphiques
        if not tk:
            print("❌ Erreur: Tkinter est manquant.")
            print("Lancez 'blx new' pour installer les dépendances nécessaires.")
            sys.exit(1)

        # Création de la fenêtre principale (AVANT d'importer PIL/ImageTk)
        self.root = tk.Tk()

        # Imports tardifs (PIL, psutil, humanize) après la création de la fenêtre Tk
        # (PIL/ImageTk segfault sur Linux si importé avant la fenêtre)
        try:
            global Image, ImageTk, humanize, psutil
            from PIL import Image, ImageTk
            import humanize
            import psutil
        except ImportError as e:
            print(f"⚠️  Bibliothèques optionnelles manquantes ({e}) - certaines fonctions désactivées.")
            Image = ImageTk = humanize = psutil = None
        self.root.title("Project Explorer Pro")
        self.root.geometry("1400x850")
        
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
        if not getattr(self, 'skip_init_setup', False):
            self.check_first_run()
            self.setup_global_command()
        self.load_config()
        self.load_projects()
        self.setup_fonts()
        self.setup_ui()
        self.process_log_queue()

        # Raccourcis clavier globaux
        self.root.bind_all("<Control-a>", self.select_all)
        self.root.bind_all("<Control-A>", self.select_all)
    
    def select_all(self, event):
        """Sélectionne tout le texte dans le widget actif (Entrée ou Texte)"""
        widget = event.widget
        if isinstance(widget, tk.Text):
            widget.tag_add(tk.SEL, "1.0", tk.END)
            widget.mark_set(tk.INSERT, "1.0")
            widget.see(tk.INSERT)
            return "break"
        elif isinstance(widget, (tk.Entry, ttk.Entry)):
            widget.selection_range(0, tk.END)
            widget.icursor(tk.END)
            return "break"
    
    def check_first_run(self):
        """Vérifie si c'est la première exécution et installe sur le bureau"""
        first_run_file = os.path.join(self.app_folder, ".first_run_done")
        
        if not os.path.exists(first_run_file):
            # C'est la première exécution
            self.root.after(100, self.first_run_setup)
    
    def first_run_setup(self):
        """Configuration de la première exécution"""
        # Si _silent_setup a déjà créé le flag, pas besoin de refaire
        done_flag = os.path.join(self.app_folder, ".first_run_done")
        if os.path.exists(done_flag):
            return
        welcome = ("Bienvenue dans Project Explorer Pro ! 🚀\n\n"
                  "L'application va maintenant configurer l'environnement.\n\n"
                  "Cliquez sur OK pour continuer.")
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
elif [ "$1" == "stop" ]; then
    "{sys.executable}" "{self.main_script}" --stop
elif [ "$1" == "uninstall" ]; then
    "{sys.executable}" "{self.main_script}" --uninstall
else
    echo "=== PROJECT EXPLORER PRO ==="
    echo "Usage: blx p [options]  (Mode Export)"
    echo "       blx p ls         (Historique)"
    echo "       blx unpack       (Désassembler un projet)"
    echo "       blx new          (Configuration/Installation)"
    echo "       blx stop         (Quitter/Arrêter)"
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
            
            # print(f"✅ Commande globale configurée: {blx_script}") # Silent in GUI
            
            # Vérifier si bin_dir est dans le PATH
            path_env = os.environ.get("PATH", "")
            if bin_dir.lower() not in path_env.lower():
                self.add_to_shell_path(bin_dir)
                
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
        # On rejette le résultat s'il pointe vers HOME directement
        try:
            res = subprocess.run(['xdg-user-dir', 'DESKTOP'], capture_output=True, text=True)
            xdg_path = res.stdout.strip()
            if res.returncode == 0 and xdg_path and xdg_path != home and os.path.isdir(xdg_path):
                return xdg_path
        except:
            pass

        # 2. Chemins communs (sous-dossiers du home seulement)
        for name in ["Bureau", "Desktop", "Desktop.localized"]:
            p = os.path.join(home, name)
            if os.path.exists(p) and os.path.isdir(p):
                return p
        
        # 3. Créer Bureau si aucun bureau trouvé
        bureau = os.path.join(home, "Bureau")
        os.makedirs(bureau, exist_ok=True)
        return bureau
    
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

        # Activer le défilement des onglets si trop nombreux
        # Note: tabposition='nw' evité car bug sur certains systèmes Linux

        # Création des onglets (chacun protégé pour ne pas bloquer les autres)
        for setup_fn in [
            self.setup_main_tab,
            self.setup_gitignore_tab,
            self.setup_projects_tab,
            self.setup_config_tab,
            self.setup_ia_tab,
        ]:
            try:
                setup_fn()
            except Exception as tab_err:
                # Créer un onglet d'erreur plutôt que de tout bloquer
                err_tab = ttk.Frame(self.notebook)
                self.notebook.add(err_tab, text="⚠️ Erreur")
                tk.Label(err_tab, text=f"Erreur chargement onglet:\n{tab_err}",
                         fg='red').pack(padx=20, pady=20)

        
        status_frame = tk.Frame(self.root, bg=self.colors['bg_tertiary'], height=30)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(status_frame, text="✅ Prêt", 
                                     bg=self.colors['bg_tertiary'], 
                                     anchor=tk.W)
        self.status_label.pack(side=tk.LEFT, padx=10)
        
        # Barre de progression custom (remplace ttk.Progressbar qui segfaulte sur Ubuntu/Py3.10)
        class _ProgressBarWidget:
            """Barre de progression Canvas avec API compatible ttk.Progressbar"""
            def __init__(inner, parent, colors):
                inner._value = 0
                inner._colors = colors
                inner._canvas = tk.Canvas(parent, height=18, width=200,
                                         bg=colors['bg_tertiary'], highlightthickness=0)
            def pack(inner, **kw):
                inner._canvas.pack(**kw)
            def _draw(inner):
                w = inner._canvas.winfo_width() or 200
                inner._canvas.delete('all')
                filled = int(w * inner._value / 100)
                if filled > 0:
                    inner._canvas.create_rectangle(0, 0, filled, 18,
                                                   fill=inner._colors['accent'], outline='')
            def config(inner, **kw):
                if 'value' in kw:
                    inner._value = kw['value']
                inner._draw()
            def __setitem__(inner, key, value):
                if key == 'value':
                    inner._value = value
                    inner._draw()
            def __getitem__(inner, key):
                if key == 'value':
                    return inner._value
                return None

        self.progress = _ProgressBarWidget(status_frame, self.colors)
        self.progress.pack(side=tk.RIGHT, padx=10, pady=6)

    
    def setup_main_tab(self):
        """Onglet principal"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="📦 Export")
        
        # Frame gauche - Infos projet
        left_frame = tk.Frame(tab, bg=self.colors['bg_secondary'], width=450)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="PROJET ACTUEL", font=self.fonts['title'],
                bg=self.colors['bg_secondary'], fg=self.colors['accent']).pack(anchor=tk.W, pady=10, padx=10)
        
        tk.Label(left_frame, text="Chemin:", bg=self.colors['bg_secondary']).pack(anchor=tk.W, padx=10)
        
        self.path_var = tk.StringVar()
        tk.Entry(left_frame, textvariable=self.path_var, font=self.fonts['normal']).pack(fill=tk.X, padx=10, pady=5, ipady=5)
        
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
        
        self.recent_listbox = tk.Listbox(left_frame, height=20,
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
        self.notebook.add(tab, text="🔒 .gitignore")
        
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
        self.notebook.add(tab, text="📚 Projets")
        
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
        self.projects_tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
        
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
        self.notebook.add(tab, text="⚙️ Config")
        
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
    def browse_folder(self):
        """Sélectionne un dossier"""
        folder = ask_modern_directory(self.root, title="Sélectionner le dossier du projet",
                                      colors=self.colors, fonts=self.fonts)
        if folder:
            self.path_var.set(folder)
            self.ia_target_var.set(folder) # Synchro avec l'onglet IA
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
        
        # Section 2: Assistant IA (Appliquer du code)
        patcher_frame = tk.LabelFrame(main_frame, text="🤖 Assistant IA (Paster GPT/Claude)", 
                                    bg=self.colors['bg_secondary'], font=self.fonts['title'], 
                                    padx=15, pady=15)
        patcher_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(patcher_frame, text="Collez ici la réponse de l'IA (nom du fichier + bloc de code).", 
                bg=self.colors['bg_secondary'], fg=self.colors['text_secondary']).pack(anchor=tk.W)

        # Sélection du dossier cible (Plus grand et aéré)
        target_frame = tk.Frame(patcher_frame, bg=self.colors['bg_secondary'])
        target_frame.pack(fill=tk.X, pady=(15, 5))
        
        tk.Label(target_frame, text="📁 Projet Cible :", 
                 bg=self.colors['bg_secondary'], font=self.fonts['title']).pack(side=tk.LEFT)
        
        self.ia_target_var = tk.StringVar(value=self.path_var.get() or os.getcwd())
        ia_entry = tk.Entry(target_frame, textvariable=self.ia_target_var, 
                           font=('Segoe UI', 12) if self.os_type == "Windows" else ('Ubuntu', 12),
                           relief=tk.FLAT, highlightthickness=1, highlightbackground=self.colors['bg_tertiary'])
        ia_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15, ipady=10)
        
        # Bouton intelligent (Recherche + Parcourir)
        tk.Button(target_frame, text="🔍 Trouver / Parcourir", 
                  command=self.browse_ia_target,
                  bg=self.colors['accent'], fg='white', 
                  font=self.fonts['normal'], padx=15, pady=2).pack(side=tk.LEFT)

        # Liste de sélection rapide (Projets récents)
        quick_pick_frame = tk.Frame(patcher_frame, bg=self.colors['bg_secondary'])
        quick_pick_frame.pack(fill=tk.X, pady=(0, 15))
        
        tk.Label(quick_pick_frame, text="⚡ Sélection rapide :", 
                 bg=self.colors['bg_secondary'], fg=self.colors['text_secondary'], font=('', 9)).pack(side=tk.LEFT)
        
        self.ia_recent_combo = ttk.Combobox(quick_pick_frame, state="readonly", width=80, height=25)
        self.ia_recent_combo.pack(side=tk.LEFT, padx=10)
        self.ia_recent_combo.bind("<<ComboboxSelected>>", self.on_ia_recent_selected)
        self.update_ia_recent_combo()
        
        header_bar = tk.Frame(patcher_frame, bg=self.colors['bg_secondary'])
        header_bar.pack(fill=tk.X, pady=(10, 5))
        
        tk.Label(header_bar, text="🤖 Collez ici la réponse de l'IA (nom du fichier + bloc de code):", 
                bg=self.colors['bg_secondary'], font=('Segoe UI', 9, 'italic')).pack(side=tk.LEFT)
        
        # Boutons d'action rapide
        tk.Button(header_bar, text="📋 Coller", command=lambda: self.ia_code_input.insert(tk.END, self.root.clipboard_get()),
                  bg=self.colors['bg_tertiary'], font=('Segoe UI', 8)).pack(side=tk.RIGHT, padx=5)
        tk.Button(header_bar, text="🧹 Vider", command=lambda: self.ia_code_input.delete("1.0", tk.END),
                  bg=self.colors['bg_tertiary'], font=('Segoe UI', 8)).pack(side=tk.RIGHT)
        
        # Layout horizontal pour Input + Liste Détectée
        editor_panel = tk.Frame(patcher_frame, bg=self.colors['bg_secondary'])
        editor_panel.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Gauche: L'éditeur
        editor_left = tk.Frame(editor_panel, bg=self.colors['bg_secondary'])
        editor_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.ia_code_input = tk.Text(editor_left, height=18, font=('Courier New', 10),
                                    relief=tk.FLAT, highlightthickness=1, highlightbackground=self.colors['bg_tertiary'])
        self.ia_code_input.pack(fill=tk.BOTH, expand=True)
        self.ia_code_input.bind("<KeyRelease>", lambda e: self.detect_files_in_ia_input())
        
        # Droite: Liste des fichiers détectés
        detection_frame = tk.LabelFrame(editor_panel, text="🔍 Fichiers Détectés", 
                                      bg=self.colors['bg_secondary'], font=('', 8, 'bold'))
        detection_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        
        self.detected_files_list = tk.Listbox(detection_frame, width=30, bg='white', font=('', 9))
        self.detected_files_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        btn_action = tk.Button(patcher_frame, text="⚡ Appliquer les changements (avec Backups)", 
                  command=self.apply_ia_patch,
                  bg=self.colors['success'], fg='white', font=self.fonts['title'], padx=25, pady=8)
        btn_action.pack()
        
        # Astuce
        tk.Label(patcher_frame, text="💡 Astuce: L'IA détecte automatiquement les blocs comme ```python / ```css etc.", 
                bg=self.colors['bg_secondary'], fg='gray', font=('', 8)).pack(pady=5)

    def detect_files_in_ia_input(self):
        """Détecte les fichiers dans l'input IA et met à jour la liste visuelle"""
        text = self.ia_code_input.get("1.0", tk.END).strip()
        self.detected_files_list.delete(0, tk.END)
        
        pattern = r'(?:[#\*\[]+)?\s*([\w\./\\\\_-]+\.[a-z0-9]+)\s*[#\*\]]*\n\s*```[a-zA-Z]*\n'
        matches = re.findall(pattern, text)
        
        if not matches:
            self.detected_files_list.insert(tk.END, "Aucun fichier détecté...")
            return
            
        for f in list(dict.fromkeys(matches)): # Unique files
            self.detected_files_list.insert(tk.END, f"📄 {f}")

    def update_ia_recent_combo(self):
        """Met à jour la liste des projets récents dans l'onglet IA"""
        if hasattr(self, 'ia_recent_combo'):
            # self.projects est une liste de dicts
            project_names = [p['name'] for p in self.projects]
            # Supprimer les doublons et garder l'ordre
            unique_names = list(dict.fromkeys(project_names))
            self.ia_recent_combo['values'] = unique_names
            if unique_names: 
                self.ia_recent_combo.set("Choisir un projet récent...")

    def on_ia_recent_selected(self, event):
        """Quand on choisit un projet dans la liste rapide"""
        name = self.ia_recent_combo.get()
        # Chercher le chemin correspondant au nom choisi
        for p in self.projects:
            if p['name'] == name:
                path = p.get('source') or p.get('path') # On veut la source pour l'IA
                if path:
                    self.ia_target_var.set(path)
                break

    def browse_ia_target(self):
        """Sélectionne le dossier pour l'IA Assistant (ou recherche si nom tape)"""
        current = self.ia_target_var.get().strip()
        
        # Si c'est juste un nom de projet (pas un chemin), on cherche !
        if current and not os.path.isabs(current) and not current.startswith('.') and not '/' in current:
            self.log(f"🔎 Recherche de '{current}'...", "info")
            self.root.update() # Forcer l'affichage du log
            
            # Utilise CLIApp sans passer None
            dummy_args = lambda: None
            dummy_args.path = None
            matches = CLIApp(dummy_args).find_project_by_name(current)
            
            if matches:
                if len(matches) == 1:
                    self.ia_target_var.set(matches[0])
                    self.log(f"✅ Dossier trouvé via recherche : {matches[0]}", "success")
                    return
                else:
                    self.log(f"❓ {len(matches)} dossiers trouvés pour '{current}'. Choisissez-en un.", "warning")
            else:
                self.log(f"❌ Aucun dossier trouvé pour '{current}'.", "error")

        # Fallback sur le sélecteur classique (en dernier recours)
        folder = ask_modern_directory(self.root, title="Choisir le dossier cible",
                                      colors=self.colors, fonts=self.fonts)
        if folder:
            self.ia_target_var.set(folder)

    def run_unpacker(self):
        """Logique du désassembleur"""
        import os, re
        file_path = ask_modern_file(self.root, title="Sélectionner un Export .txt",
                                   filetypes=[("Fichiers Texte", "*.txt")],
                                   colors=self.colors, fonts=self.fonts)
        if not file_path: return
        
        dest_folder = ask_modern_directory(self.root, title="Dossier de destination",
                                          colors=self.colors, fonts=self.fonts)
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
        """Applique les changements suggérés par l'IA"""
        text = self.ia_code_input.get("1.0", tk.END).strip()
        target_dir = self.ia_target_var.get().strip()
        
        if not text:
            messagebox.showwarning("Assistant IA", "Veuillez d'abord coller la réponse de l'IA.")
            return
            
        if not os.path.isdir(target_dir):
            messagebox.showerror("Assistant IA", f"Le dossier cible est invalide :\n{target_dir}")
            return

        # Parsing amélioré pour supporter plus de styles (Markdown, headings, etc.)
        # Supporte : ### file.py ou **file.py** ou [file.py]
        pattern = r'(?:[#\*\[]+)?\s*([\w\./\\\\_-]+\.[a-z0-9]+)\s*[#\*\]]*\n\s*```[a-zA-Z]*\n(.*?)\n\s*```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if not matches:
            messagebox.showwarning("Assistant IA", "Aucun fichier ou bloc de code (```) détecté dans le texte.")
            return

        # Confirmation
        msg = f"L'IA a détecté {len(matches)} fichiers à modifier.\n\nVoulez-vous les appliquer dans :\n{target_dir} ?"
        if not messagebox.askyesno("Confirmer les changements", msg):
            return

        # Création du dossier de backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = os.path.join(target_dir, "backups_blx", timestamp)
        
        try:
            modified_count = 0
            for rel_path, content in matches:
                # Nettoyage du chemin
                rel_path = re.sub(r'[^\w\.\-/]', '', rel_path).strip('/')
                full_path = os.path.join(target_dir, rel_path)
                
                # 1. Backup si existe
                if os.path.exists(full_path):
                    backup_path = os.path.join(backup_root, rel_path)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    shutil.copy2(full_path, backup_path)
                    status = "Mise à jour (Backup ok)"
                else:
                    status = "Création"
                
                # 2. Ecriture
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content.strip())
                
                self.log(f"Assistant IA: {rel_path} ({status})", "success")
                modified_count += 1
                
            final_msg = f"🎉 Succès ! {modified_count} fichiers traités.\n\n"
            if os.path.exists(backup_root):
                final_msg += f"📍 Backups créés dans :\n{backup_root}"
            
            messagebox.showinfo("Assistant IA", final_msg)
            self.ia_code_input.delete("1.0", tk.END) # Nettoyer après succès
            
        except Exception as e:
            messagebox.showerror("Assistant IA", f"Erreur lors de l'application :\n{e}")
            self.log(f"Erreur Assistant IA: {e}", "error")

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

    def find_project_by_name(self, name):
        """Recherche intelligente d'un dossier par nom dans les dossiers courants"""
        home = os.path.expanduser("~")
        
        # Liste restreinte de dossiers à scanner au lieu de tout OS.WALK(HOME)
        search_roots = []
        for d in ["Documents", "Desktop", "Bureau", "Projects", "Code", "Dev", "Stage"]:
            p = os.path.join(home, d)
            if os.path.exists(p): search_roots.append(p)
            
        if not search_roots: search_roots = [home] # Fallback if all missing
        
        matches = []
        ignore = {'.git', 'node_modules', '__pycache__', '.vscode', '.cache', '.local', '.idea', 'venv', 'env', 'backups_blx'}
        
        try:
            for root_dir in search_roots:
                if matches: break # Si on a déjà trouvé quelque chose on arrête
                for root, dirs, files in os.walk(root_dir):
                    # Filtrer directories pour aller vite (Limite profondeur 4)
                    rel = os.path.relpath(root, root_dir)
                    if rel.count(os.sep) > 3: 
                        dirs[:] = []
                        continue
                        
                    dirs[:] = [d for d in dirs if d not in ignore and not d.startswith('.')]
                    if name.lower() in [d.lower() for d in dirs]:
                        # Trouver l'original matchant le nom
                        for d in dirs:
                            if d.lower() == name.lower():
                                matches.append(os.path.join(root, d))
                        
                    if len(matches) >= 5: break
        except KeyboardInterrupt: pass
        return matches

    def resolve_path(self, path_input):
        """Résout le chemin : direct (., .., /, ~) ou par recherche de nom"""
        if not path_input: return None
        if path_input == '.': return os.getcwd()
        if path_input == '..': return os.path.dirname(os.getcwd())
        
        # 1. Chemin direct
        full_path = os.path.abspath(os.path.expanduser(path_input))
        if os.path.exists(full_path) and os.path.isdir(full_path):
            return full_path
            
        # 2. Recherche par nom
        if os.sep not in path_input and '/' not in path_input:
            matches = self.find_project_by_name(path_input)
            if not matches: return None
            if len(matches) == 1:
                print(f"✅ Dossier trouvé: {matches[0]}")
                return matches[0]
                
            print(f"\n📂 Plusieurs dossiers trouvés pour '{path_input}' :")
            for i, m in enumerate(matches, 1):
                print(f"  {i}. {m}")
            
            choice = input(f"\nVotre choix (1-{len(matches)}) [1]: ").strip() or "1"
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(matches): return matches[idx]
            except: pass
            return matches[0]
        return None

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
            file_path = input("📂 Chemin du fichier .txt à désassembler ('q' pour annuler) : ").strip()
            if file_path.lower() in ('q', 'quit', 'annuler', 's'):
                return
        
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

    def apply_ai_changes(self, text, target_dir):
        """Parse le texte de l'IA et applique les changements avec backup"""
        # On cherche un titre (Markdown, gras ou [brackets]) suivi de texte puis un bloc de code
        # On essaie d'isoler un chemin de fichier (ex: index.html ou css/style.css)
        # On accepte les emojis et décorations autour
        pattern = r'(?:#+|(?:\*\*)|\[).*?([\w\./\\_-]+\.[a-z0-9]+).*?\n\s*```[\w]*\n(.*?)\n\s*```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if not matches:
            print("⚠️ Aucun fichier détecté. Vérifiez le format (Titre du fichier puis bloc de code ```)")
            return False

        # Création du dossier de backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = os.path.join(target_dir, "backups_blx", timestamp)
        
        modified_count = 0
        for rel_path, content in matches:
            # Nettoyer le chemin (enlever emojis ou espaces superflus)
            rel_path = re.sub(r'[^\w\.\-/]', '', rel_path).strip('/')
            full_path = os.path.join(target_dir, rel_path)
            
            # 1. Backup si le fichier existe
            if os.path.exists(full_path):
                backup_path = os.path.join(backup_root, rel_path)
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(full_path, backup_path)
                status = "Mise à jour (Backup créé)"
            else:
                status = "Nouveau fichier"
            
            # 2. Ecriture du nouveau contenu
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            
            print(f"✅ {rel_path} : {status}")
            modified_count += 1
            
        if modified_count > 0:
            print(f"\n🎉 Succès ! {modified_count} fichiers traités.")
            print(f"📍 Backups disponibles dans : {backup_root}")
            return True
        return False

    def run_ai_assistant(self, target_dir=None):
        """Mode interactif pour coller une réponse d'IA"""
        print(f"\n{'🤖 MODE ASSISTANT IA':^50}")
        print("="*50)
        
        if not target_dir:
            print(f"📍 Répertoire de travail : {os.getcwd()}")
            path_input = input("📁 Dossier cible (Entrée pour '.') : ").strip() or "."
            target_dir = self.resolve_path(path_input)
            if not target_dir:
                print("❌ Dossier introuvable.")
                return

        print("\n📝 Collez la réponse de l'IA ci-dessous.")
        print("💡 (Sous Linux/Mac: Entrée puis Ctrl+D pour valider)")
        print("💡 (Sous Windows: Entrée puis Ctrl+Z puis Entrée)")
        print("-" * 30)
        
        lines = []
        try:
            while True:
                line = sys.stdin.readline()
                if not line: break
                lines.append(line)
        except EOFError: pass
        
        ai_text = "".join(lines)
        if not ai_text.strip():
            print("❌ Texte vide.")
            return

        print("\n⚙️ Analyse et application des changements...")
        self.apply_ai_changes(ai_text, target_dir)

    def run_interactive(self):
        """Mode terminal interactif (Option 2)"""
        print("\n--- CONFIGURATION DE L'EXPORT (TERMINAL) ---")
        
        folder = None
        while True:
            print(f"\n📍 Répertoire courant : {os.getcwd()}")
            path_input = input("📁 Chemin ou nom du projet (Entrée pour '.', 'q' pour annuler) : ").strip()
            
            if path_input.lower() in ('q', 'quit', 'annuler'):
                return
            
            if not path_input:
                path_input = "."
                
            folder = self.resolve_path(path_input)
            if folder:
                break
            print(f"❌ Erreur: Impossible de localiser '{path_input}'. Veuillez réessayer.")
            
        self.args.path = folder
        folder = os.path.abspath(folder)

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

        folder = self.resolve_path(self.args.path)
        if not folder:
            tried_path = os.path.abspath(os.path.expanduser(self.args.path))
            print(f"❌ Erreur: Le dossier '{self.args.path}' est introuvable.")
            print(f"📍 Chemin tenté (absolu) : {tried_path}")
            return

        folder = os.path.abspath(folder)

        # Configuration logic
        project_name = self.args.name or os.path.basename(folder)
        merge_lines = getattr(self.args, 'cl', True)
        if hasattr(self.args, 'no_merge') and self.args.no_merge:
            merge_lines = False
            
        max_size = float('inf') if getattr(self.args, 'unlimited', False) else (self.args.max_size or self.config.get('max_size_mb', 500)) * 1024 * 1024
        
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
            
            limit_reached = False
            for root, dirs, files in os.walk(folder):
                if limit_reached: break
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
                    
                    try:
                        file_size = os.path.getsize(file_path)
                    except: continue

                    if current_size + file_size > max_size:
                        print(f"\n⚠️ Limite de taille atteinte ({self.config.get('max_size_mb', 500)} Mo).")
                        print("👉 Utilisez l'option --unlimited ou -u pour ignorer cette limite.")
                        limit_reached = True
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
    
    choice = input("\nVotre choix [2]: ").strip() or "2"
    
    if choice == "1":
        print("\n📦 Installation des dépendances Terminal...")
        check_and_install_dependencies(mode="core")
    else:
        print("\n📦 Installation complète (GUI + Terminal)...")
        check_and_install_dependencies(mode="full")

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
                dummy_root.after(100, dummy_root.destroy)
                dummy_root.mainloop()
            except Exception as e:
                print(f"⚠️  Mode graphique indisponible ({e}). Configuration Terminal seulement.")
                m = MinimalSetup()
                m.setup_global_command()
        else:
            m = MinimalSetup()
            m.setup_global_command()

        print("\n✅ Configuration terminée avec succès !")
        print("\n🚀 Commandes disponibles :")
        print("   - blx p        : Lancer un export")
        print("   - blx p ls     : Voir l'historique")
        print("   - blx p --gui  : Lancer l'interface graphique")

        if choice == "2":
            # Lancer l'interface graphique automatiquement et quitter le terminal
            print("\n🚀 Lancement de l'interface graphique...")
            try:
                cmd = [sys.executable, os.path.abspath(__file__), "--gui"]
                subprocess.Popen(cmd, start_new_session=True)
            except Exception as e:
                print(f"⚠️ Erreur lors du lancement : {e}")
            sys.exit(0)  # Fermer le terminal proprement
        else:
            print("\n💡 Tapez 'blx p' pour commencer votre premier export.")

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
        # Entrée menu système
        os.path.join(home, ".local", "share", "applications", "project-explorer.desktop"),
        # Fichier directement dans le home (cas xdg-user-dir retournant HOME)
        os.path.join(home, "project-explorer.desktop"),
    ]
    # Chercher dans les dossiers bureau connus
    for d in ["Desktop", "Bureau", "Desktop.localized"]:
        d_path = os.path.join(home, d)
        if os.path.exists(d_path):
            desktop_files.append(os.path.join(d_path, "project-explorer.desktop"))
    
    for df in desktop_files:
        if os.path.exists(df):
            os.remove(df)
            print(f"   ✓ Supprimé: {df}")
            
    print("🧹 Nettoyage du PATH dans les fichiers shell...")
    for shell_rc in [".bashrc", ".zshrc", ".profile"]:
        rc_path = os.path.join(home, shell_rc)
        if os.path.exists(rc_path):
            try:
                with open(rc_path, 'r') as f:
                    content = f.read()
                # Supprimer le bloc ajouté par add_to_shell_path (commentaire + export)
                # Le bloc écrit est : \n# Project Explorer Pro\nexport PATH="$PATH:<bin_dir>"\n
                import re as _re
                # Nettoyer toutes les variantes possibles du commentaire
                cleaned = _re.sub(
                    r'\n# Project Explorer Pro\nexport PATH=\"\$PATH:[^"]+\"\n',
                    '',
                    content
                )
                # Ancienne variante aussi (au cas où)
                cleaned = _re.sub(
                    r'\n# Ajout de Project Explorer Pro au PATH\nexport PATH=\"\$PATH:[^"]+\"\n',
                    '',
                    cleaned
                )
                if cleaned != content:
                    with open(rc_path, 'w') as f:
                        f.write(cleaned)
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
    parser.add_argument('-cl', '--cl', action='store_true', help='Compresser sur une ligne (fusion)')
    parser.add_argument('-y', '-yes', '--yes', action='store_true', help='Ouvrir le dossier de sortie')
    parser.add_argument('--gui', action='store_true', help='Forcer le mode graphique')
    parser.add_argument('--setup', action='store_true', help='Lancer l\'assistant de configuration')
    parser.add_argument('--uninstall', action='store_true', help='Désinstaller l\'application')
    parser.add_argument('--ai', action='store_true', help='Mode Assistant IA (Appliquer réponse IA)')
    parser.add_argument('--unpack', action='store_true', help='Désassembler un projet (v3.0)')
    parser.add_argument('-s', '--stop', action='store_true', help='Arrêter et quitter l\'application')
    
    # Compatibility
    parser.add_argument('--no-merge', action='store_true', help='Désactiver la fusion')

    args = parser.parse_args()

    try:
        # 1. First run priority commands (non-loop)
        if getattr(args, 'setup', False):
            run_setup_wizard()
            return

        if getattr(args, 'uninstall', False):
            run_uninstall()
            return

        # 1b. Configuration automatique du PATH au premier lancement (silencieux)
        _silent_setup()

        # 2. Force GUI via flag
        if getattr(args, 'gui', False):
            check_and_install_dependencies(mode="full")
            app = ProfessionalApp()
            app.run()
            return

        # 3. Command with path or 'ls' -> Mode Persistent CLI
        while True:
            ai_mode = getattr(args, 'ai', False)
            unpack_mode = getattr(args, 'unpack', False)
            
            if args.path or args.command == 'ls' or unpack_mode or ai_mode:
                if getattr(args, 'stop', False) and not (args.path or unpack_mode or ai_mode):
                    print("👋 Arrêt de Project Explorer Pro...")
                    break
                    
                app = CLIApp(args)
                
                if ai_mode:
                    app.run_ai_assistant(app.resolve_path(args.path) if args.path else None)
                else:
                    app.run()
                
                if getattr(args, 'stop', False):
                    break
                
                args.path = None
                args.command = None
                args.unpack = False
                args.ai = False
                continue

            # 4. No arguments -> Show interactive menu
            if sys.stdout.isatty():
                print("\n" + "="*45)
                print(f"{'🔱 MENU GÉNÉRAL PROJECT EXPLORER PRO':^45}")
                print("="*45)
                print("1. 🖥️  Interface Graphique (GUI)")
                print("2. ⌨️  Mode Terminal (Interactif)")
                print("3. 📜 Voir l'historique (ls)")
                print("4. ⚙️  Installer/Reconfigurer (blx new)")
                print("5. 📦 Désassemblage (unpack)")
                print("6. 🤖 Assistant IA (Paster GPT/Claude)")
                print("7. 🗑️  Désinstaller")
                print("s. Quitter")
                
                choice = input("\nAction : ").strip().lower()
                
                if choice == '1':
                    check_and_install_dependencies(mode="full")
                    app = ProfessionalApp()
                    app.run()
                elif choice == '2':
                    app = CLIApp(args)
                    app.run_interactive()
                elif choice == '3':
                    args.path = 'ls'
                    continue
                elif choice == '4':
                    run_setup_wizard()
                elif choice == '5':
                    args.unpack = True
                    continue
                elif choice == '6':
                    app = CLIApp(args)
                    app.run_ai_assistant()
                elif choice == '7':
                    run_uninstall()
                    break
                elif choice in ('s', 'stop', 'q', 'quit'):
                    print("👋 À bientôt !")
                    break
                else:
                    print("⚠️ Choix invalide.")
            else:
                # Mode non-TTY (Raccourci Bureau) -> GUI directement
                check_and_install_dependencies(mode="full")
                app = ProfessionalApp()
                app.run()
                break
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