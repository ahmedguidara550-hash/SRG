"""
SRG — Application de Gestion de Stock et Facturation
Société de Rechange et Garniture
Version 3.0
"""

import contextlib
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk
import os, subprocess, sys
from datetime import datetime, timedelta

import database as db
from pdf_generator import generer_facture_pdf

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

COLOR_RED   = "#C0392B"
COLOR_RED_H = "#A93226"
COLOR_WHITE = "#FFFFFF"
COLOR_BG    = "#F5F5F5"
COLOR_DARK  = "#1A1A1A"
COLOR_GRAY  = "#777777"
COLOR_LGRAY = "#E8E8E8"
COLOR_WARN  = "#E67E22"
COLOR_GREEN = "#27AE60"
COLOR_BLUE  = "#2980B9"

FONT_TITLE  = ("Helvetica", 22, "bold")
FONT_HEADER = ("Helvetica", 13, "bold")
FONT_NORMAL = ("Helvetica", 11)
FONT_SMALL  = ("Helvetica", 9)
FONT_BOLD   = ("Helvetica", 11, "bold")


# ─────────────────────────────── WIDGETS ───────────────────────────────
class RedButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_RED); kwargs.setdefault("hover_color", COLOR_RED_H)
        kwargs.setdefault("text_color", COLOR_WHITE); kwargs.setdefault("corner_radius", 6)
        kwargs.setdefault("font", FONT_BOLD)
        super().__init__(master, **kwargs)

class GrayButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_LGRAY); kwargs.setdefault("hover_color", "#D0D0D0")
        kwargs.setdefault("text_color", COLOR_DARK); kwargs.setdefault("corner_radius", 6)
        kwargs.setdefault("font", FONT_NORMAL)
        super().__init__(master, **kwargs)

class SectionCard(ctk.CTkFrame):
    def __init__(self, master, title="", **kwargs):
        kwargs.setdefault("fg_color", COLOR_WHITE); kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **kwargs)
        if title:
            ctk.CTkLabel(self, text=title, font=FONT_HEADER,
                         text_color=COLOR_DARK).pack(anchor="w", padx=15, pady=(12, 5))

def _make_tree_style():
    s = ttk.Style()
    s.theme_use("clam")
    s.configure("Treeview", font=("Helvetica", 10), rowheight=30,
                background=COLOR_WHITE, fieldbackground=COLOR_WHITE, foreground=COLOR_DARK)
    s.configure("Treeview.Heading", font=("Helvetica", 10, "bold"),
                background=COLOR_RED, foreground=COLOR_WHITE, relief="flat")
    s.map("Treeview", background=[("selected", "#FDECEA")], foreground=[("selected", COLOR_RED)])


def _make_red_header(parent, title, height=50):
    """Crée une barre d'en-tête rouge standard et retourne le frame."""
    hdr = ctk.CTkFrame(parent, fg_color=COLOR_RED, corner_radius=8, height=height)
    hdr.pack(fill="x", padx=12, pady=(12, 8))
    hdr.pack_propagate(False)
    ctk.CTkLabel(hdr, text=title, font=FONT_HEADER,
                 text_color=COLOR_WHITE).pack(side="left", padx=15, pady=12)
    return hdr


