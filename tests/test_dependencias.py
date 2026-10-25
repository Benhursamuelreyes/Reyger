"""requirements.txt (CI y desarrollo) y pyproject.toml (instaladores) no
deben divergir: antes faltaba platformdirs y la cota de cryptography."""

import os
import re

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def _normalizar(dependencia):
    return re.sub(r"\s+", "", dependencia).replace('"', "'")


def _pyproject():
    with open(os.path.join(RAIZ, "pyproject.toml"), encoding="utf-8") as f:
        texto = f.read()
    bloque = re.search(r"^dependencies = \[(.*?)^\]", texto, re.M | re.S).group(1)
    return {_normalizar(d) for d in re.findall(r'"([^"]+)"', bloque)}


def _requirements():
    with open(os.path.join(RAIZ, "requirements.txt"), encoding="utf-8") as f:
        lineas = [l.split("#")[0].strip() for l in f]
    return {_normalizar(l) for l in lineas if l}


def test_requirements_incluye_todas_las_dependencias_de_pyproject():
    faltan = _pyproject() - _requirements()
    assert not faltan, f"Faltan en requirements.txt: {sorted(faltan)}"


def test_requirements_solo_anade_dependencias_de_windows():
    extra = _requirements() - _pyproject()
    assert all("platform_system=='Windows'" in d for d in extra), extra
