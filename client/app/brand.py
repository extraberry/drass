"""Display names and asset paths. The product is branded DRASS (Digital Research Archiving System with Semantic Search); internal identifiers (DB name, folders) are unchanged."""
import os

APP_NAME = "DRASS"
TAGLINE = "Digital Research Archiving System with Semantic Search"
INSTITUTION = "Mary the Queen College of Quezon City, Inc."
RES = os.path.join(os.path.dirname(__file__), "resources")


def logo_icon():
    """Open-book mark: navy book on a gold tile, in both themes."""
    from PySide6.QtGui import QIcon
    return QIcon(res("logo_book.svg"))


def res(name: str) -> str:
    return os.path.join(RES, name)
