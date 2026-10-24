from cnc_one.setup import arten, rechnung, rollen


def after_install():
	rollen.anlegen()
	rollen.standard_waehrung()
	arten.serienart_anlegen()
	rechnung.steuerschluessel_anlegen()
	rechnung.firma_vorbelegen()