# ─────────────────────────────── DIALOG PIÈCE STOCK ───────────────────────────────
class PieceDialog(ctk.CTkToplevel):
    def __init__(self, master, categories, piece=None, on_save=None):
        super().__init__(master)
        self.title("Modifier pièce" if piece else "Nouvelle pièce")
        self.geometry("480x560"); self.resizable(False, False); self.grab_set()
        self.categories = categories; self.piece = piece; self.on_save = on_save
        self._build()
        if piece: self._fill(piece)

    def _build(self):
        self.configure(fg_color=COLOR_BG)
        hdr = ctk.CTkFrame(self, fg_color=COLOR_RED, corner_radius=0, height=50)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="✏️  Modifier" if self.piece else "➕  Nouvelle pièce",
                     font=FONT_HEADER, text_color=COLOR_WHITE).pack(side="left", padx=15, pady=12)
        form = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG, corner_radius=0)
        form.pack(fill="both", expand=True, padx=20, pady=15)

        def row(lbl, fn):
            ctk.CTkLabel(form, text=lbl, font=FONT_BOLD, text_color=COLOR_DARK,
                         anchor="w").pack(fill="x", pady=(8,2))
            w = fn(form); w.pack(fill="x"); return w

        self.e_nom   = row("Désignation *", lambda p: ctk.CTkEntry(p, placeholder_text="ex: Roulement 6205", height=36))
        self.e_ref   = row("Référence",     lambda p: ctk.CTkEntry(p, placeholder_text="auto si vide", height=36))
        ctk.CTkLabel(form, text="Catégorie *", font=FONT_BOLD, text_color=COLOR_DARK,
                     anchor="w").pack(fill="x", pady=(8,2))
        self.cat_names = [c["nom"] for c in self.categories]
        self.cat_var   = ctk.StringVar(value=self.cat_names[0] if self.cat_names else "")
        ctk.CTkOptionMenu(form, variable=self.cat_var, values=self.cat_names, height=36).pack(fill="x")

        grid = ctk.CTkFrame(form, fg_color="transparent")
        grid.pack(fill="x", pady=(8,0)); grid.columnconfigure((0,1), weight=1)

        def nf(parent, lbl, ph, r, col):
            pad = (0 if col==0 else 8, 0)
            ctk.CTkLabel(parent, text=lbl, font=FONT_BOLD, text_color=COLOR_DARK,
                         anchor="w").grid(row=r*2, column=col, sticky="w", padx=pad)
            e = ctk.CTkEntry(parent, placeholder_text=ph, height=36)
            e.grid(row=r*2+1, column=col, sticky="ew", padx=pad, pady=(2,8)); return e

        self.e_qte   = nf(grid, "Quantité *",        "0",    0, 0)
        self.e_qmin  = nf(grid, "Qté minimale *",    "5",    0, 1)
        self.e_pachat= nf(grid, "Prix achat (TND) *","0.00", 1, 0)
        self.e_pvente= nf(grid, "Prix vente (TND) *","0.00", 1, 1)
        self.e_unite = row("Unité", lambda p: ctk.CTkEntry(p, placeholder_text="unité, paire…", height=36))

        bf = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=0)
        bf.pack(fill="x", side="bottom")
        GrayButton(bf, text="Annuler", command=self.destroy, width=120).pack(side="right", padx=(5,15), pady=12)
        RedButton(bf, text="💾  Enregistrer", command=self._save, width=160).pack(side="right", padx=5, pady=12)

    def _fill(self, p):
        self.e_nom.insert(0, p["nom"]); self.e_ref.insert(0, p.get("reference","") or "")
        if (cn := p.get("categorie_nom","")) in self.cat_names: self.cat_var.set(cn)
        self.e_qte.insert(0, str(p["quantite"])); self.e_qmin.insert(0, str(p["qmin"]))
        self.e_pachat.insert(0, str(p["prix_achat"])); self.e_pvente.insert(0, str(p["prix_vente"]))
        self.e_unite.insert(0, p.get("unite","unité") or "unité")

    def _save(self):
        nom = self.e_nom.get().strip()
        if not nom: messagebox.showerror("Erreur", "Désignation obligatoire.", parent=self); return
        try:
            qte=int(self.e_qte.get() or 0); qmin=int(self.e_qmin.get() or 0)
            pa=float(self.e_pachat.get() or 0); pv=float(self.e_pvente.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Valeurs numériques invalides.", parent=self); return
        cat_id = next((c["id"] for c in self.categories if c["nom"]==self.cat_var.get()), None)
        if self.piece:
            db.modifier_piece(self.piece["id"], nom, cat_id, qte, qmin, pa, pv,
                              self.e_ref.get().strip(), self.e_unite.get().strip() or "unité")
        else:
            db.ajouter_piece(nom, cat_id, qte, qmin, pa, pv,
                             self.e_ref.get().strip(), self.e_unite.get().strip() or "unité")
        if self.on_save: self.on_save()
        self.destroy()


# ─────────────────────────────── ONGLET STOCK ───────────────────────────────
class StockTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self.app = app; self._build(); self.refresh()

    def _build(self):
        _make_tree_style()
        tb = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8, height=56)
        tb.pack(fill="x", padx=12, pady=(12,6)); tb.pack_propagate(False)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ctk.CTkEntry(tb, textvariable=self.search_var, placeholder_text="🔍  Rechercher…",
                     height=36, width=300).pack(side="left", padx=12, pady=10)
        self.categories = db.get_categories()
        cat_names = ["Toutes catégories"] + [c["nom"] for c in self.categories]
        self.cat_filter = ctk.StringVar(value="Toutes catégories")
        self.cat_filter.trace_add("write", lambda *_: self.refresh())
        ctk.CTkOptionMenu(tb, variable=self.cat_filter, values=cat_names,
                          width=180, height=36).pack(side="left", padx=4, pady=10)
        RedButton(tb, text="➕  Ajouter", command=self._add_piece,
                  width=120, height=36).pack(side="right", padx=12, pady=10)

        tf = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8)
        tf.pack(fill="both", expand=True, padx=12, pady=6)
        cols = ("ref","nom","categorie","quantite","qmin","prix_achat","prix_vente","unite")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", selectmode="browse")
        for col, text, w in [
            ("ref","Référence",100),("nom","Désignation",220),("categorie","Catégorie",130),
            ("quantite","Qté",60),("qmin","Qté Min",65),("prix_achat","P. Achat",100),
            ("prix_vente","P. Vente",100),("unite","Unité",70)]:
            self.tree.heading(col, text=text); self.tree.column(col, width=w, anchor="center")
        self.tree.column("nom", anchor="w")
        self.tree.tag_configure("alerte", background="#FDECEA", foreground=COLOR_RED)
        self.tree.tag_configure("normal", background=COLOR_WHITE)
        self.tree.tag_configure("zebra",  background="#FAFAFA")
        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", lambda e: self._edit_piece())

        af = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8, height=52)
        af.pack(fill="x", padx=12, pady=6); af.pack_propagate(False)
        GrayButton(af, text="✏️  Modifier",  command=self._edit_piece,   width=120, height=36).pack(side="left", padx=12, pady=8)
        GrayButton(af, text="🗑️  Supprimer", command=self._delete_piece, width=120, height=36).pack(side="left", padx=4, pady=8)
        self.count_label = ctk.CTkLabel(af, text="", font=FONT_SMALL, text_color=COLOR_GRAY)
        self.count_label.pack(side="right", padx=16)

    def refresh(self):
        self.categories = db.get_categories()
        cat_nom = self.cat_filter.get()
        cat_id  = None if cat_nom == "Toutes catégories" else next(
            (c["id"] for c in self.categories if c["nom"]==cat_nom), None)
        pieces = db.get_pieces(search=self.search_var.get(), categorie_id=cat_id)
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(pieces):
            tag = "alerte" if p["quantite"] <= p["qmin"] else ("normal" if i%2==0 else "zebra")
            self.tree.insert("","end", iid=str(p["id"]), tags=(tag,), values=(
                p.get("reference","") or "", p["nom"], p.get("categorie_nom","") or "",
                p["quantite"], p["qmin"], f'{p["prix_achat"]:.2f}',
                f'{p["prix_vente"]:.2f}', p.get("unite","unité") or "unité"))
        self.count_label.configure(text=f"{len(pieces)} pièce(s)")
        if hasattr(self.app, 'alertes_tab'): self.app.check_alerts()

    def _sel(self): sel=self.tree.selection(); return int(sel[0]) if sel else None

    def _add_piece(self):
        PieceDialog(self, db.get_categories(), on_save=self.refresh)

    def _edit_piece(self):
        if not (pid := self._sel()):
            messagebox.showinfo("Info","Sélectionnez une pièce.", parent=self); return
        PieceDialog(self, db.get_categories(), piece=db.get_piece_by_id(pid), on_save=self.refresh)

    def _delete_piece(self):
        if not (pid := self._sel()):
            messagebox.showinfo("Info","Sélectionnez une pièce.", parent=self); return
        p = db.get_piece_by_id(pid)
        if messagebox.askyesno("Confirmer", f"Supprimer « {p['nom']} » ?", parent=self):
            db.supprimer_piece(pid); self.refresh()


