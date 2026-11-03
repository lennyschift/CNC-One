"""Frappes Datei mit Löschsperre: die Prüfung läuft, bevor die Datei von der Platte entfernt wird."""

from frappe.core.doctype.file.file import File

from cnc_one.logic import archiv


class ArchivFile(File):
	def on_trash(self):
		archiv.loeschen_pruefen(self)
		super().on_trash()
		archiv.datei_protokollieren("Gelöscht", self)
