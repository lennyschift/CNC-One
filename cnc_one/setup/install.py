from cnc_one.setup import arten, rollen


def after_install():
	rollen.anlegen()
	rollen.standard_waehrung()
	arten.serienart_anlegen()