# ─────────────────────────────── ONGLET FACTURATION v3 ───────────────────────────────
class FactureTab(ctk.CTkFrame):
    """
    Catalogue à gauche  |  Facture en cours à droite
    - Clic sur pièce → sélection, prix modifiable, ajouter au panier
    - Suppr sur ligne → supprime la ligne
    - Double-clic sur ligne → modifier qté/prix
    - Remise en TND (déduit du total calculé)
    - Total à payer affiché en vert
    """
    def __init__(self, master, app, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self.app = app
        self.current_facture_id  = None
        self.current_facture_num = None
        self._selected_piece     = None
        self._piece_cache        = []   # liste pièces affichées dans catalogue
        self._build()
        self._load_catalogue()

    # ── Construction UI ──
    def _build(self):
        _make_tree_style()
        body = ctk.CTkFrame(self, fg_color=COLOR_BG)
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # ─ Colonne gauche : catalogue ─
        left = ctk.CTkFrame(body, fg_color=COLOR_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self._build_catalogue(left)

        # ─ Colonne droite : facture ─
        right = ctk.CTkFrame(body, fg_color=COLOR_BG, width=620)
        right.pack(side="left", fill="both", expand=True)
        right.pack_propagate(False)
        self._build_facture(right)

    def _build_catalogue(self, parent):
        # Titre
        ctk.CTkLabel(parent, text="Catalogue de pièces", font=FONT_HEADER,
                     text_color=COLOR_RED).pack(pady=(0, 6))

        # Recherche + filtre catégorie
        self.cat_search_var = ctk.StringVar()
        self.cat_search_var.trace_add("write", lambda *_: self._load_catalogue())
        ctk.CTkEntry(parent, textvariable=self.cat_search_var,
                     placeholder_text="Rechercher…", height=34).pack(fill="x", pady=(0, 4))

        self.categories = db.get_categories()
        cat_names = ["Toutes"] + [c["nom"] for c in self.categories]
        self.cat_var = ctk.StringVar(value="Toutes")
        self.cat_var.trace_add("write", lambda *_: self._load_catalogue())
        ctk.CTkOptionMenu(parent, variable=self.cat_var, values=cat_names,
                          height=30).pack(fill="x", pady=(0, 6))

        # Tableau catalogue
        cat_frame = ctk.CTkFrame(parent, fg_color=COLOR_WHITE, corner_radius=8)
        cat_frame.pack(fill="both", expand=True)

        cols = ("nom", "ref", "stock", "prix")
        self.cat_tree = ttk.Treeview(cat_frame, columns=cols, show="headings", selectmode="browse")
        for col, text, w, anchor in [
            ("nom","Nom",200,"w"), ("ref","Réf",80,"center"),
            ("stock","Qté dispo",80,"center"), ("prix","Prix vente",90,"center")]:
            self.cat_tree.heading(col, text=text)
            self.cat_tree.column(col, width=w, anchor=anchor)
        self.cat_tree.tag_configure("rupture",  background="#FDECEA", foreground=COLOR_RED)
        self.cat_tree.tag_configure("bas",      background="#FEF9E7", foreground=COLOR_WARN)
        self.cat_tree.tag_configure("normal",   background=COLOR_WHITE)
        self.cat_tree.tag_configure("zebra",    background="#FAFAFA")
        vsb = ttk.Scrollbar(cat_frame, orient="vertical", command=self.cat_tree.yview)
        self.cat_tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y"); self.cat_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.cat_tree.bind("<<TreeviewSelect>>", self._on_cat_select)
        self.cat_tree.bind("<Double-1>", lambda e: self._add_to_facture())

        ctk.CTkLabel(parent, text="— Clic simple pour sélectionner",
                     font=FONT_SMALL, text_color=COLOR_GRAY).pack(pady=(4, 0))

        # Zone sélection + ajout
        sel_frame = ctk.CTkFrame(parent, fg_color=COLOR_LGRAY, corner_radius=8)
        sel_frame.pack(fill="x", pady=(8, 0))

        self.sel_info = ctk.CTkLabel(sel_frame, text="", font=FONT_SMALL,
                                     text_color=COLOR_GREEN, anchor="center")
        self.sel_info.pack(fill="x", padx=10, pady=(8, 4))

        row = ctk.CTkFrame(sel_frame, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(row, text="Qté :", font=FONT_BOLD, width=40).pack(side="left")
        self.e_qty = ctk.CTkEntry(row, width=65, height=34)
        self.e_qty.insert(0, "1"); self.e_qty.pack(side="left", padx=(4, 10))

        ctk.CTkLabel(row, text="Prix unit. (modifiable) :", font=FONT_BOLD).pack(side="left")
        self.e_prix_unit = ctk.CTkEntry(row, width=90, height=34)
        self.e_prix_unit.pack(side="left", padx=(4, 10))

        RedButton(row, text="+ Ajouter au panier", command=self._add_to_facture,
                  height=34).pack(side="left")

    def _build_facture(self, parent):
        # Titre + client
        ctk.CTkLabel(parent, text="Facture en cours", font=FONT_HEADER,
                     text_color=COLOR_RED).pack(pady=(0, 6))

        client_row = ctk.CTkFrame(parent, fg_color="transparent")
        client_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(client_row, text="Nom du client :", font=FONT_BOLD,
                     width=110).pack(side="left")
        self.e_client = ctk.CTkEntry(client_row, placeholder_text="Nom client…", height=32)
        self.e_client.pack(side="left", fill="x", expand=True, padx=(6, 6))
        self.e_tel = ctk.CTkEntry(client_row, placeholder_text="Téléphone", height=32, width=130)
        self.e_tel.pack(side="left")

        # Tableau lignes facture
        lines_frame = ctk.CTkFrame(parent, fg_color=COLOR_WHITE, corner_radius=8)
        lines_frame.pack(fill="both", expand=True)

        cols = ("nom","ref","qty","pu","total")
        self.lines_tree = ttk.Treeview(lines_frame, columns=cols, show="headings")
        for col, text, w, anchor in [
            ("nom","Nom",200,"w"), ("ref","Réf",80,"center"),
            ("qty","Qté",55,"center"), ("pu","Prix unit.",105,"center"),
            ("total","Total ligne",105,"center")]:
            self.lines_tree.heading(col, text=text)
            self.lines_tree.column(col, width=w, anchor=anchor)

        vsb2 = ttk.Scrollbar(lines_frame, orient="vertical", command=self.lines_tree.yview)
        self.lines_tree.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self.lines_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.lines_tree.bind("<Double-1>",  self._edit_ligne)
        self.lines_tree.bind("<Delete>",    self._del_ligne_key)

        ctk.CTkLabel(parent, text="Double-clic pour modifier   Suppr pour effacer",
                     font=FONT_SMALL, text_color=COLOR_GRAY).pack(pady=(2, 4))

        # Barre totaux
        totaux_frame = ctk.CTkFrame(parent, fg_color="transparent")
        totaux_frame.pack(fill="x", pady=(0, 6))

        self.total_calcule_label = ctk.CTkLabel(totaux_frame, text="Total calculé : 0.00 TND",
                                                font=FONT_BOLD, text_color=COLOR_RED)
        self.total_calcule_label.pack(side="left", padx=(6, 12))

        ctk.CTkLabel(totaux_frame, text="Remise :", font=FONT_BOLD).pack(side="left")
        self.e_remise = ctk.CTkEntry(totaux_frame, width=80, height=30)
        self.e_remise.insert(0, "0"); self.e_remise.pack(side="left", padx=(4, 4))
        ctk.CTkLabel(totaux_frame, text="TND", font=FONT_NORMAL,
                     text_color=COLOR_GRAY).pack(side="left")
        self.e_remise.bind("<KeyRelease>", lambda e: self._refresh_totaux())

        self.total_payer_label = ctk.CTkLabel(parent, text="Total à payer : 0.00 TND",
                                              font=("Helvetica", 14, "bold"), text_color=COLOR_GREEN)
        self.total_payer_label.pack(pady=(0, 8))

        # Boutons bas
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x")
        GrayButton(btn_row, text="🗑️  Vider", command=self._cancel_facture,
                   width=120, height=36).pack(side="left", padx=(0, 8))
        RedButton(btn_row, text="🖨️  Créer & PDF", command=self._finalize,
                  width=160, height=36).pack(side="right")

    # ── Catalogue ──
    def _load_catalogue(self):
        q      = self.cat_search_var.get()
        cat_n  = self.cat_var.get()
        cat_id = None if cat_n == "Toutes" else next(
            (c["id"] for c in self.categories if c["nom"]==cat_n), None)
        self._piece_cache = db.get_pieces(search=q, categorie_id=cat_id)
        self.cat_tree.delete(*self.cat_tree.get_children())
        for i, p in enumerate(self._piece_cache):
            if p["quantite"] == 0:   tag = "rupture"
            elif p["quantite"] <= p["qmin"]: tag = "bas"
            elif i % 2 == 1:         tag = "zebra"
            else:                    tag = "normal"
            self.cat_tree.insert("","end", iid=str(p["id"]), tags=(tag,), values=(
                p["nom"], p.get("reference","") or "",
                p["quantite"], f'{p["prix_vente"]:.2f}'))

    def _on_cat_select(self, event=None):
        sel = self.cat_tree.selection()
        if not sel: return
        p = next((x for x in self._piece_cache if str(x["id"])==sel[0]), None)
        if not p: return
        self._selected_piece = p
        self.sel_info.configure(text=f"✓ {p['nom']} — Stock: {p['quantite']}")
        # Remplir prix unitaire avec prix vente par défaut
        self.e_prix_unit.delete(0, "end")
        self.e_prix_unit.insert(0, f"{p['prix_vente']:.2f}")
        self.e_qty.delete(0, "end"); self.e_qty.insert(0, "1")
        self.e_qty.focus_set(); self.e_qty.select_range(0, "end")

    # ── Facture ──
    def _ensure_facture(self):
        """Crée une facture ouverte si aucune n'existe."""
        if self.current_facture_id:
            return True
        client = self.e_client.get().strip() or "Client"
        tel    = self.e_tel.get().strip()
        fid, fnum = db.creer_facture(client, tel)
        self.current_facture_id  = fid
        self.current_facture_num = fnum
        return True

    def _add_to_facture(self):
        if not self._selected_piece:
            messagebox.showwarning("Attention","Sélectionnez d'abord une pièce.", parent=self); return
        try:
            qty  = int(self.e_qty.get() or 1)
            prix = float(self.e_prix_unit.get() or self._selected_piece["prix_vente"])
            if qty <= 0 or prix < 0: raise ValueError
        except ValueError:
            messagebox.showerror("Erreur","Quantité ou prix invalide.", parent=self); return

        self._ensure_facture()
        # On passe par la fonction DB mais on override le prix si différent
        ok, msg = db.ajouter_ligne_facture(self.current_facture_id, self._selected_piece["id"], qty)
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self); return
        # Si le prix a été modifié, mettre à jour la ligne
        lignes = db.get_lignes_facture(self.current_facture_id)
        ligne  = next((l for l in lignes if l["piece_id"]==self._selected_piece["id"]), None)
        if ligne and abs(prix - ligne["prix_unitaire"]) > 0.001:
            db.modifier_ligne_facture(ligne["id"], ligne["quantite"], prix)
        self._post_add_refresh()

    def _post_add_refresh(self):
        """Rafraîchit catalogue, lignes et stock après ajout d'un article."""
        self._refresh_lines()
        self._load_catalogue()
        self.app.stock_tab.refresh()
        self.e_qty.delete(0, "end")
        self.e_qty.insert(0, "1")

    def _edit_ligne(self, event=None):
        sel = self.lines_tree.selection()
        if not sel: return
        lid = int(sel[0])
        conn = db.get_connection()
        c    = conn.cursor()
        c.execute("SELECT * FROM facture_lignes WHERE id=?", (lid,))
        ligne = dict(c.fetchone()); conn.close()

        dlg = ctk.CTkToplevel(self)
        dlg.title("Modifier la ligne"); dlg.geometry("360x240")
        dlg.resizable(False, False); dlg.grab_set()
        dlg.configure(fg_color=COLOR_BG)

        hdr = ctk.CTkFrame(dlg, fg_color=COLOR_RED, corner_radius=0, height=44)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f"✏️  {ligne['piece_nom']}",
                     font=FONT_HEADER, text_color=COLOR_WHITE).pack(side="left", padx=14, pady=10)

        body = ctk.CTkFrame(dlg, fg_color=COLOR_BG); body.pack(fill="both", expand=True, padx=20, pady=14)

        def field(lbl, val):
            r = ctk.CTkFrame(body, fg_color="transparent"); r.pack(fill="x", pady=5)
            ctk.CTkLabel(r, text=lbl, font=FONT_BOLD, width=130, anchor="w").pack(side="left")
            e = ctk.CTkEntry(r, width=140, height=34); e.insert(0, str(val)); e.pack(side="left"); return e

        e_q = field("Quantité :", ligne["quantite"])
        e_p = field("Prix unitaire :", f'{ligne["prix_unitaire"]:.2f}')

        def save():
            try:
                q = int(e_q.get()); p = float(e_p.get())
                if q <= 0 or p < 0: raise ValueError
            except ValueError:
                messagebox.showerror("Erreur","Valeurs invalides.", parent=dlg); return
            ok, msg = db.modifier_ligne_facture(lid, q, p)
            if not ok: messagebox.showerror("Erreur", msg, parent=dlg); return
            self._refresh_lines(); self._load_catalogue(); self.app.stock_tab.refresh(); dlg.destroy()

        bf = ctk.CTkFrame(dlg, fg_color=COLOR_WHITE, corner_radius=0)
        bf.pack(fill="x", side="bottom")
        GrayButton(bf, text="Annuler", command=dlg.destroy, width=110).pack(side="right", padx=(5,14), pady=10)
        RedButton(bf, text="💾  Enregistrer", command=save, width=150).pack(side="right", padx=5, pady=10)

    def _del_ligne_key(self, event=None):
        sel = self.lines_tree.selection()
        if not sel: return
        db.supprimer_ligne_facture(int(sel[0]))
        self._post_add_refresh()

    def _refresh_lines(self):
        self.lines_tree.delete(*self.lines_tree.get_children())
        if not self.current_facture_id:
            self._refresh_totaux(0); return
        lignes = db.get_lignes_facture(self.current_facture_id)
        for l in lignes:
            self.lines_tree.insert("","end", iid=str(l["id"]), values=(
                l["piece_nom"], l.get("piece_ref","") or "",
                l["quantite"], f'{l["prix_unitaire"]:.2f}', f'{l["total_ligne"]:.2f}'))
        facture = db.get_facture(self.current_facture_id)
        self._refresh_totaux(facture["total_ht"] if facture else 0)

    def _refresh_totaux(self, total_ht=None):
        if total_ht is None and self.current_facture_id:
            f = db.get_facture(self.current_facture_id)
            total_ht = f["total_ht"] if f else 0
        total_ht = total_ht or 0
        try:    remise = float(self.e_remise.get() or 0)
        except: remise = 0
        total_payer = max(0, total_ht - remise)
        self.total_calcule_label.configure(text=f"Total calculé : {total_ht:,.2f} TND")
        self.total_payer_label.configure(text=f"Total à payer : {total_payer:,.2f} TND")

    def _reset_facture_courante(self):
        self.current_facture_id  = None
        self.current_facture_num = None
        self._selected_piece     = None
        self.sel_info.configure(text="")
        self.e_remise.delete(0,"end"); self.e_remise.insert(0,"0")

    def _post_facture_refresh(self, rapport=False):
        self._refresh_lines(); self._load_catalogue(); self.app.stock_tab.refresh()
        if hasattr(self.app, 'historique_tab'): self.app.historique_tab.refresh()
        if rapport and hasattr(self.app, 'rapport_tab'): self.app.rapport_tab.refresh()

    def _cancel_facture(self):
        if not self.current_facture_id: return
        if messagebox.askyesno("Confirmer","Vider la facture et restaurer le stock ?", parent=self):
            db.annuler_facture(self.current_facture_id)
            self._reset_facture_courante()
            self._post_facture_refresh()

    def _finalize(self):
        if not self.current_facture_id:
            messagebox.showwarning("Attention","Ajoutez d'abord des articles.", parent=self); return
        lignes = db.get_lignes_facture(self.current_facture_id)
        if not lignes:
            messagebox.showwarning("Attention","La facture est vide.", parent=self); return
        try:    remise_TND = float(self.e_remise.get() or 0)
        except: remise_TND = 0
        # Appliquer remise comme remise %
        facture  = db.get_facture(self.current_facture_id)
        total_ht = facture["total_ht"]
        remise_pct = round((remise_TND / total_ht * 100), 4) if total_ht > 0 else 0
        db.finaliser_facture(self.current_facture_id, remise_pct)
        facture = db.get_facture(self.current_facture_id)
        try:
            path = generer_facture_pdf(facture, lignes)
            messagebox.showinfo("✅  Facture créée", f"PDF enregistré :\n{path}", parent=self)
            with contextlib.suppress(Exception):
                if sys.platform.startswith("win"):  os.startfile(path)
                elif sys.platform == "darwin":      subprocess.Popen(["open", path])
                else:                               subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Erreur PDF", str(e), parent=self)
        self._reset_facture_courante()
        self._post_facture_refresh(rapport=True)

    def reload_catalogue(self):
        """Appelé depuis l'extérieur pour rafraîchir le catalogue."""
        self.categories = db.get_categories()
        self._load_catalogue()


# ─────────────────────────────── ONGLET HISTORIQUE ───────────────────────────────
class HistoriqueTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self._build(); self.refresh()

    def _build(self):
        _make_tree_style()
        hdr = _make_red_header(self, "📂  Historique des Factures")
        GrayButton(hdr, text="🔄  Actualiser", command=self.refresh,
                   width=130, height=34).pack(side="right", padx=12, pady=8)

        # Filtres
        flt = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8, height=50)
        flt.pack(fill="x", padx=12, pady=(0,6)); flt.pack_propagate(False)
        ctk.CTkLabel(flt, text="Filtrer :", font=FONT_BOLD).pack(side="left", padx=12, pady=12)
        self.statut_var = ctk.StringVar(value="Toutes")
        self.statut_var.trace_add("write", lambda *_: self.refresh())
        ctk.CTkOptionMenu(flt, variable=self.statut_var,
                          values=["Toutes","finalisée","ouverte","annulée"],
                          width=140, height=32).pack(side="left", padx=4, pady=10)
        self.search_hist = ctk.StringVar()
        self.search_hist.trace_add("write", lambda *_: self.refresh())
        ctk.CTkEntry(flt, textvariable=self.search_hist,
                     placeholder_text="Rechercher client / N°…",
                     height=32, width=220).pack(side="left", padx=8, pady=10)

        # Tableau principal
        card = SectionCard(self)
        card.pack(fill="both", expand=True, padx=12, pady=(0,6))

        cols = ("num","date","client","tel","ht","remise","ttc","statut")
        self.tree = ttk.Treeview(card, columns=cols, show="headings")
        for col, text, w, anchor in [
            ("num",    "N° Facture",  130, "center"),
            ("date",   "Date",        120, "center"),
            ("client", "Client",      140, "w"),
            ("tel",    "Téléphone",    110, "center"),
            ("ht",     "Total HT",     90, "center"),
            ("remise", "Remise %",     70, "center"),
            ("ttc",    "Total TTC",    100, "center"),
            ("statut", "Statut",       80, "center")]:
            self.tree.heading(col, text=text); self.tree.column(col, width=w, anchor=anchor)
        self.tree.column("client", anchor="w")
        self.tree.tag_configure("finalisée", foreground=COLOR_GREEN)
        self.tree.tag_configure("annulée",   foreground=COLOR_GRAY)
        self.tree.tag_configure("ouverte",   foreground=COLOR_WARN)
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0,8), pady=8)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.bind("<Double-1>", self._voir_pdf)

        # Stats résumé bas
        self.resume_label = ctk.CTkLabel(self, text="", font=FONT_SMALL, text_color=COLOR_GRAY)
        self.resume_label.pack(pady=4)
        ctk.CTkLabel(self, text="Double-clic sur une facture finalisée pour voir le PDF",
                     font=FONT_SMALL, text_color=COLOR_GRAY).pack(pady=(0,6))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        factures = db.get_historique_factures(200)
        q       = self.search_hist.get().lower()
        statut  = self.statut_var.get()
        filtered = []
        for f in factures:
            if statut != "Toutes" and f["statut"] != statut: continue
            if q and q not in f["numero"].lower() and q not in f["client_nom"].lower(): continue
            filtered.append(f)

        total_ttc_sum = 0
        for f in filtered:
            try:    d = datetime.fromisoformat(f["date_facture"]).strftime("%d/%m/%Y %H:%M")
            except: d = f["date_facture"]
            self.tree.insert("","end", iid=str(f["id"]), tags=(f["statut"],), values=(
                f["numero"], d, f["client_nom"], f.get("client_tel","") or "",
                f'{f["total_ht"]:.2f}', f'{f.get("remise",0):.1f}%',
                f'{f["total_ttc"]:.2f}', f["statut"]))
            if f["statut"] == "finalisée": total_ttc_sum += f["total_ttc"]
        self.resume_label.configure(
            text=f"{len(filtered)} facture(s) affichée(s)   |   Total TTC facturé : {total_ttc_sum:,.2f} TND")

    def _voir_pdf(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        fid = int(sel[0])
        facture = db.get_facture(fid)
        lignes  = db.get_lignes_facture(fid)
        if not lignes:
            messagebox.showinfo("Vide","Cette facture ne contient aucun article.", parent=self); return
        try:
            path = generer_facture_pdf(facture, lignes)
            with contextlib.suppress(Exception):
                if sys.platform.startswith("win"):  os.startfile(path)
                elif sys.platform == "darwin":      subprocess.Popen(["open", path])
                else:                               subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)


