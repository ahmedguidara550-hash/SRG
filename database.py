"""
SRG - Société de Rechange et Garniture
Module: Base de données SQLite
"""

import sqlite3
import os
import json
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "db", "srg.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialise toutes les tables de la base de données."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_connection()
    c = conn.cursor()

    # Table des catégories
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            type TEXT DEFAULT 'auto'  -- 'auto' ou 'agri'
        )
    """)

    # Table des pièces
    c.execute("""
        CREATE TABLE IF NOT EXISTS pieces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT UNIQUE,
            nom TEXT NOT NULL,
            categorie_id INTEGER,
            quantite INTEGER DEFAULT 0,
            qmin INTEGER DEFAULT 5,
            prix_achat REAL DEFAULT 0.0,
            prix_vente REAL DEFAULT 0.0,
            unite TEXT DEFAULT 'unité',
            date_ajout TEXT DEFAULT CURRENT_TIMESTAMP,
            date_modif TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categorie_id) REFERENCES categories(id)
        )
    """)

    # Table des factures
    c.execute("""
        CREATE TABLE IF NOT EXISTS factures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE NOT NULL,
            client_nom TEXT DEFAULT 'Client',
            client_tel TEXT DEFAULT '',
            date_facture TEXT DEFAULT CURRENT_TIMESTAMP,
            total_ht REAL DEFAULT 0.0,
            remise REAL DEFAULT 0.0,
            total_ttc REAL DEFAULT 0.0,
            statut TEXT DEFAULT 'ouverte'
        )
    """)

    # Table des lignes de facture
    c.execute("""
        CREATE TABLE IF NOT EXISTS facture_lignes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facture_id INTEGER NOT NULL,
            piece_id INTEGER NOT NULL,
            piece_nom TEXT NOT NULL,
            piece_ref TEXT DEFAULT '',
            quantite INTEGER NOT NULL,
            prix_unitaire REAL NOT NULL,
            total_ligne REAL NOT NULL,
            FOREIGN KEY (facture_id) REFERENCES factures(id),
            FOREIGN KEY (piece_id) REFERENCES pieces(id)
        )
    """)

    # Catégories par défaut
    categories_default = [
        ("Roulements", "auto"),
        ("Filtres", "auto"),
        ("Courroies", "auto"),
        ("Freinage", "auto"),
        ("Moteur", "auto"),
        ("Transmission", "auto"),
        ("Électrique", "auto"),
        ("Pièces Agricoles", "agri"),
        ("Chaînes", "agri"),
        ("Autres", "auto"),
    ]
    for nom, typ in categories_default:
        c.execute("INSERT OR IGNORE INTO categories (nom, type) VALUES (?, ?)", (nom, typ))

    conn.commit()
    conn.close()


# ─────────────────────────────── PIÈCES ───────────────────────────────

def ajouter_piece(nom, categorie_id, quantite, qmin, prix_achat, prix_vente, reference="", unite="unité"):
    conn = get_connection()
    c = conn.cursor()
    if not reference:
        reference = f"SRG-{datetime.now().strftime('%y%m%d%H%M%S')}"
    c.execute("""
        INSERT INTO pieces (reference, nom, categorie_id, quantite, qmin, prix_achat, prix_vente, unite)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (reference, nom, categorie_id, quantite, qmin, prix_achat, prix_vente, unite))
    conn.commit()
    piece_id = c.lastrowid
    conn.close()
    return piece_id


