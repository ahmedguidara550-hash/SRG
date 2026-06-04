"""
SRG — Synchronisation automatique (Backup)
Copie automatiquement la base de données vers Google Drive, OneDrive, ou Dropbox
À lancer en tâche planifiée Windows (Task Scheduler) ou crontab Linux/macOS

Usage:
    python sync_backup.py --drive "C:/Users/VotreNom/Google Drive/SRG_Backup"
    python sync_backup.py --onedrive "C:/Users/VotreNom/OneDrive/SRG_Backup"
    python sync_backup.py --dropbox "C:/Users/VotreNom/Dropbox/SRG_Backup"
    python sync_backup.py --auto   (détecte automatiquement)
"""

import os
import sys
import shutil
import argparse
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "db", "srg.db")
LOG_PATH = os.path.join(BASE_DIR, "backups", "sync_log.txt")
CFG_PATH = os.path.join(BASE_DIR, "backups", "sync_config.json")

# Chemins par défaut selon l'OS et le service
COMMON_CLOUD_PATHS = {
    "Google Drive": [
        os.path.expanduser("~/Google Drive"),
        os.path.expanduser("~/GoogleDrive"),
        "C:/Users/%USERNAME%/Google Drive",
        "D:/Google Drive",
    ],
    "OneDrive": [
        os.path.expanduser("~/OneDrive"),
        "C:/Users/%USERNAME%/OneDrive",
    ],
    "Dropbox": [
        os.path.expanduser("~/Dropbox"),
        "C:/Users/%USERNAME%/Dropbox",
    ],
}


def log(msg):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def find_cloud_folder():
    """Détecte automatiquement un dossier cloud disponible."""
    for service, paths in COMMON_CLOUD_PATHS.items():
        for path in paths:
            expanded = os.path.expandvars(path)
            if os.path.isdir(expanded):
                log(f"✅ Service cloud détecté: {service} → {expanded}")
                return os.path.join(expanded, "SRG_Backup")
    return None


def save_config(path, service_name=""):
    os.makedirs(os.path.dirname(CFG_PATH), exist_ok=True)
    with open(CFG_PATH, "w") as f:
        json.dump({"backup_path": path, "service": service_name,
                   "configured_at": datetime.now().isoformat()}, f, indent=2)


def load_config():
    if os.path.exists(CFG_PATH):
        with open(CFG_PATH) as f:
            return json.load(f)
    return None


def do_backup(dest_dir):
    """Effectue la sauvegarde vers dest_dir."""
    os.makedirs(dest_dir, exist_ok=True)

    if not os.path.exists(DB_PATH):
        log("❌ Base de données introuvable: " + DB_PATH)
        return False

    # Copie principale (toujours présente, écrasée à chaque fois)
    main_dest = os.path.join(dest_dir, "srg_current.db")
    shutil.copy2(DB_PATH, main_dest)

    # Copie datée (garde l'historique — max 30 fichiers)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    dated_dest = os.path.join(dest_dir, f"srg_{timestamp}.db")
    shutil.copy2(DB_PATH, dated_dest)

    # Nettoyer les anciennes sauvegardes (garder les 30 plus récentes)
    backups = sorted([
        f for f in os.listdir(dest_dir)
        if f.startswith("srg_") and f.endswith(".db") and f != "srg_current.db"
    ])
    while len(backups) > 30:
        old = os.path.join(dest_dir, backups.pop(0))
        os.remove(old)
        log(f"🗑️  Ancienne sauvegarde supprimée: {old}")

    size = os.path.getsize(main_dest)
    log(f"✅ Sauvegarde réussie → {dest_dir} ({size:,} bytes)")
    return True


def setup_windows_task(dest_dir):
    """Crée une tâche planifiée Windows pour lancer le backup toutes les heures."""
    script_path = os.path.abspath(__file__)
    task_cmd = (
        f'schtasks /create /tn "SRG_Backup" /tr '
        f'"{sys.executable} \"{script_path}\" --path \"{dest_dir}\"" '
        f'/sc hourly /f'
    )
    os.system(task_cmd)
    log(f"⏰ Tâche planifiée Windows créée (toutes les heures)")


def main():
    parser = argparse.ArgumentParser(description="SRG — Synchronisation backup")
    parser.add_argument("--path",     help="Dossier de destination personnalisé")
    parser.add_argument("--drive",    help="Dossier Google Drive")
    parser.add_argument("--onedrive", help="Dossier OneDrive")
    parser.add_argument("--dropbox",  help="Dossier Dropbox")
    parser.add_argument("--auto",     action="store_true", help="Détection automatique")
    parser.add_argument("--setup",    action="store_true", help="Configurer la tâche planifiée Windows")
    args = parser.parse_args()

    log("─── Démarrage SRG Sync Backup ───")

    # Déterminer le dossier de destination
    dest = None
    if args.path:
        dest = args.path
    elif args.drive:
        dest = os.path.join(args.drive, "SRG_Backup")
        save_config(dest, "Google Drive")
    elif args.onedrive:
        dest = os.path.join(args.onedrive, "SRG_Backup")
        save_config(dest, "OneDrive")
    elif args.dropbox:
        dest = os.path.join(args.dropbox, "SRG_Backup")
        save_config(dest, "Dropbox")
    elif args.auto:
        dest = find_cloud_folder()
        if dest:
            save_config(dest)
    else:
        # Lire la config sauvegardée
        cfg = load_config()
        if cfg:
            dest = cfg.get("backup_path")
            log(f"📂 Config chargée: {dest} ({cfg.get('service','')})")
        else:
            # Essayer de détecter automatiquement
            dest = find_cloud_folder()
            if dest:
                save_config(dest)
            else:
                # Backup local uniquement
                dest = os.path.join(BASE_DIR, "backups", "local")
                log("⚠️  Aucun service cloud détecté. Sauvegarde locale uniquement.")

    if not dest:
        log("❌ Impossible de déterminer le dossier de sauvegarde.")
        log("   Usage: python sync_backup.py --drive 'C:/Users/Nom/Google Drive'")
        sys.exit(1)

    success = do_backup(dest)

    if args.setup and success and sys.platform.startswith("win"):
        setup_windows_task(dest)

    log("─── Fin SRG Sync Backup ───\n")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()