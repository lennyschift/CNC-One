"""Auslieferung der CNC-One-Oberfläche unter /cnc-one.

Die Vue-App wird aus `frontend/` nach `cnc_one/public/frontend` gebaut (`npm run build:app`).
Diese Seite liest die fertige index.html zur Laufzeit und übernimmt deren Tags, damit nach
einem neuen Build keine Dateinamen angepasst werden müssen.
"""

import re
from urllib.parse import urlencode

import frappe
from frappe import _

from cnc_one.api.stamm import einstellungen

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.redirect(f"/login?{urlencode({'redirect-to': frappe.request.path})}")

	if frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User":
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	index = frappe.get_app_path("cnc_one", "public", "frontend", "index.html")
	try:
		with open(index, encoding="utf-8") as f:
			html = f.read()
	except FileNotFoundError:
		frappe.throw(_("Die Oberfläche wurde noch nicht gebaut (npm run build:app)."))

	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	# Farbschema des Benutzers, damit die Seite nicht erst hell aufblitzt
	context.theme = einstellungen().get("theme", "")
	context.style_tags = "\n".join(re.findall(r"<link[^>]+rel=\"(?:stylesheet|modulepreload)\"[^>]*>", html))
	context.script_tags = "\n".join(re.findall(r"<script[^>]+src=[^>]*></script>", html))
	return context