def modifier_piece(piece_id, nom, categorie_id, quantite, qmin, prix_achat, prix_vente, reference="", unite="unité"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE pieces SET nom=?, categorie_id=?, quantite=?, qmin=?, prix_achat=?, prix_vente=?,
        reference=?, unite=?, date_modif=CURRENT_TIMESTAMP
        WHERE id=?
    """, (nom, categorie_id, quantite, qmin, prix_achat, prix_vente, reference, unite, piece_id))
    conn.commit()
    conn.close()


def supprimer_piece(piece_id):
    conn = get_connection()
    conn.execute("DELETE FROM pieces WHERE id=?", (piece_id,))
    conn.commit()
    conn.close()


def get_pieces(search="", categorie_id=None):
    conn = get_connection()
    c = conn.cursor()
    query = """
        SELECT p.*, cat.nom as categorie_nom, cat.type as categorie_type
        FROM pieces p
        LEFT JOIN categories cat ON p.categorie_id = cat.id
        WHERE 1=1
    """
    params = []
    if search:
        query += " AND (p.nom LIKE ? OR p.reference LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if categorie_id:
        query += " AND p.categorie_id = ?"
        params.append(categorie_id)
    query += " ORDER BY p.nom ASC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_piece_by_id(piece_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        SELECT p.*, cat.nom as categorie_nom FROM pieces p
        LEFT JOIN categories cat ON p.categorie_id = cat.id
        WHERE p.id=?
    """, (piece_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_pieces_stock_bas():
    """Retourne les pièces dont quantite <= qmin."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM pieces WHERE quantite <= qmin AND qmin > 0")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ajuster_quantite(piece_id, delta):
    """Ajoute delta à la quantité (delta peut être négatif)."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE pieces SET quantite = MAX(0, quantite + ?) WHERE id=?", (delta, piece_id))
    conn.commit()
    conn.close()


# ─────────────────────────────── CATÉGORIES ───────────────────────────────

def get_categories():
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM categories ORDER BY nom")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def ajouter_categorie(nom, type_cat="auto"):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO categories (nom, type) VALUES (?, ?)", (nom, type_cat))
    conn.commit()
    conn.close()


# ─────────────────────────────── FACTURES ───────────────────────────────

def creer_facture(client_nom="Client", client_tel=""):
    conn = get_connection()
    c = conn.cursor()
    # Numéro de facture unique
    today = datetime.now().strftime("%Y%m%d")
    c.execute("SELECT COUNT(*) FROM factures WHERE date_facture LIKE ?", (f"{datetime.now().strftime('%Y-%m-%d')}%",))
    count = c.fetchone()[0] + 1
    numero = f"FAC-{today}-{count:04d}"
    c.execute("""
        INSERT INTO factures (numero, client_nom, client_tel) VALUES (?, ?, ?)
    """, (numero, client_nom, client_tel))
    conn.commit()
    fid = c.lastrowid
    conn.close()
    return fid, numero


def ajouter_ligne_facture(facture_id, piece_id, quantite):
    """Ajoute une ligne à la facture et décrémente le stock."""
    conn = get_connection()
    c = conn.cursor()

    # Récupérer infos pièce
    c.execute("SELECT * FROM pieces WHERE id=?", (piece_id,))
    piece = c.fetchone()
    if not piece:
        conn.close()
        return False, "Pièce introuvable"
    if piece["quantite"] < quantite:
        conn.close()
        return False, f"Stock insuffisant (disponible: {piece['quantite']})"

    prix_u = piece["prix_vente"]
    total_ligne = prix_u * quantite

    # Vérifier si la pièce est déjà dans cette facture
    c.execute("SELECT id, quantite FROM facture_lignes WHERE facture_id=? AND piece_id=?", (facture_id, piece_id))
    existing = c.fetchone()

    if existing:
        new_qty = existing["quantite"] + quantite
        new_total = prix_u * new_qty
        c.execute("UPDATE facture_lignes SET quantite=?, total_ligne=? WHERE id=?",
                  (new_qty, new_total, existing["id"]))
    else:
        c.execute("""
            INSERT INTO facture_lignes (facture_id, piece_id, piece_nom, piece_ref, quantite, prix_unitaire, total_ligne)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (facture_id, piece_id, piece["nom"], piece["reference"] or "", quantite, prix_u, total_ligne))

    # Décrémenter stock
    c.execute("UPDATE pieces SET quantite = quantite - ? WHERE id=?", (quantite, piece_id))

    # Recalculer total facture
    c.execute("SELECT SUM(total_ligne) FROM facture_lignes WHERE facture_id=?", (facture_id,))
    total = c.fetchone()[0] or 0
    c.execute("UPDATE factures SET total_ht=?, total_ttc=? WHERE id=?", (total, total, facture_id))

    conn.commit()
    conn.close()
    return True, "OK"


def supprimer_ligne_facture(ligne_id):
    """Supprime une ligne et restaure le stock."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM facture_lignes WHERE id=?", (ligne_id,))
    ligne = c.fetchone()
    if ligne:
        # Restaurer stock
        c.execute("UPDATE pieces SET quantite = quantite + ? WHERE id=?",
                  (ligne["quantite"], ligne["piece_id"]))
        c.execute("DELETE FROM facture_lignes WHERE id=?", (ligne_id,))
        # Recalculer total
        facture_id = ligne["facture_id"]
        c.execute("SELECT SUM(total_ligne) FROM facture_lignes WHERE facture_id=?", (facture_id,))
        total = c.fetchone()[0] or 0
        c.execute("UPDATE factures SET total_ht=?, total_ttc=? WHERE id=?", (total, total, facture_id))
        conn.commit()
    conn.close()


