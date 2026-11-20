"""Angebote überarbeiten (neue Fassung -1, -2 …) und laufende Aufträge ändern (mit Verlauf und neuer AB)."""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from cnc_one.api import angebot, auftrag, belegdruck, fertigung, lieferschein
from cnc_one.logic import pdf
from cnc_one.tests.test_angebot import teil


class TestAngebotFassungen(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Fassungskunde"}).insert().name

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def gesendet(self, teile):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde, "projekt": "ZZ-Projekt"}, "teile": teile})
		return angebot.senden(a["id"])

	def test_ueberarbeiten_legt_fassung_an_und_ersetzt_beim_senden(self):
		a = self.gesendet([teil("t1"), teil("t2", "Welle", "ZZ-FA-2")])
		n = angebot.ueberarbeiten(a["id"], "Welle entfällt")
		self.assertEqual(n["id"], f"{a['id']}-1")
		self.assertEqual(n["status"], "Entwurf")
		self.assertEqual((n["fassung"], n["ursprung"], n["vorgaenger"], n["aenderungsgrund"]), (1, a["id"], a["id"], "Welle entfällt"))
		self.assertEqual([p["key"] for p in n["positionen"]], ["t1", "t2"])
		self.assertEqual(n["kopf"]["projekt"], "ZZ-Projekt")
		self.assertEqual([f["id"] for f in n["fassungen"]], [a["id"], n["id"]])
		# ein zweiter Klick liefert dieselbe offene Überarbeitung
		self.assertEqual(angebot.ueberarbeiten(a["id"])["id"], n["id"])
		# solange die neue Fassung Entwurf ist, gilt das Original
		self.assertEqual(frappe.db.get_value("Angebot", a["id"], "status"), "Gesendet")

		# Position streichen und senden: das Original bleibt inhaltlich unverändert, gilt aber als ersetzt
		netto_alt = frappe.db.get_value("Angebot", a["id"], "netto")
		angebot.entwurf_speichern({"id": n["id"], "kopf": {"kundeId": self.kunde}, "teile": [teil("t1")]})
		angebot.senden(n["id"])
		alt = frappe.get_doc("Angebot", a["id"])
		self.assertEqual((alt.status, alt.ersetzt_durch, len(alt.positionen), alt.netto), ("Ersetzt", n["id"], 2, netto_alt))
		with self.assertRaises(frappe.ValidationError):
			angebot.ueberarbeiten(a["id"])
		with self.assertRaises(frappe.ValidationError):
			auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 10}])

		# die nächste Fassung zählt weiter am ursprünglichen Angebot
		n2 = angebot.ueberarbeiten(n["id"])
		self.assertEqual((n2["id"], n2["fassung"], n2["ursprung"], n2["vorgaenger"]), (f"{a['id']}-2", 2, a["id"], n["id"]))

	def test_beauftragtes_angebot_wird_im_auftrag_geaendert(self):
		a = self.gesendet([teil("t1")])
		auftrag.aus_angebot(a["id"], "", [{"angebotKey": "t1", "menge": 10}])
		with self.assertRaises(frappe.ValidationError):
			angebot.ueberarbeiten(a["id"])

	def test_entwurf_laesst_sich_nicht_ueberarbeiten(self):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1")]})
		with self.assertRaises(frappe.ValidationError):
			angebot.ueberarbeiten(a["id"])

	def test_pdf_nennt_das_ersetzte_angebot(self):
		a = self.gesendet([teil("t1")])
		n = angebot.ueberarbeiten(a["id"])
		g = {}
		with patch.object(pdf, "pdf_a3", side_effect=lambda html, **kw: g.setdefault("h", html) and b""):
			angebot.pdf_erzeugen(frappe.get_doc("Angebot", n["id"]))
		self.assertIn("Überarbeitetes Angebot", g["h"])
		self.assertIn(f"ersetzt unser Angebot {a['id']}", g["h"])


