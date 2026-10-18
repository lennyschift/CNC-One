import frappe

from cnc_one.logic import lager


def execute():
	"""Bringt das Lager auf den Stand der schon vorhandenen Fertigungsbauteile."""
	for name in frappe.get_all("Fertigungsbauteil", pluck="name"):
		lager.fertigung_abgleichen(frappe.get_doc("Fertigungsbauteil", name))
