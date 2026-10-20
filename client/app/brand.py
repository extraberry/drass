"""Display names and asset paths. The product is branded ResearchVault; internal identifiers (DB name, folders) are unchanged."""
import os

APP_NAME = "ResearchVault"
TAGLINE = "Digital Research Archiving System with Semantic Search"
INSTITUTION = "Mary the Queen College of Quezon City, Inc."
RES = os.path.join(os.path.dirname(__file__), "resources")


def res(name: str) -> str:
    return os.path.join(RES, name)
