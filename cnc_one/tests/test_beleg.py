import json
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

from cnc_one.logic.beleg import position_fuer_auftrag
from cnc_one.logic.kalkulation import berechne


def faelle():
	pfad = Path(frappe.get_app_path("cnc_one")).parent / "shared" / "auftrag_faelle.json"
	return json.loads(pfad.read_text(encoding="utf-8"))


class TestBeleg(UnitTestCase):
	def test_gleiche_ergebnisse_wie_die_oberflaeche(self):
		"""Dieselben Fälle prüft frontend/src/lib/auftrag_faelle.test.js gegen beleg.js."""
		alle = faelle()
		self.assertGreater(len(alle), 8)
		for f in alle:
			with self.subTest(f["name"]):
				r = position_fuer_auftrag(f["teil"], berechne(f["teil"]), f["wahl"], f["menge"], f["kostenAus"])
				self.assertEqual(r, f["erwartet"])
