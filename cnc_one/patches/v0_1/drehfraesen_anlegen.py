"""Die Arbeitsgangart „Drehfräsen“ (Standard intern) anlegen, falls es sie noch nicht gibt. Fräsen und Drehen gibt es schon."""

import frappe


def execute():
	if not frappe.db.exists("Arbeitsgangart", {"bezeichnung": "Drehfräsen"}):
		frappe.get_doc({"doctype": "Arbeitsgangart", "bezeichnung": "Drehfräsen", "typ": "Intern", "aktiv": 1}).insert(ignore_permissions=True)
