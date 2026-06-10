#!/usr/bin/env python3
"""
SRG — Lanceur universel
Lance l'application desktop + le serveur mobile simultanément
Sauvegarde automatique à chaque démarrage
Compatible Windows, macOS, Linux
"""

import subprocess, sys, os, socket, threading, time, shutil, json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "db", "srg.db")
CFG_PATH = os.path.join(BASE_DIR, "backups", "config.txt")
LOG_PATH = os.path.join(BASE_DIR, "backups", "sync_log.txt")


def check_and_install():
    print("  Vérification des dépendances...")
    import importlib.util
    pkg_map = {"pillow": "PIL", "customtkinter": "customtkinter",
               "reportlab": "reportlab", "flask": "flask"}
    if missing := [pkg for pkg, imp in pkg_map.items()
                   if not importlib.util.find_spec(imp)]:
        print(f"  Installation: {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"])
        print("  ✅ Dépendances installées!")
    else:
        print("  ✅ Toutes les dépendances sont présentes.")


def auto_backup():
    """
    Sauvegarde automatique au démarrage vers le dossier configuré
    (Google Drive, OneDrive, Dropbox, ou dossier local).
    Garde les 30 dernières sauvegardes datées + 1 fichier srg_current.db.
    """
    if not os.path.exists(DB_PATH):
        return

    # Lire le dossier de destination configuré
    dest_dir = None
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH) as f:
            dest_dir = f.read().strip() or None

    # Si pas configuré, utiliser le dossier local backups/
    if not dest_dir:
        dest_dir = os.path.join(BASE_DIR, "backups", "local")

    os.makedirs(dest_dir, exist_ok=True)

    # Copie principale (toujours à jour)
    current = os.path.join(dest_dir, "srg_current.db")
    shutil.copy2(DB_PATH, current)

    # Copie datée
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dated = os.path.join(dest_dir, f"srg_{ts}.db")
    shutil.copy2(DB_PATH, dated)

    # Garder seulement les 30 plus récentes
    all_dated = sorted([
        f for f in os.listdir(dest_dir)
        if f.startswith("srg_2") and f.endswith(".db")
    ])
    while len(all_dated) > 7:
        os.remove(os.path.join(dest_dir, all_dated.pop(0)))

    # Log
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as log:
        size = os.path.getsize(current)
        log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                  f"Backup OK → {dest_dir}  ({size:,} bytes)\n")

    # Afficher info
    label = "Google Drive" if "drive" in dest_dir.lower() else \
            "OneDrive"     if "onedrive" in dest_dir.lower() else \
            "Dropbox"      if "dropbox" in dest_dir.lower() else \
            "Dossier local"
    print(f"  💾 Sauvegarde automatique → {label}")
    print(f"     {dest_dir}")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    os.chdir(BASE_DIR)
    print()
    print("  ══════════════════════════════════════════")
    print("    SRG — Société de Rechange et Garniture ")
    print("  ══════════════════════════════════════════")
    print()

    check_and_install()
    print()

    # Sauvegarde automatique au démarrage
    try:
        auto_backup()
    except Exception as e:
        print(f"  ⚠️  Sauvegarde échouée: {e}")
    print()

    # Lancer serveur mobile
    def run_server():
        subprocess.Popen([sys.executable, "mobile_server.py"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    threading.Thread(target=run_server, daemon=True).start()
    time.sleep(1.5)

    ip = get_local_ip()
    print("  🌐 Serveur mobile démarré:")
    print("     PC        : http://localhost:5000")
    print(f"     Téléphone : http://{ip}:5000")
    print("     (même réseau Wi-Fi requis)")
    print()
    print("  🖥️  Lancement de l'application desktop...")
    print()

    # Lancer le desktop (bloquant)
    subprocess.run([sys.executable, "main.py"])

    # Sauvegarde automatique à la fermeture aussi
    print()
    print("  🔒 Sauvegarde finale à la fermeture...")
    try:
        auto_backup()
        print("  ✅ Données sauvegardées.")
    except Exception as e:
        print(f"  ⚠️  {e}")


if __name__ == "__main__":
    main()