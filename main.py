"""
SRG — Application de Gestion de Stock et Facturation
Société de Rechange et Garniture
Version 1.0
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import os
import subprocess
import sys
from datetime import datetime

import database as db
from pdf_generator import generer_facture_pdf

# ──────────────────────────────────────────────
#  THÈME GLOBAL
# ──────────────────────────────────────────────
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

COLOR_RED    = "#C0392B"
COLOR_RED_H  = "#A93226"
COLOR_WHITE  = "#FFFFFF"
COLOR_BG     = "#F5F5F5"
COLOR_DARK   = "#1A1A1A"
COLOR_GRAY   = "#777777"
COLOR_LGRAY  = "#E8E8E8"
COLOR_WARN   = "#090808"

FONT_TITLE  = ("Helvetica", 22, "bold")
FONT_HEADER = ("Helvetica", 13, "bold")
FONT_NORMAL = ("Helvetica", 11)
FONT_SMALL  = ("Helvetica", 9)
FONT_BOLD   = ("Helvetica", 11, "bold")


# ──────────────────────────────────────────────
#  WIDGETS RÉUTILISABLES
# ──────────────────────────────────────────────
class RedButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_RED)
        kwargs.setdefault("hover_color", COLOR_RED_H)
        kwargs.setdefault("text_color", COLOR_WHITE)
        kwargs.setdefault("corner_radius", 6)
        kwargs.setdefault("font", FONT_BOLD)
        super().__init__(master, **kwargs)


class GrayButton(ctk.CTkButton):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_LGRAY)
        kwargs.setdefault("hover_color", "#D0D0D0")
        kwargs.setdefault("text_color", COLOR_DARK)
        kwargs.setdefault("corner_radius", 6)
        kwargs.setdefault("font", FONT_NORMAL)
        super().__init__(master, **kwargs)


class SectionCard(ctk.CTkFrame):
    def __init__(self, master, title="", **kwargs):
        kwargs.setdefault("fg_color", COLOR_WHITE)
        kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **kwargs)
        if title:
            ctk.CTkLabel(self, text=title, font=FONT_HEADER,
                         text_color=COLOR_DARK).pack(anchor="w", padx=15, pady=(12, 5))


class StatCard(ctk.CTkFrame):
    def __init__(self, master, title, value, color=COLOR_RED, **kwargs):
        kwargs.setdefault("fg_color", color)
        kwargs.setdefault("corner_radius", 10)
        super().__init__(master, **kwargs)
        ctk.CTkLabel(self, text=value, font=("Helvetica", 26, "bold"),
                     text_color=COLOR_WHITE).pack(pady=(14, 2), padx=15)
        ctk.CTkLabel(self, text=title, font=FONT_SMALL,
                     text_color="#FFCCCC").pack(pady=(0, 12), padx=15)


# ──────────────────────────────────────────────
#  DIALOG AJOUT / MODIFICATION PIÈCE
# ──────────────────────────────────────────────
class PieceDialog(ctk.CTkToplevel):
    def __init__(self, master, categories, piece=None, on_save=None):
        super().__init__(master)
        self.title("Modifier pièce" if piece else "Nouvelle pièce")
        self.geometry("480x560")
        self.resizable(False, False)
        self.grab_set()
        self.categories = categories
        self.piece = piece
        self.on_save = on_save
        self._build()
        if piece:
            self._fill(piece)

    def _build(self):
        self.configure(fg_color=COLOR_BG)
        # Title bar
        header = ctk.CTkFrame(self, fg_color=COLOR_RED, corner_radius=0, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        title_txt = "✏️  Modifier la pièce" if self.piece else "➕  Nouvelle pièce"
        ctk.CTkLabel(header, text=title_txt, font=FONT_HEADER,
                     text_color=COLOR_WHITE).pack(side="left", padx=15, pady=12)

        form = ctk.CTkScrollableFrame(self, fg_color=COLOR_BG, corner_radius=0)
        form.pack(fill="both", expand=True, padx=20, pady=15)

        def row(label, widget_fn):
            ctk.CTkLabel(form, text=label, font=FONT_BOLD, text_color=COLOR_DARK,
                         anchor="w").pack(fill="x", pady=(8, 2))
            w = widget_fn(form)
            w.pack(fill="x")
            return w

        self.e_nom       = row("Désignation *", lambda p: ctk.CTkEntry(p, placeholder_text="ex: Roulement 6205", height=36))
        self.e_ref       = row("Référence", lambda p: ctk.CTkEntry(p, placeholder_text="ex: R-6205 (auto si vide)", height=36))

        # Catégorie
        ctk.CTkLabel(form, text="Catégorie *", font=FONT_BOLD, text_color=COLOR_DARK,
                     anchor="w").pack(fill="x", pady=(8, 2))
        self.cat_names = [c["nom"] for c in self.categories]
        self.cat_var = ctk.StringVar(value=self.cat_names[0] if self.cat_names else "")
        self.cat_menu = ctk.CTkOptionMenu(form, variable=self.cat_var, values=self.cat_names, height=36)
        self.cat_menu.pack(fill="x")

        # Grille numérique
        grid = ctk.CTkFrame(form, fg_color="transparent")
        grid.pack(fill="x", pady=(8, 0))
        grid.columnconfigure((0, 1), weight=1)

        def num_field(parent, label, placeholder, row_, col_):
            ctk.CTkLabel(parent, text=label, font=FONT_BOLD, text_color=COLOR_DARK,
                         anchor="w").grid(row=row_*2, column=col_, sticky="w", padx=(0 if col_==0 else 8, 0))
            e = ctk.CTkEntry(parent, placeholder_text=placeholder, height=36)
            e.grid(row=row_*2+1, column=col_, sticky="ew", padx=(0 if col_==0 else 8, 0), pady=(2, 8))
            return e

        self.e_qte      = num_field(grid, "Quantité *", "0", 0, 0)
        self.e_qmin     = num_field(grid, "Qté minimale *", "5", 0, 1)
        self.e_pachat   = num_field(grid, "Prix achat (TND) *", "0.00", 1, 0)
        self.e_pvente   = num_field(grid, "Prix vente (TND) *", "0.00", 1, 1)

        self.e_unite = row("Unité", lambda p: ctk.CTkEntry(p, placeholder_text="ex: unité, paire, litre", height=36))

        # Boutons
        btn_frame = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=0)
        btn_frame.pack(fill="x", side="bottom")
        GrayButton(btn_frame, text="Annuler", command=self.destroy,
                   width=120).pack(side="right", padx=(5, 15), pady=12)
        RedButton(btn_frame, text="💾  Enregistrer", command=self._save,
                  width=160).pack(side="right", padx=5, pady=12)

    def _fill(self, p):
        self.e_nom.insert(0, p["nom"])
        self.e_ref.insert(0, p.get("reference", "") or "")
        cat_nom = p.get("categorie_nom", "")
        if cat_nom in self.cat_names:
            self.cat_var.set(cat_nom)
        self.e_qte.insert(0, str(p["quantite"]))
        self.e_qmin.insert(0, str(p["qmin"]))
        self.e_pachat.insert(0, str(p["prix_achat"]))
        self.e_pvente.insert(0, str(p["prix_vente"]))
        self.e_unite.insert(0, p.get("unite", "unité") or "unité")

    def _save(self):
        nom = self.e_nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "La désignation est obligatoire.", parent=self)
            return
        try:
            qte   = int(self.e_qte.get() or 0)
            qmin  = int(self.e_qmin.get() or 0)
            pa    = float(self.e_pachat.get() or 0)
            pv    = float(self.e_pvente.get() or 0)
        except ValueError:
            messagebox.showerror("Erreur", "Veuillez entrer des valeurs numériques valides.", parent=self)
            return

        ref   = self.e_ref.get().strip()
        unite = self.e_unite.get().strip() or "unité"
        cat_nom = self.cat_var.get()
        cat_id = next((c["id"] for c in self.categories if c["nom"] == cat_nom), None)

        if self.piece:
            db.modifier_piece(self.piece["id"], nom, cat_id, qte, qmin, pa, pv, ref, unite)
        else:
            db.ajouter_piece(nom, cat_id, qte, qmin, pa, pv, ref, unite)

        if self.on_save:
            self.on_save()
        self.destroy()


# ──────────────────────────────────────────────
#  ONGLET STOCK
# ──────────────────────────────────────────────
class StockTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self.app = app
        self._build()
        self.refresh()

    def _build(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8, height=56)
        toolbar.pack(fill="x", padx=12, pady=(12, 6))
        toolbar.pack_propagate(False)

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        search = ctk.CTkEntry(toolbar, textvariable=self.search_var,
                              placeholder_text="🔍  Rechercher une pièce...",
                              height=36, width=300)
        search.pack(side="left", padx=12, pady=10)

        # Filtre catégorie
        self.categories = db.get_categories()
        cat_names = ["Toutes catégories"] + [c["nom"] for c in self.categories]
        self.cat_filter = ctk.StringVar(value="Toutes catégories")
        self.cat_filter.trace_add("write", lambda *_: self.refresh())
        ctk.CTkOptionMenu(toolbar, variable=self.cat_filter, values=cat_names,
                          width=180, height=36).pack(side="left", padx=4, pady=10)

        RedButton(toolbar, text="➕  Ajouter", command=self._add_piece,
                  width=120, height=36).pack(side="right", padx=12, pady=10)

        # Treeview
        tree_frame = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8)
        tree_frame.pack(fill="both", expand=True, padx=12, pady=6)

        cols = ("ref", "nom", "categorie", "quantite", "qmin", "prix_achat", "prix_vente", "unite")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")

        headers = {
            "ref":        ("Référence", 100),
            "nom":        ("Désignation", 220),
            "categorie":  ("Catégorie", 130),
            "quantite":   ("Qté", 60),
            "qmin":       ("Qté Min", 65),
            "prix_achat": ("P. Achat", 100),
            "prix_vente": ("P. Vente", 100),
            "unite":      ("Unité", 70),
        }
        for col, (text, w) in headers.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor="center")
        self.tree.column("nom", anchor="w")

        # Style du treeview
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", font=("Helvetica", 10), rowheight=32,
                         background=COLOR_WHITE, fieldbackground=COLOR_WHITE,
                         foreground=COLOR_DARK)
        style.configure("Treeview.Heading", font=("Helvetica", 10, "bold"),
                         background=COLOR_RED, foreground=COLOR_WHITE)
        style.map("Treeview", background=[("selected", "#3B3837")])
        self.tree.tag_configure("alerte", background="#FDECEA", foreground=COLOR_RED)
        self.tree.tag_configure("normal", background=COLOR_WHITE)
        self.tree.tag_configure("zebra", background="#FAFAFA")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.tree.bind("<Double-1>", lambda e: self._edit_piece())

        # Actions bas
        actions = ctk.CTkFrame(self, fg_color=COLOR_WHITE, corner_radius=8, height=52)
        actions.pack(fill="x", padx=12, pady=6)
        actions.pack_propagate(False)

        GrayButton(actions, text="✏️  Modifier", command=self._edit_piece,
                   width=120, height=36).pack(side="left", padx=12, pady=8)
        GrayButton(actions, text="🗑️  Supprimer", command=self._delete_piece,
                   width=120, height=36).pack(side="left", padx=4, pady=8)
        self.count_label = ctk.CTkLabel(actions, text="", font=FONT_SMALL, text_color=COLOR_GRAY)
        self.count_label.pack(side="right", padx=16)

    def refresh(self):
        self.categories = db.get_categories()
        search = self.search_var.get()
        cat_nom = self.cat_filter.get()
        cat_id = None
        if cat_nom != "Toutes catégories":
            cat_id = next((c["id"] for c in self.categories if c["nom"] == cat_nom), None)

        pieces = db.get_pieces(search=search, categorie_id=cat_id)
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(pieces):
            tag = "alerte" if p["quantite"] <= p["qmin"] else ("normal" if i % 2 == 0 else "zebra")
            self.tree.insert("", "end", iid=str(p["id"]), tags=(tag,), values=(
                p.get("reference", "") or "",
                p["nom"],
                p.get("categorie_nom", "") or "",
                p["quantite"],
                p["qmin"],
                f'{p["prix_achat"]:.2f}',
                f'{p["prix_vente"]:.2f}',
                p.get("unite", "unité") or "unité",
            ))
        self.count_label.configure(text=f"{len(pieces)} pièce(s) affichée(s)")
        # Notif alertes (seulement si l'app est entièrement chargée)
        if hasattr(self.app, 'alertes_tab'):
            self.app.check_alerts()

    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _add_piece(self):
        cats = db.get_categories()
        PieceDialog(self, cats, on_save=self.refresh)

    def _edit_piece(self):
        pid = self._selected_id()
        if not pid:
            messagebox.showinfo("Info", "Sélectionnez une pièce à modifier.", parent=self)
            return
        piece = db.get_piece_by_id(pid)
        cats = db.get_categories()
        PieceDialog(self, cats, piece=piece, on_save=self.refresh)

    def _delete_piece(self):
        pid = self._selected_id()
        if not pid:
            messagebox.showinfo("Info", "Sélectionnez une pièce à supprimer.", parent=self)
            return
        piece = db.get_piece_by_id(pid)
        if messagebox.askyesno("Confirmer", f"Supprimer « {piece['nom']} » ?", parent=self):
            db.supprimer_piece(pid)
            self.refresh()


# ──────────────────────────────────────────────
#  ONGLET FACTURATION
# ──────────────────────────────────────────────
class FactureTab(ctk.CTkFrame):
    def __init__(self, master, app, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self.app = app
        self.current_facture_id = None
        self.current_facture_num = None
        self._build()

    def _build(self):
        # Split: gauche (création) / droite (historique)
        paned = ctk.CTkFrame(self, fg_color=COLOR_BG)
        paned.pack(fill="both", expand=True, padx=10, pady=10)

        left = ctk.CTkFrame(paned, fg_color=COLOR_BG)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        right = ctk.CTkFrame(paned, fg_color=COLOR_BG, width=300)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        self._build_creator(left)
        self._build_history(right)

    def _build_creator(self, parent):
        # ── Nouvelle facture ──
        top = SectionCard(parent, title="📋  Nouvelle Facture")
        top.pack(fill="x", pady=(0, 8))

        row1 = ctk.CTkFrame(top, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkLabel(row1, text="Client:", font=FONT_BOLD, width=70).pack(side="left")
        self.e_client = ctk.CTkEntry(row1, placeholder_text="Nom du client", height=34)
        self.e_client.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.e_tel = ctk.CTkEntry(row1, placeholder_text="Téléphone", height=34, width=140)
        self.e_tel.pack(side="left")

        btn_row = ctk.CTkFrame(top, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=(0, 12))
        RedButton(btn_row, text="📄  Nouvelle facture", command=self._new_facture,
                  width=180, height=36).pack(side="left")
        self.facture_label = ctk.CTkLabel(btn_row, text="Aucune facture ouverte",
                                          font=FONT_NORMAL, text_color=COLOR_GRAY)
        self.facture_label.pack(side="left", padx=16)

        # ── Ajouter article ──
        mid = SectionCard(parent, title="➕  Ajouter un article")
        mid.pack(fill="x", pady=(0, 8))

        search_row = ctk.CTkFrame(mid, fg_color="transparent")
        search_row.pack(fill="x", padx=15, pady=(0, 8))
        ctk.CTkLabel(search_row, text="Pièce:", font=FONT_BOLD, width=70).pack(side="left")
        self.art_search = ctk.CTkEntry(search_row, placeholder_text="🔍 Rechercher...", height=34)
        self.art_search.pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.art_search.bind("<KeyRelease>", self._search_pieces)

        # Listbox résultats
        lb_frame = ctk.CTkFrame(mid, fg_color=COLOR_LGRAY, corner_radius=6)
        lb_frame.pack(fill="x", padx=15, pady=(0, 8))
        self.lb_pieces = tk.Listbox(lb_frame, font=("Helvetica", 10), height=5,
                                    selectmode="single", bd=0,
                                    bg=COLOR_WHITE, fg=COLOR_DARK,
                                    selectbackground="#FDECEA", selectforeground=COLOR_RED)
        self.lb_pieces.pack(fill="x", padx=4, pady=4)
        self.lb_pieces.bind("<<ListboxSelect>>", self._on_piece_select)
        self._piece_results = []

        qty_row = ctk.CTkFrame(mid, fg_color="transparent")
        qty_row.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkLabel(qty_row, text="Quantité:", font=FONT_BOLD, width=80).pack(side="left")
        self.e_qty = ctk.CTkEntry(qty_row, placeholder_text="1", width=80, height=34)
        self.e_qty.pack(side="left", padx=(8, 12))
        self.e_qty.insert(0, "1")
        self.selected_piece_id = None
        self.piece_info_label = ctk.CTkLabel(qty_row, text="", font=FONT_SMALL, text_color=COLOR_GRAY)
        self.piece_info_label.pack(side="left")
        RedButton(qty_row, text="Ajouter →", command=self._add_line,
                  width=120, height=34).pack(side="right")

        # ── Lignes facture ──
        lines_card = SectionCard(parent, title="🧾  Articles facturés")
        lines_card.pack(fill="both", expand=True, pady=(0, 8))

        tree_f = ctk.CTkFrame(lines_card, fg_color=COLOR_WHITE, corner_radius=6)
        tree_f.pack(fill="both", expand=True, padx=15, pady=(0, 8))

        cols = ("piece", "ref", "qty", "pu", "total")
        self.lines_tree = ttk.Treeview(tree_f, columns=cols, show="headings", height=6)
        heads = {"piece": ("Désignation", 200), "ref": ("Réf.", 90), "qty": ("Qté", 60),
                 "pu": ("Prix U.", 100), "total": ("Total", 100)}
        for c, (h, w) in heads.items():
            self.lines_tree.heading(c, text=h)
            self.lines_tree.column(c, width=w, anchor="center")
        self.lines_tree.column("piece", anchor="w")
        vsb2 = ttk.Scrollbar(tree_f, orient="vertical", command=self.lines_tree.yview)
        self.lines_tree.configure(yscrollcommand=vsb2.set)
        vsb2.pack(side="right", fill="y")
        self.lines_tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Total & actions
        bot = ctk.CTkFrame(lines_card, fg_color="transparent")
        bot.pack(fill="x", padx=15, pady=(0, 12))
        GrayButton(bot, text="🗑️ Supprimer ligne", command=self._del_line,
                   width=160, height=34).pack(side="left")
        self.total_label = ctk.CTkLabel(bot, text="Total: 0.00 TND",
                                         font=("Helvetica", 14, "bold"), text_color=COLOR_RED)
        self.total_label.pack(side="right")

        # Remise & finaliser
        fin_row = ctk.CTkFrame(parent, fg_color=COLOR_WHITE, corner_radius=8, height=56)
        fin_row.pack(fill="x", pady=(0, 4))
        fin_row.pack_propagate(False)

        ctk.CTkLabel(fin_row, text="Remise (%):", font=FONT_BOLD).pack(side="left", padx=12, pady=10)
        self.e_remise = ctk.CTkEntry(fin_row, placeholder_text="0", width=70, height=34)
        self.e_remise.pack(side="left", pady=10)
        self.e_remise.insert(0, "0")

        GrayButton(fin_row, text="❌  Annuler", command=self._cancel_facture,
                   width=110, height=36).pack(side="right", padx=12, pady=10)
        RedButton(fin_row, text="✅  Finaliser & PDF", command=self._finalize,
                  width=170, height=36).pack(side="right", padx=4, pady=10)

    def _build_history(self, parent):
        hist = SectionCard(parent, title="📂  Historique")
        hist.pack(fill="both", expand=True)

        self.hist_tree = ttk.Treeview(hist, columns=("num", "client", "total", "statut"),
                                      show="headings", height=20)
        hh = {"num": ("N°", 90), "client": ("Client", 100), "total": ("Total", 75), "statut": ("Statut", 70)}
        for c, (h, w) in hh.items():
            self.hist_tree.heading(c, text=h)
            self.hist_tree.column(c, width=w, anchor="center")

        self.hist_tree.tag_configure("finalisée", foreground="#27AE60")
        self.hist_tree.tag_configure("annulée", foreground=COLOR_GRAY)
        self.hist_tree.tag_configure("ouverte", foreground=COLOR_WARN)

        vsb3 = ttk.Scrollbar(hist, orient="vertical", command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=vsb3.set)
        vsb3.pack(side="right", fill="y")
        self.hist_tree.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.hist_tree.bind("<Double-1>", self._view_hist_facture)
        ctk.CTkLabel(hist, text="Double-clic = voir PDF", font=FONT_SMALL,
                     text_color=COLOR_GRAY).pack(pady=(0, 8))
        self._refresh_history()

    def _refresh_history(self):
        self.hist_tree.delete(*self.hist_tree.get_children())
        for f in db.get_historique_factures():
            try:
                d = datetime.fromisoformat(f["date_facture"]).strftime("%d/%m %H:%M")
            except Exception:
                d = ""
            self.hist_tree.insert("", "end", iid=str(f["id"]),
                                   tags=(f["statut"],), values=(
                f["numero"], f["client_nom"],
                f'{f["total_ttc"]:.2f}', f["statut"]
            ))

    # ── Actions ──
    def _new_facture(self):
        if self.current_facture_id:
            if not messagebox.askyesno("Attention", "Une facture est déjà ouverte. Créer quand même ?", parent=self):
                return
        client = self.e_client.get().strip() or "Client"
        tel    = self.e_tel.get().strip()
        fid, fnum = db.creer_facture(client, tel)
        self.current_facture_id  = fid
        self.current_facture_num = fnum
        self.facture_label.configure(text=f"Facture: {fnum}", text_color=COLOR_RED)
        self._refresh_lines()
        self._refresh_history()

    def _search_pieces(self, event=None):
        q = self.art_search.get()
        self._piece_results = db.get_pieces(search=q)
        self.lb_pieces.delete(0, "end")
        for p in self._piece_results:
            stock_txt = f" [Stock: {p['quantite']}]"
            self.lb_pieces.insert("end", f"{p['nom']}  —  {p['prix_vente']:.2f} TND{stock_txt}")

    def _on_piece_select(self, event=None):
        sel = self.lb_pieces.curselection()
        if not sel:
            return
        p = self._piece_results[sel[0]]
        self.selected_piece_id = p["id"]
        self.piece_info_label.configure(
            text=f"Stock: {p['quantite']} {p.get('unite','unité')}  |  Réf: {p.get('reference','')}")

    def _add_line(self):
        if not self.current_facture_id:
            messagebox.showwarning("Attention", "Ouvrez d'abord une nouvelle facture.", parent=self)
            return
        if not self.selected_piece_id:
            messagebox.showwarning("Attention", "Sélectionnez une pièce.", parent=self)
            return
        try:
            qty = int(self.e_qty.get() or 1)
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erreur", "Quantité invalide.", parent=self)
            return

        ok, msg = db.ajouter_ligne_facture(self.current_facture_id, self.selected_piece_id, qty)
        if not ok:
            messagebox.showerror("Erreur", msg, parent=self)
            return
        self._refresh_lines()
        self.app.stock_tab.refresh()

    def _del_line(self):
        sel = self.lines_tree.selection()
        if not sel:
            return
        ligne_id = int(sel[0])
        db.supprimer_ligne_facture(ligne_id)
        self._refresh_lines()
        self.app.stock_tab.refresh()

    def _refresh_lines(self):
        self.lines_tree.delete(*self.lines_tree.get_children())
        if not self.current_facture_id:
            self.total_label.configure(text="Total: 0.00 TND")
            return
        facture = db.get_facture(self.current_facture_id)
        lignes = db.get_lignes_facture(self.current_facture_id)
        for l in lignes:
            self.lines_tree.insert("", "end", iid=str(l["id"]), values=(
                l["piece_nom"], l.get("piece_ref", ""),
                l["quantite"], f'{l["prix_unitaire"]:.2f}', f'{l["total_ligne"]:.2f}'
            ))
        total = facture["total_ttc"] if facture else 0
        self.total_label.configure(text=f"Total: {total:,.2f} TND")

    def _finalize(self):
        if not self.current_facture_id:
            messagebox.showwarning("Attention", "Aucune facture ouverte.", parent=self)
            return
        lignes = db.get_lignes_facture(self.current_facture_id)
        if not lignes:
            messagebox.showwarning("Attention", "Ajoutez au moins un article.", parent=self)
            return
        try:
            remise = float(self.e_remise.get() or 0)
        except ValueError:
            remise = 0
        db.finaliser_facture(self.current_facture_id, remise)
        facture = db.get_facture(self.current_facture_id)
        # Générer PDF
        try:
            path = generer_facture_pdf(facture, lignes)
            messagebox.showinfo("Succès", f"Facture finalisée!\nPDF: {path}", parent=self)
            try:
                if sys.platform.startswith("win"):
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Erreur PDF", str(e), parent=self)
        self.current_facture_id = None
        self.current_facture_num = None
        self.facture_label.configure(text="Aucune facture ouverte", text_color=COLOR_GRAY)
        self._refresh_lines()
        self._refresh_history()
        self.app.stock_tab.refresh()

    def _cancel_facture(self):
        if not self.current_facture_id:
            return
        if messagebox.askyesno("Confirmer", "Annuler cette facture et restaurer le stock ?", parent=self):
            db.annuler_facture(self.current_facture_id)
            self.current_facture_id = None
            self.current_facture_num = None
            self.facture_label.configure(text="Aucune facture ouverte", text_color=COLOR_GRAY)
            self._refresh_lines()
            self._refresh_history()
            self.app.stock_tab.refresh()

    def _view_hist_facture(self, event=None):
        sel = self.hist_tree.selection()
        if not sel:
            return
        fid = int(sel[0])
        facture = db.get_facture(fid)
        lignes = db.get_lignes_facture(fid)
        if not lignes:
            messagebox.showinfo("Facture vide", "Cette facture ne contient aucun article.", parent=self)
            return
        try:
            path = generer_facture_pdf(facture, lignes)
            if sys.platform.startswith("win"):
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)


# ──────────────────────────────────────────────
#  ONGLET ALERTES
# ──────────────────────────────────────────────
class AlertesTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self._build()
        self.refresh()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color=COLOR_RED, corner_radius=8, height=50)
        header.pack(fill="x", padx=12, pady=(12, 6))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="⚠️  Alertes de Stock Minimum",
                     font=FONT_HEADER, text_color=COLOR_WHITE).pack(side="left", padx=15, pady=12)
        GrayButton(header, text="🔄 Actualiser", command=self.refresh,
                   width=120, height=34).pack(side="right", padx=12, pady=8)

        card = SectionCard(self)
        card.pack(fill="both", expand=True, padx=12, pady=6)

        cols = ("nom", "ref", "quantite", "qmin", "manquant", "categorie")
        self.tree = ttk.Treeview(card, columns=cols, show="headings")
        heads = {
            "nom": ("Désignation", 220), "ref": ("Référence", 100),
            "quantite": ("Stock actuel", 100), "qmin": ("Stock min", 90),
            "manquant": ("À commander", 100), "categorie": ("Catégorie", 130)
        }
        for c, (h, w) in heads.items():
            self.tree.heading(c, text=h)
            self.tree.column(c, width=w, anchor="center")
        self.tree.column("nom", anchor="w")
        self.tree.tag_configure("rouge", background="#FDECEA", foreground=COLOR_RED)
        self.tree.tag_configure("orange", background="#FEF9E7", foreground=COLOR_WARN)

        vsb = ttk.Scrollbar(card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y", padx=(0, 8), pady=8)
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)

        self.info_label = ctk.CTkLabel(self, text="", font=FONT_NORMAL, text_color=COLOR_GRAY)
        self.info_label.pack(pady=6)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        alertes = db.get_pieces_stock_bas()
        for p in alertes:
            manquant = max(0, p["qmin"] - p["quantite"])
            tag = "rouge" if p["quantite"] == 0 else "orange"
            self.tree.insert("", "end", tags=(tag,), values=(
                p["nom"], p.get("reference", "") or "",
                p["quantite"], p["qmin"], manquant,
                p.get("categorie_nom", "") or ""
            ))
        if alertes:
            self.info_label.configure(
                text=f"⚠️  {len(alertes)} pièce(s) en dessous du stock minimum",
                text_color=COLOR_RED)
        else:
            self.info_label.configure(
                text="✅  Tous les stocks sont suffisants", text_color="#27AE60")


# ──────────────────────────────────────────────
#  ONGLET PARAMÈTRES
# ──────────────────────────────────────────────
class ParametresTab(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLOR_BG)
        super().__init__(master, **kwargs)
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="⚙️  Paramètres", font=FONT_TITLE,
                     text_color=COLOR_DARK).pack(pady=(20, 10), padx=20, anchor="w")

        # Backup
        backup_card = SectionCard(self, title="💾  Sauvegarde")
        backup_card.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(backup_card, text=(
            "La base de données est stockée localement dans le dossier db/srg.db\n"
            "Pour la synchronisation mobile, activez la sauvegarde automatique vers\n"
            "Google Drive, OneDrive, ou Dropbox en pointant vers leur dossier local synchronisé."
        ), font=FONT_NORMAL, text_color=COLOR_GRAY, justify="left").pack(padx=15, pady=(4, 8))

        row = ctk.CTkFrame(backup_card, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=(0, 12))
        self.backup_path = ctk.CTkEntry(row, placeholder_text="Chemin du dossier de sauvegarde...", height=34)
        self.backup_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        # Essayer de charger chemin sauvegardé
        self._load_backup_path()

        RedButton(row, text="📁  Choisir dossier", command=self._choose_dir,
                  width=150, height=34).pack(side="left", padx=(0, 8))
        RedButton(row, text="💾  Sauvegarder maintenant", command=self._do_backup,
                  width=200, height=34).pack(side="left")

        # Catégories
        cat_card = SectionCard(self, title="📂  Gestion des catégories")
        cat_card.pack(fill="x", padx=16, pady=8)
        row2 = ctk.CTkFrame(cat_card, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(0, 12))
        self.e_cat = ctk.CTkEntry(row2, placeholder_text="Nom de la nouvelle catégorie", height=34)
        self.e_cat.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.cat_type = ctk.StringVar(value="auto")
        ctk.CTkOptionMenu(row2, variable=self.cat_type, values=["auto", "agri"],
                          width=100, height=34).pack(side="left", padx=(0, 8))
        RedButton(row2, text="➕  Ajouter", command=self._add_cat, width=120, height=34).pack(side="left")

        # Info
        info_card = SectionCard(self, title="ℹ️  À propos")
        info_card.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(info_card, text=(
            "SRG — Société de Rechange et Garniture\n"
            "Application de gestion de stock et facturation\n"
            "Version 1.0  |  Développée avec Python & CustomTkinter"
        ), font=FONT_NORMAL, text_color=COLOR_GRAY, justify="left").pack(padx=15, pady=(4, 15))

    def _load_backup_path(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "backups", "config.txt")
        if os.path.exists(cfg_path):
            with open(cfg_path) as f:
                path = f.read().strip()
            self.backup_path.insert(0, path)

    def _choose_dir(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Choisir le dossier de sauvegarde")
        if path:
            self.backup_path.delete(0, "end")
            self.backup_path.insert(0, path)
            cfg_path = os.path.join(os.path.dirname(__file__), "backups", "config.txt")
            os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
            with open(cfg_path, "w") as f:
                f.write(path)

    def _do_backup(self):
        path = self.backup_path.get().strip() or None
        try:
            dest = db.backup_db(path)
            messagebox.showinfo("Succès", f"Sauvegarde créée:\n{dest}")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _add_cat(self):
        nom = self.e_cat.get().strip()
        if nom:
            db.ajouter_categorie(nom, self.cat_type.get())
            self.e_cat.delete(0, "end")
            messagebox.showinfo("OK", f"Catégorie « {nom} » ajoutée.")
        else:
            messagebox.showwarning("Attention", "Entrez un nom de catégorie.")


# ──────────────────────────────────────────────
#  APPLICATION PRINCIPALE
# ──────────────────────────────────────────────
class SRGApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.title("SRG — Gestion de Stock et Facturation")
        self.geometry("1200x780")
        self.minsize(900, 600)
        self._alert_shown = False
        self._build_ui()
        self.after(1000, self.check_alerts)

    def _build_ui(self):
        self.configure(fg_color=COLOR_BG)

        # ── BARRE TITRE ──
        titlebar = ctk.CTkFrame(self, fg_color=COLOR_RED, corner_radius=0, height=62)
        titlebar.pack(fill="x")
        titlebar.pack_propagate(False)

        # Logo SRG
        logo_frame = ctk.CTkFrame(titlebar, fg_color="transparent")
        logo_frame.pack(side="left", padx=18, pady=8)
        ctk.CTkLabel(logo_frame, text="SRG", font=("Helvetica", 26, "bold"),
                     text_color=COLOR_WHITE).pack(side="left")
        ctk.CTkLabel(logo_frame, text=" Société de Rechange et Garniture",
                     font=("Helvetica", 11), text_color="#FFCCCC").pack(side="left", pady=(8, 0))

        # Stats rapides dans le titre
        self.stat_frame = ctk.CTkFrame(titlebar, fg_color="transparent")
        self.stat_frame.pack(side="right", padx=20, pady=8)
        self.lbl_pieces = ctk.CTkLabel(self.stat_frame, text="", font=FONT_SMALL, text_color=COLOR_WHITE)
        self.lbl_pieces.pack(side="right", padx=10)
        self.lbl_alert = ctk.CTkLabel(self.stat_frame, text="", font=FONT_SMALL, text_color="#FFEEAA")
        self.lbl_alert.pack(side="right", padx=10)

        # ── TABS ──
        self.tabview = ctk.CTkTabview(self, fg_color=COLOR_BG,
                                       segmented_button_fg_color=COLOR_LGRAY,
                                       segmented_button_selected_color=COLOR_RED,
                                       segmented_button_selected_hover_color=COLOR_RED_H,
                                       segmented_button_unselected_color=COLOR_LGRAY,
                                       segmented_button_unselected_hover_color="#D5D5D5",
                                       text_color=COLOR_DARK,
                                       text_color_disabled=COLOR_GRAY)
        self.tabview.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self.tabview.add("📦  Stock")
        self.tabview.add("🧾  Facturation")
        self.tabview.add("⚠️  Alertes")
        self.tabview.add("⚙️  Paramètres")

        self.stock_tab = StockTab(self.tabview.tab("📦  Stock"), self)
        self.stock_tab.pack(fill="both", expand=True)

        self.facture_tab = FactureTab(self.tabview.tab("🧾  Facturation"), self)
        self.facture_tab.pack(fill="both", expand=True)

        self.alertes_tab = AlertesTab(self.tabview.tab("⚠️  Alertes"))
        self.alertes_tab.pack(fill="both", expand=True)

        self.params_tab = ParametresTab(self.tabview.tab("⚙️  Paramètres"))
        self.params_tab.pack(fill="both", expand=True)

        self._update_header_stats()

    def _update_header_stats(self):
        if not hasattr(self, 'lbl_pieces'):
            return
        stats = db.get_stats()
        self.lbl_pieces.configure(text=f"🗄️  {stats['total_pieces']} pièces")
        alertes = stats["alertes_stock"]
        if alertes > 0:
            self.lbl_alert.configure(text=f"⚠️  {alertes} alerte(s)")
        else:
            self.lbl_alert.configure(text="✅  Stock OK")

    def check_alerts(self):
        """Vérifie les alertes stock et affiche une notification."""
        alertes = db.get_pieces_stock_bas()
        self._update_header_stats()
        if hasattr(self, 'alertes_tab'):
            self.alertes_tab.refresh()
        if alertes and not self._alert_shown:
            self._alert_shown = True
            noms = "\n".join(f"• {p['nom']} (stock: {p['quantite']}, min: {p['qmin']})"
                             for p in alertes[:5])
            msg = f"{len(alertes)} pièce(s) à réapprovisionner:\n\n{noms}"
            if len(alertes) > 5:
                msg += f"\n... et {len(alertes)-5} autres"
            messagebox.showwarning("⚠️  Alerte Stock Minimum", msg)
        elif not alertes:
            self._alert_shown = False
        self.after(60000, self.check_alerts)  # Vérifie toutes les minutes


if __name__ == "__main__":
    app = SRGApp()
    app.mainloop()