# ─────────────────────────────── ONGLET RAPPORT ───────────────────────────────
class RapportTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self._current_date = datetime.now().strftime('%Y-%m-%d')
        self._build(); self.refresh()

    def _build(self):
        _make_tree_style()
        # Barre navigation date
        nav = ctk.CTkFrame(self, fg_color=COLOR_RED, corner_radius=8, height=52)
        nav.pack(fill="x", padx=12, pady=(12,8)); nav.pack_propagate(False)
        GrayButton(nav, text="◀  Jour précédent", command=self._prev_day,
                   width=150, height=36).pack(side="left", padx=12, pady=8)
        self.date_label = ctk.CTkLabel(nav, text="", font=("Helvetica",14,"bold"),
                                       text_color=COLOR_WHITE)
        self.date_label.pack(side="left", expand=True)
        RedButton(nav, text="📅  Aujourd'hui", command=self._today,
                  fg_color="#A93226", width=130, height=36).pack(side="right", padx=4, pady=8)
        GrayButton(nav, text="Jour suivant  ▶", command=self._next_day,
                   width=150, height=36).pack(side="right", padx=4, pady=8)

        body = ctk.CTkFrame(self, fg_color=COLOR_BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0,8))

        # Liste jours (gauche)
        left = ctk.CTkFrame(body, fg_color=COLOR_BG, width=220)
        left.pack(side="left", fill="y", padx=(0,8)); left.pack_propagate(False)
        ctk.CTkLabel(left, text="📅  Jours avec ventes", font=FONT_BOLD,
                     text_color=COLOR_DARK).pack(anchor="w", pady=(4,6))
        self.days_list = tk.Listbox(left, font=("Helvetica",10), selectmode="single", bd=0,
                                    bg=COLOR_WHITE, fg=COLOR_DARK, selectbackground="#FDECEA",
                                    selectforeground=COLOR_RED, relief="flat", highlightthickness=0)
        self.days_list.pack(fill="both", expand=True)
        self.days_list.bind("<<ListboxSelect>>", self._on_day_select)
        self._jours_data = []

        # Détail (droite)
        right = ctk.CTkFrame(body, fg_color=COLOR_BG)
        right.pack(side="left", fill="both", expand=True)

        # ── 5 cartes stats ──
        cf = ctk.CTkFrame(right, fg_color=COLOR_BG)
        cf.pack(fill="x", pady=(0,8)); cf.columnconfigure((0,1,2,3,4), weight=1)

        def stat_card(col, title, color):
            f = ctk.CTkFrame(cf, fg_color=color, corner_radius=10)
            f.grid(row=0, column=col, padx=3, pady=2, sticky="ew")
            val = ctk.CTkLabel(f, text="—", font=("Helvetica",18,"bold"), text_color=COLOR_WHITE)
            val.pack(pady=(10,2), padx=8)
            ctk.CTkLabel(f, text=title, font=("Helvetica",8), text_color="#FFCCCC").pack(pady=(0,10), padx=8)
            return val

        self.v_ca       = stat_card(0, "Chiffre d'affaires", COLOR_RED)
        self.v_cout     = stat_card(1, "Coût total achat",   "#7F8C8D")
        self.v_profit   = stat_card(2, "Profit net",         COLOR_GREEN)
        self.v_factures = stat_card(3, "Nb factures",        COLOR_BLUE)
        self.v_articles = stat_card(4, "Pièces vendues",     COLOR_WARN)

        # Tableau pièces vendues
        pv_card = SectionCard(right, title="📦  Pièces vendues ce jour")
        pv_card.pack(fill="both", expand=True, pady=(0,8))
        pv_f = ctk.CTkFrame(pv_card, fg_color=COLOR_WHITE, corner_radius=6)
        pv_f.pack(fill="both", expand=True, padx=12, pady=(0,12))
        cols_pv = ("nom","ref","qte","px_vente","px_achat","total_vente","profit")
        self.pv_tree = ttk.Treeview(pv_f, columns=cols_pv, show="headings")
        for col, text, w in [
            ("nom","Désignation",200),("ref","Référence",90),("qte","Qté vendue",80),
            ("px_vente","Prix vente",95),("px_achat","Prix achat",95),
            ("total_vente","Total vente",105),("profit","Profit",100)]:
            self.pv_tree.heading(col, text=text); self.pv_tree.column(col, width=w, anchor="center")
        self.pv_tree.column("nom", anchor="w")
        self.pv_tree.tag_configure("profit_pos", foreground=COLOR_GREEN)
        self.pv_tree.tag_configure("profit_neg", foreground=COLOR_RED)
        self.pv_tree.tag_configure("zebra",      background="#FAFAFA")
        vsb_pv = ttk.Scrollbar(pv_f, orient="vertical", command=self.pv_tree.yview)
        self.pv_tree.configure(yscrollcommand=vsb_pv.set)
        vsb_pv.pack(side="right", fill="y", pady=6); self.pv_tree.pack(fill="both", expand=True, padx=6, pady=6)

        # Tableau factures du jour
        fac_card = SectionCard(right, title="🧾  Factures du jour")
        fac_card.pack(fill="x", pady=(0,4))
        fac_f = ctk.CTkFrame(fac_card, fg_color=COLOR_WHITE, corner_radius=6)
        fac_f.pack(fill="x", padx=12, pady=(0,12))
        cols_f = ("num","client","tel","ht","remise","ttc")
        self.fac_tree = ttk.Treeview(fac_f, columns=cols_f, show="headings", height=4)
        for col, text, w in [("num","N° Facture",130),("client","Client",130),("tel","Téléphone",100),
                              ("ht","Total HT",90),("remise","Remise %",70),("ttc","Total TTC",100)]:
            self.fac_tree.heading(col, text=text); self.fac_tree.column(col, width=w, anchor="center")
        self.fac_tree.column("client", anchor="w")
        vsb_f = ttk.Scrollbar(fac_f, orient="vertical", command=self.fac_tree.yview)
        self.fac_tree.configure(yscrollcommand=vsb_f.set)
        vsb_f.pack(side="right", fill="y", pady=6); self.fac_tree.pack(fill="x", padx=6, pady=6)

    def _prev_day(self):
        self._current_date = (datetime.strptime(self._current_date,'%Y-%m-%d') - timedelta(days=1)).strftime('%Y-%m-%d')
        self._load_detail()

    def _next_day(self):
        self._current_date = (datetime.strptime(self._current_date,'%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
        self._load_detail()

    def _today(self):
        self._current_date = datetime.now().strftime('%Y-%m-%d'); self._load_detail()

    def _on_day_select(self, event=None):
        if sel := self.days_list.curselection():
            self._current_date = self._jours_data[sel[0]]["jour"]
            self._load_detail()

    def refresh(self):
        self._jours_data = db.get_jours_avec_ventes(60)
        self.days_list.delete(0,"end")
        for j in self._jours_data:
            try:  d = datetime.strptime(j["jour"],'%Y-%m-%d').strftime('%d/%m/%Y')
            except: d = j["jour"]
            self.days_list.insert("end", f"  {d}   {j['ca_jour']:,.0f}")
        for i, j in enumerate(self._jours_data):
            if j["jour"] == self._current_date:
                self.days_list.selection_clear(0,"end"); self.days_list.selection_set(i)
                self.days_list.see(i); break
        self._load_detail()

    def _load_detail(self):
        rapport = db.get_rapport_journalier(self._current_date)
        try:    d_fmt = datetime.strptime(self._current_date,'%Y-%m-%d').strftime('%A %d %B %Y').capitalize()
        except: d_fmt = self._current_date
        suffix = "  —  Aujourd'hui" if self._current_date == datetime.now().strftime('%Y-%m-%d') else ""
        self.date_label.configure(text=f"📅  {d_fmt}{suffix}")

        t   = rapport["totaux"]
        pv  = rapport["pieces_vendues"]
        nb_articles   = sum(x["qte_vendue"] for x in pv)
        cout_total    = sum(x["total_achat"] for x in pv)

        self.v_ca.configure(       text=f'{t["total_ttc"]:,.0f} TND')
        self.v_cout.configure(     text=f'{cout_total:,.0f} TND')
        self.v_profit.configure(   text=f'{rapport["profit_total"]:,.0f} TND')
        self.v_factures.configure( text=str(t["nb_factures"]))
        self.v_articles.configure( text=str(nb_articles))

        self.pv_tree.delete(*self.pv_tree.get_children())
        for i, p in enumerate(pv):
            tag = "zebra" if i%2==1 else ("profit_pos" if p["profit_ligne"]>=0 else "profit_neg")
            self.pv_tree.insert("","end", tags=(tag,), values=(
                p["piece_nom"], p.get("piece_ref","") or "", int(p["qte_vendue"]),
                f'{p["prix_vente"]:.2f}', f'{p["prix_achat"]:.2f}',
                f'{p["total_vente"]:.2f}', f'{p["profit_ligne"]:.2f}'))

        self.fac_tree.delete(*self.fac_tree.get_children())
        for f in rapport["factures"]:
            self.fac_tree.insert("","end", values=(
                f["numero"], f["client_nom"], f.get("client_tel","") or "",
                f'{f["total_ht"]:.2f}', f'{f.get("remise",0):.1f}%', f'{f["total_ttc"]:.2f}'))


# ─────────────────────────────── ONGLET ALERTES ───────────────────────────────
class AlertesTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self._build(); self.refresh()

    def _build(self):
        _make_tree_style()
        hdr = _make_red_header(self, "⚠️  Alertes de Stock Minimum")
        GrayButton(hdr, text="🔄 Actualiser", command=self.refresh,
                   width=120, height=34).pack(side="right", padx=12, pady=8)
        card = SectionCard(self)
        card.pack(fill="both", expand=True, padx=12, pady=6)
        cols = ("nom","ref","quantite","qmin","manquant","categorie")
        self.tree = ttk.Treeview(card, columns=cols, show="headings")
        for col, text, w in [("nom","Désignation",220),("ref","Référence",100),
                              ("quantite","Stock actuel",100),("qmin","Stock min",90),
                              ("manquant","À commander",100),("categorie","Catégorie",130)]:
            self.tree.heading(col, text=text); self.tree.column(col, width=w, anchor="center")
        self.tree.column("nom", anchor="w")
        self.tree.tag_configure("rouge",  background="#FDECEA", foreground=COLOR_RED)
        self.tree.tag_configure("orange", background="#FEF9E7", foreground=COLOR_WARN)
        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0,8), pady=8)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.info_label = ctk.CTkLabel(self, text="", font=FONT_NORMAL, text_color=COLOR_GRAY)
        self.info_label.pack(pady=6)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        alertes = db.get_pieces_stock_bas()
        for p in alertes:
            manquant = max(0, p["qmin"] - p["quantite"])
            tag = "rouge" if p["quantite"] == 0 else "orange"
            self.tree.insert("","end", tags=(tag,), values=(
                p["nom"], p.get("reference","") or "", p["quantite"], p["qmin"],
                manquant, p.get("categorie_nom","") or ""))
        if alertes:
            self.info_label.configure(text=f"⚠️  {len(alertes)} pièce(s) en dessous du stock minimum",
                                      text_color=COLOR_RED)
        else:
            self.info_label.configure(text="✅  Tous les stocks sont suffisants", text_color=COLOR_GREEN)


