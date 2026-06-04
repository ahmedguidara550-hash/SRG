#!/usr/bin/env python3
"""
SRG — Lanceur universel
Lance l'application desktop + le serveur mobile simultanément
Compatible Windows, macOS, Linux
"""

import subprocess
import sys
import os
import socket
import threading
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REQUIRED_PACKAGES = ["customtkinter", "pillow", "reportlab", "flask"]


def check_and_install():
    print("  Vérification des dépendances...")
    import importlib
    missing = []
    pkg_map = {"pillow": "PIL", "customtkinter": "customtkinter",
               "reportlab": "reportlab", "flask": "flask"}
    for pkg, imp in pkg_map.items():
        try:
            importlib.import_module(imp)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"  Installation: {', '.join(missing)}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"])
        print("  ✅ Dépendances installées!")
    else:
        print("  ✅ Toutes les dépendances sont présentes.")


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

    # Lancer serveur mobile en thread séparé
    def run_server():
        subprocess.Popen(
            [sys.executable, "mobile_server.py"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1.5)

    ip = get_local_ip()
    print(f"  🌐 Serveur mobile démarré:")
    print(f"     PC      : http://localhost:5000")
    print(f"     Téléphone: http://{ip}:5000")
    print(f"     (même réseau Wi-Fi requis)")
    print()
    print("  🖥️  Lancement de l'application desktop...")
    print()

    # Lancer l'application desktop (bloquant)
    subprocess.run([sys.executable, "main.py"])


if __name__ == "__main__":
    main()