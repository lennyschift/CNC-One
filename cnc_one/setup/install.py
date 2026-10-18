from cnc_one.setup import rollen


def after_install():
	rollen.anlegen()
	rollen.standard_waehrung()
