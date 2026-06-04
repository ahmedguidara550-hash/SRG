"""
SRG — Serveur Web Mobile
Accessible depuis smartphone sur le même réseau Wi-Fi
Lance un serveur Flask local qui expose l'interface mobile + API REST
"""

import os, sys, json, socket
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory

# Ajouter le dossier parent pour importer database
sys.path.insert(0, os.path.dirname(__file__))
import database as db

app = Flask(__name__, static_folder="mobile_static")
db.init_db()


def resp(data=None, error=None, status=200):
    if error:
        return jsonify({"ok": False, "error": error}), status
    return jsonify({"ok": True, "data": data}), status


# ──────────── PIÈCES ────────────

@app.route("/api/pieces", methods=["GET"])
def get_pieces():
    search = request.args.get("q", "")
    cat_id = request.args.get("cat", None)
    if cat_id:
        cat_id = int(cat_id)
    return resp(db.get_pieces(search=search, categorie_id=cat_id))


@app.route("/api/pieces/<int:pid>", methods=["GET"])
def get_piece(pid):
    p = db.get_piece_by_id(pid)
    if not p:
        return resp(error="Pièce introuvable", status=404)
    return resp(p)


@app.route("/api/pieces", methods=["POST"])
def add_piece():
    d = request.json
    try:
        pid = db.ajouter_piece(
            d["nom"], d.get("categorie_id"), d.get("quantite", 0),
            d.get("qmin", 5), d.get("prix_achat", 0), d.get("prix_vente", 0),
            d.get("reference", ""), d.get("unite", "unité")
        )
        return resp({"id": pid})
    except Exception as e:
        return resp(error=str(e), status=400)


@app.route("/api/pieces/<int:pid>", methods=["PUT"])
def update_piece(pid):
    d = request.json
    try:
        db.modifier_piece(
            pid, d["nom"], d.get("categorie_id"), d.get("quantite", 0),
            d.get("qmin", 5), d.get("prix_achat", 0), d.get("prix_vente", 0),
            d.get("reference", ""), d.get("unite", "unité")
        )
        return resp({"id": pid})
    except Exception as e:
        return resp(error=str(e), status=400)


@app.route("/api/pieces/<int:pid>", methods=["DELETE"])
def delete_piece(pid):
    db.supprimer_piece(pid)
    return resp({"deleted": pid})


@app.route("/api/alertes", methods=["GET"])
def get_alertes():
    return resp(db.get_pieces_stock_bas())


# ──────────── CATÉGORIES ────────────

@app.route("/api/categories", methods=["GET"])
def get_categories():
    return resp(db.get_categories())


@app.route("/api/categories", methods=["POST"])
def add_categorie():
    d = request.json
    db.ajouter_categorie(d["nom"], d.get("type", "auto"))
    return resp({"ok": True})


# ──────────── FACTURES ────────────

@app.route("/api/factures", methods=["GET"])
def get_factures():
    return resp(db.get_historique_factures())


@app.route("/api/factures", methods=["POST"])
def create_facture():
    d = request.json or {}
    fid, fnum = db.creer_facture(d.get("client_nom", "Client"), d.get("client_tel", ""))
    return resp({"id": fid, "numero": fnum})


@app.route("/api/factures/<int:fid>", methods=["GET"])
def get_facture(fid):
    f = db.get_facture(fid)
    if not f:
        return resp(error="Facture introuvable", status=404)
    lignes = db.get_lignes_facture(fid)
    return resp({"facture": f, "lignes": lignes})


@app.route("/api/factures/<int:fid>/lignes", methods=["POST"])
def add_ligne(fid):
    d = request.json
    ok, msg = db.ajouter_ligne_facture(fid, d["piece_id"], d.get("quantite", 1))
    if not ok:
        return resp(error=msg, status=400)
    return resp({"ok": True})


@app.route("/api/factures/lignes/<int:lid>", methods=["DELETE"])
def del_ligne(lid):
    db.supprimer_ligne_facture(lid)
    return resp({"deleted": lid})


@app.route("/api/factures/<int:fid>/finaliser", methods=["POST"])
def finaliser(fid):
    d = request.json or {}
    db.finaliser_facture(fid, d.get("remise", 0))
    return resp({"ok": True})


@app.route("/api/factures/<int:fid>/annuler", methods=["POST"])
def annuler(fid):
    db.annuler_facture(fid)
    return resp({"ok": True})


# ──────────── STATS ────────────

@app.route("/api/stats", methods=["GET"])
def get_stats():
    return resp(db.get_stats())


# ──────────── PAGE MOBILE ────────────

@app.route("/")
def index():
    return send_from_directory(".", "mobile.html")


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = get_local_ip()
    port = 5000
    print("\n" + "="*55)
    print("  SRG — Serveur Mobile Démarré")
    print("="*55)
    print(f"  PC local    : http://localhost:{port}")
    print(f"  Smartphone  : http://{ip}:{port}")
    print("  (Même réseau Wi-Fi requis)")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)