from assignment_autopsy.i18n import load_catalog


def test_english_catalog_comes_from_po_file() -> None:
    catalog = load_catalog("en")
    assert catalog["Mis equipos"] == "My teams"
    assert catalog["Insertar nivel aquí"] == "Insert level here"


def test_spanish_catalog_is_identity() -> None:
    catalog = load_catalog("es")
    assert all(source == target for source, target in catalog.items())


def test_unknown_language_is_empty() -> None:
    assert load_catalog("xx") == {}
