import frappe

# Rollen der Anwendung. System Manager darf immer alles.
ROLLEN = ("CNC Admin", "CNC Vertrieb", "CNC Fertigung", "CNC Buchhaltung")


def anlegen():
	"""Legt die Rollen an, falls sie fehlen. Mehrfaches Ausführen ist unkritisch."""
	for name in ROLLEN:
		if not frappe.db.exists("Role", name):
			frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(ignore_permissions=True)


def standard_waehrung():
	"""Euro als Standardwährung, damit Währungsfelder ohne ERPNext sinnvoll formatiert werden."""
	if frappe.db.exists("Currency", "EUR"):
		frappe.db.set_default("currency", "EUR")
