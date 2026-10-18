import json
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

from cnc_one.logic.kalkulation import berechne, num, r2


def faelle():
	pfad = Path(frappe.get_app_path("cnc_one")).parent / "shared" / "kalkulation_faelle.json"
	return json.loads(pfad.read_text(encoding="utf-8"))


class TestKalkulation(UnitTestCase):
	def test_gleiche_ergebnisse_wie_die_oberflaeche(self):
		"""Dieselben Fälle prüft frontend/src/lib/kalkulation_faelle.test.js gegen calc.js."""
		alle = faelle()
		self.assertGreater(len(alle), 10)
		for f in alle:
			with self.subTest(f["name"]):
				self.assertEqual(berechne(f["eingabe"]), f["erwartet"])

	def test_zahlen_wie_in_javascript(self):
		self.assertEqual(num("12.5"), 12.5)
		self.assertEqual(num("12,5"), 0)
		self.assertEqual(num(None), 0)
		self.assertEqual(num(True), 1)
		self.assertEqual(num(float("nan")), 0)

	def test_runden_halbe_werte_nach_oben(self):
		self.assertEqual(r2(1.005), 1.01)
		self.assertEqual(r2(2.675), 2.68)
		self.assertEqual(r2(0.125), 0.13)
		self.assertEqual(r2(-0.125), -0.12)