def get_lignes_facture(facture_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM facture_lignes WHERE facture_id=? ORDER BY id", (facture_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_facture(facture_id):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM factures WHERE id=?", (facture_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def finaliser_facture(facture_id, remise=0.0):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT total_ht FROM factures WHERE id=?", (facture_id,))
    row = c.fetchone()
    if row:
        total_ht = row["total_ht"]
        total_ttc = total_ht * (1 - remise / 100)
        c.execute("UPDATE factures SET statut='finalisée', remise=?, total_ttc=? WHERE id=?",
                  (remise, total_ttc, facture_id))
        conn.commit()
    conn.close()


def annuler_facture(facture_id):
    """Annule une facture et restaure tout le stock."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM facture_lignes WHERE facture_id=?", (facture_id,))
    lignes = c.fetchall()
    for ligne in lignes:
        c.execute("UPDATE pieces SET quantite = quantite + ? WHERE id=?",
                  (ligne["quantite"], ligne["piece_id"]))
    c.execute("DELETE FROM facture_lignes WHERE facture_id=?", (facture_id,))
    c.execute("UPDATE factures SET statut='annulée' WHERE id=?", (facture_id,))
    conn.commit()
    conn.close()


def get_historique_factures(limit=50):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM factures ORDER BY id DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────── BACKUP ───────────────────────────────

def backup_db(backup_dir=None):
    """Crée une copie de sauvegarde de la base de données."""
    if backup_dir is None:
        backup_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(backup_dir, f"srg_backup_{timestamp}.db")
    shutil.copy2(DB_PATH, dest)
    return dest


def get_stats():
    """Statistiques générales pour le dashboard."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total_pieces FROM pieces")
    total_pieces = c.fetchone()["total_pieces"]
    c.execute("SELECT COUNT(*) as alertes FROM pieces WHERE quantite <= qmin AND qmin > 0")
    alertes = c.fetchone()["alertes"]
    c.execute("SELECT COUNT(*) as factures_today FROM factures WHERE date_facture LIKE ? AND statut='finalisée'",
              (f"{datetime.now().strftime('%Y-%m-%d')}%",))
    factures_today = c.fetchone()["factures_today"]
    c.execute("""SELECT COALESCE(SUM(total_ttc),0) as ca_today FROM factures
                 WHERE date_facture LIKE ? AND statut='finalisée'""",
              (f"{datetime.now().strftime('%Y-%m-%d')}%",))
    ca_today = c.fetchone()["ca_today"]
    conn.close()
    return {
        "total_pieces": total_pieces,
        "alertes_stock": alertes,
        "factures_aujourd_hui": factures_today,
        "ca_aujourd_hui": ca_today
    }