class TestAuftragAendern(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.kunde = frappe.get_doc({"doctype": "Kunde", "kundenname": "ZZ Änderungskunde"}).insert().name
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t1", "Flansch", "ZZ-AE-1"), teil("t2", "Welle", "ZZ-AE-2")]})
		self.ang = angebot.senden(a["id"])
		self.auf = auftrag.aus_angebot(self.ang["id"], "PO-AE", [{"angebotKey": "t1", "menge": 10, "termin": "2026-12-01"}, {"angebotKey": "t2", "menge": 5}])
		self.p1, self.p2 = (p["key"] for p in self.auf["positionen"])

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_menge_preis_termin_und_kosten_aendern(self):
		r = auftrag.aendern(self.auf["id"], "Nachverhandlung", [
			{"key": self.p1, "menge": 8, "einzelpreis": 9.5, "termin": "2026-12-15", "kosten": [{"label": "Rüstkosten", "betrag": 50}]},
		])
		p = r["positionen"][0]
		self.assertEqual((p["menge"], p["einzelpreis"], p["termin"], p["mengeUrspruenglich"]), (8, 9.5, "2026-12-15", 10))
		self.assertEqual(p["kosten"], [{"label": "Rüstkosten", "betrag": 50}])
		self.assertAlmostEqual(p["summe"], 8 * 9.5 + 50, places=2)
		self.assertEqual(r["aenderungNr"], 1)
		z = r["aenderungen"][0]
		self.assertEqual((z["nr"], z["grund"]), (1, "Nachverhandlung"))
		text = "\n".join(z["details"])
		for teil_text in ("Menge 10 → 8 Stk", "Stückpreis", "Liefertermin 01.12.2026 → 15.12.2026", "Messkosten entfällt", "Rüstkosten"):
			self.assertIn(teil_text, text)
		self.assertEqual(r["ab"]["aenderung"], 0)  # neue AB steht aus

	def test_position_entfaellt_und_kommt_nicht_mehr_in_lieferschein(self):
		r = auftrag.aendern(self.auf["id"], "Kunde braucht die Welle nicht", [{"key": self.p2, "menge": 0}])
		p = next(x for x in r["positionen"] if x["key"] == self.p2)
		self.assertTrue(p["entfallen"])
		self.assertEqual((p["menge"], p["summe"], p["kosten"]), (0, 0, []))
		self.assertNotIn(self.p2, [x["auftragPosKey"] for x in lieferschein.vorschlag(self.auf["id"])["positionen"]])

	def test_grund_ist_pflicht_und_ohne_aenderung_gibt_es_fehler(self):
		with self.assertRaises(frappe.ValidationError):
			auftrag.aendern(self.auf["id"], "", [{"key": self.p1, "menge": 5}])
		with self.assertRaises(frappe.ValidationError):
			auftrag.aendern(self.auf["id"], "nichts", [{"key": self.p1, "menge": 10}])

	def test_nicht_unter_die_gelieferte_menge(self):
		lieferschein.anlegen(self.kunde, [{"auftrag": self.auf["id"], "auftragsposition": self.p1, "menge": 6}])
		with self.assertRaises(frappe.ValidationError):
			auftrag.aendern(self.auf["id"], "weniger", [{"key": self.p1, "menge": 5}])
		r = auftrag.aendern(self.auf["id"], "weniger", [{"key": self.p1, "menge": 6}])
		self.assertEqual(r["positionen"][0]["menge"], 6)

	def test_neue_position_aus_dem_angebot(self):
		a = angebot.entwurf_speichern({"id": None, "kopf": {"kundeId": self.kunde}, "teile": [teil("t9", "Hülse", "ZZ-AE-9")]})
		a = angebot.senden(a["id"])
		r = auftrag.aendern(self.auf["id"], "Zusatzbestellung", [], [{"angebotId": a["id"], "angebotKey": "t9", "menge": 3}])
		self.assertEqual(len(r["positionen"]), 3)
		self.assertEqual(r["positionen"][-1]["menge"], 3)
		self.assertIn("Neue Position Hülse", r["aenderungen"][0]["details"][0])

	def test_fertigung_wird_mitgezogen(self):
		fertigung.starten(self.auf["id"])
		auftrag.aendern(self.auf["id"], "weniger und Welle entfällt", [{"key": self.p1, "menge": 7, "termin": "2026-12-20"}, {"key": self.p2, "menge": 0}])
		fb1 = frappe.get_doc("Fertigungsbauteil", {"auftrag": self.auf["id"], "auftragsposition_key": self.p1})
		self.assertEqual((fb1.menge, str(fb1.termin)), (7, "2026-12-20"))
		self.assertIn("Auftragsänderung 1", fb1.bemerkungen)
		self.assertFalse(frappe.db.exists("Fertigungsbauteil", {"auftrag": self.auf["id"], "auftragsposition_key": self.p2}))
		details = frappe.get_doc("Auftrag", self.auf["id"]).aenderungen[0].details
		self.assertIn("Fertigung: Welle", details)

	def test_ab_zur_aenderung(self):
		auftrag.aendern(self.auf["id"], "Welle entfällt", [{"key": self.p2, "menge": 0}])
		d = frappe.get_doc("Auftrag", self.auf["id"])
		self.assertEqual(belegdruck.ab_dateiname(d), f"Auftragsbestätigung {d.name} Änderung 1.pdf")
		g = {}
		with patch.object(pdf, "pdf_a3", side_effect=lambda html, **kw: g.setdefault("h", html) and b""):
			belegdruck.ab_pdf_erzeugen(d)
		h = g["h"]
		self.assertIn("Auftragsbestätigung – Änderung 1", h)
		self.assertIn("entfällt", h)
		self.assertIn("Welle (ZZ-AE-2): entfällt (vorher 5 Stk)", h)
		self.assertNotIn("Fertigung:", h)