# ─────────────────────────────── ONGLET PARAMÈTRES ───────────────────────────────
class ParametresTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="⚙️  Paramètres", font=FONT_TITLE,
                     text_color=COLOR_DARK).pack(pady=(20,10), padx=20, anchor="w")
        # Backup
        bc = SectionCard(self, title="💾  Sauvegarde")
        bc.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(bc, text="Base de données stockée dans db/srg.db  —  Pointez vers Google Drive / OneDrive pour sync mobile.",
                     font=FONT_NORMAL, text_color=COLOR_GRAY, justify="left").pack(padx=15, pady=(4,8))
        row = ctk.CTkFrame(bc, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0,12))
        self.backup_path = ctk.CTkEntry(row, placeholder_text="Chemin du dossier…", height=34)
        self.backup_path.pack(side="left", fill="x", expand=True, padx=(0,8))
        self._load_backup_path()
        RedButton(row, text="📁  Choisir", command=self._choose_dir, width=120, height=34).pack(side="left", padx=(0,8))
        RedButton(row, text="💾  Sauvegarder", command=self._do_backup, width=150, height=34).pack(side="left")
        # Catégories
        cc = SectionCard(self, title="📂  Gestion des catégories")
        cc.pack(fill="x", padx=16, pady=8)
        row2 = ctk.CTkFrame(cc, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(0,12))
        self.e_cat = ctk.CTkEntry(row2, placeholder_text="Nom de la nouvelle catégorie", height=34)
        self.e_cat.pack(side="left", fill="x", expand=True, padx=(0,8))
        self.cat_type = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(row2, variable=self.cat_type, values=["auto","agri"],
                          width=100, height=34).pack(side="left", padx=(0,8))
        RedButton(row2, text="➕  Ajouter", command=self._add_cat, width=120, height=34).pack(side="left")
        # À propos
        ic = SectionCard(self, title="ℹ️  À propos")
        ic.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(ic, text="SRG — Société de Rechange et Garniture\nVersion 3.0  |  Python & CustomTkinter",
                     font=FONT_NORMAL, text_color=COLOR_GRAY, justify="left").pack(padx=15, pady=(4,15))

    def _load_backup_path(self):
        cfg = os.path.join(os.path.dirname(__file__), "backups", "config.txt")
        if os.path.exists(cfg):
            with open(cfg) as f: self.backup_path.insert(0, f.read().strip())

    def _choose_dir(self):
        from tkinter import filedialog
        if path := filedialog.askdirectory(title="Choisir le dossier de sauvegarde"):
            self.backup_path.delete(0,"end"); self.backup_path.insert(0, path)
            cfg = os.path.join(os.path.dirname(__file__), "backups", "config.txt")
            os.makedirs(os.path.dirname(cfg), exist_ok=True)
            with open(cfg,"w") as f: f.write(path)

    def _do_backup(self):
        try:
            dest = db.backup_db(self.backup_path.get().strip() or None)
            messagebox.showinfo("Succès", f"Sauvegarde créée:\n{dest}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _add_cat(self):
        if nom := self.e_cat.get().strip():
            db.ajouter_categorie(nom, self.cat_type.get())
            self.e_cat.delete(0,"end")
            messagebox.showinfo("OK", f"Catégorie « {nom} » ajoutée.")
        else:
            messagebox.showwarning("Attention","Entrez un nom de catégorie.")


# ─────────────────────────────── APPLICATION PRINCIPALE ───────────────────────────────
class SRGApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.title("SRG — Gestion de Stock et Facturation")
        self.geometry("1350x820"); self.minsize(1100, 680)
        self._alert_shown = False
        self._build_ui()
        self.after(1000, self.check_alerts)

    def _build_ui(self):
        self.configure(fg_color=COLOR_BG)
        # Barre titre
        tb = ctk.CTkFrame(self, fg_color=COLOR_RED, corner_radius=0, height=62)
        tb.pack(fill="x"); tb.pack_propagate(False)
        logo = ctk.CTkFrame(tb, fg_color="transparent")
        logo.pack(side="left", padx=18, pady=8)
        ctk.CTkLabel(logo, text="SRG", font=("Helvetica",26,"bold"),
                     text_color=COLOR_WHITE).pack(side="left")
        ctk.CTkLabel(logo, text=" Société de Rechange et Garniture",
                     font=("Helvetica",11), text_color="#FFCCCC").pack(side="left", pady=(8,0))
        sf = ctk.CTkFrame(tb, fg_color="transparent")
        sf.pack(side="right", padx=20, pady=8)
        self.lbl_pieces = ctk.CTkLabel(sf, text="", font=FONT_SMALL, text_color=COLOR_WHITE)
        self.lbl_pieces.pack(side="right", padx=10)
        self.lbl_alert  = ctk.CTkLabel(sf, text="", font=FONT_SMALL, text_color="#FFEEAA")
        self.lbl_alert.pack(side="right", padx=10)

        # Tabs
        self.tabview = ctk.CTkTabview(self, fg_color=COLOR_BG,
                                      segmented_button_fg_color=COLOR_LGRAY,
                                      segmented_button_selected_color=COLOR_RED,
                                      segmented_button_selected_hover_color=COLOR_RED_H,
                                      segmented_button_unselected_color=COLOR_LGRAY,
                                      segmented_button_unselected_hover_color="#D5D5D5",
                                      text_color=COLOR_DARK, text_color_disabled=COLOR_GRAY)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=(4,8))

        for tab in ["📦  Stock","🧾  Facturation","📂  Historique","📊  Rapport","⚠️  Alertes","⚙️  Paramètres"]:
            self.tabview.add(tab)

        self.stock_tab      = StockTab(self.tabview.tab("📦  Stock"), self)
        self.stock_tab.pack(fill="both", expand=True)
        self.facture_tab    = FactureTab(self.tabview.tab("🧾  Facturation"), self)
        self.facture_tab.pack(fill="both", expand=True)
        self.historique_tab = HistoriqueTab(self.tabview.tab("📂  Historique"))
        self.historique_tab.pack(fill="both", expand=True)
        self.rapport_tab    = RapportTab(self.tabview.tab("📊  Rapport"))
        self.rapport_tab.pack(fill="both", expand=True)
        self.alertes_tab    = AlertesTab(self.tabview.tab("⚠️  Alertes"))
        self.alertes_tab.pack(fill="both", expand=True)
        self.params_tab     = ParametresTab(self.tabview.tab("⚙️  Paramètres"))
        self.params_tab.pack(fill="both", expand=True)
        self._update_header_stats()

    def _update_header_stats(self):
        if not hasattr(self, 'lbl_pieces'): return
        stats = db.get_stats()
        self.lbl_pieces.configure(text=f"🗄️  {stats['total_pieces']} pièces")
        a = stats["alertes_stock"]
        self.lbl_alert.configure(text=f"⚠️  {a} alerte(s)" if a>0 else "✅  Stock OK")

    def check_alerts(self):
        alertes = db.get_pieces_stock_bas()
        self._update_header_stats()
        if hasattr(self, 'alertes_tab'): self.alertes_tab.refresh()
        if alertes and not self._alert_shown:
            self._alert_shown = True
            noms = "\n".join(f"• {p['nom']} (stock: {p['quantite']}, min: {p['qmin']})" for p in alertes[:5])
            msg  = f"{len(alertes)} pièce(s) à réapprovisionner:\n\n{noms}"
            if len(alertes) > 5: msg += f"\n... et {len(alertes)-5} autres"
            messagebox.showwarning("⚠️  Alerte Stock Minimum", msg)
        elif not alertes:
            self._alert_shown = False
        self.after(60000, self.check_alerts)


if __name__ == "__main__":
    app = SRGApp()
    app.mainloop()