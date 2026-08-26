"""Tests de Persistencia Segura (encriptación Fernet)."""

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

PLANTILLA = os.path.join(
    os.path.dirname(__file__), "..", "src", "reyger", "assets", "database.db"
)


@pytest.fixture(autouse=True)
def _entorno_seguro(tmp_path):
    """Entorno temporal con BD y directorio de clave propio."""
    import reyger.core.db as modulo_db
    import reyger.core.backup as mod_backup
    from reyger.core import seguridad as seg

    ruta_bd = str(tmp_path / "tienda.db")
    shutil.copyfile(PLANTILLA, ruta_bd)
    original_db = modulo_db.get_db_path
    modulo_db.get_db_path = lambda: ruta_bd
    modulo_db.close()

    # Redirigir get_db_path de backup.py también
    original_backup_get_db = mod_backup.get_db_path
    mod_backup.get_db_path = lambda: ruta_bd

    # Redirigir la clave a un directorio temporal
    original_ruta_clave = seg._ruta_clave
    seg._ruta_clave = lambda: os.path.join(str(tmp_path), "reyger.key")

    yield

    modulo_db.close()
    modulo_db.get_db_path = original_db
    mod_backup.get_db_path = original_backup_get_db
    seg._ruta_clave = original_ruta_clave


def test_generar_clave():
    """generar_clave crea un fichero .key persistente."""
    from reyger.core import seguridad as seg

    clave = seg.generar_clave()
    assert clave is not None
    assert len(clave) > 20
    assert os.path.exists(seg.ruta_clave())


def test_clave_persiste():
    """Si la clave ya existe, cargar_clave retorna la misma."""
    from reyger.core import seguridad as seg

    clave1 = seg.generar_clave()
    clave2 = seg.generar_clave()
    assert clave1 == clave2


def test_cargar_clave_sin_fichero():
    """Si no hay fichero de clave, devuelve None."""
    from reyger.core import seguridad as seg

    # Eliminar la clave si existe
    if os.path.exists(seg.ruta_clave()):
        os.unlink(seg.ruta_clave())
    assert seg.cargar_clave() is None


def test_cifrar_descifrar_fichero(tmp_path):
    """Cifrar y descifrar un fichero produce los datos originales."""
    from reyger.core import seguridad as seg

    orig = tmp_path / "datos.txt"
    orig.write_bytes(b"contenido secreto de prueba")

    ruta_enc = seg.cifrar_fichero(str(orig))
    assert os.path.exists(ruta_enc)
    assert ruta_enc.endswith(".enc")
    assert os.path.getsize(ruta_enc) > len(b"contenido secreto de prueba")

    ruta_dec = seg.descifrar_fichero(ruta_enc)
    assert open(ruta_dec, "rb").read() == b"contenido secreto de prueba"


def test_cifrar_descifrar_ruta_custom(tmp_path):
    """Se puede especificar una ruta de salida personalizada."""
    from reyger.core import seguridad as seg

    orig = tmp_path / "base.db"
    orig.write_bytes(b"datos de base")
    salida = tmp_path / "encriptado.bin"

    seg.cifrar_fichero(str(orig), str(salida))
    assert os.path.exists(str(salida))

    desc = tmp_path / "restaurado.db"
    seg.descifrar_fichero(str(salida), str(desc))
    assert desc.read_bytes() == b"datos de base"


def test_descifrar_con_clave_erronea(tmp_path):
    """Descifrar con una clave diferente lanza InvalidToken."""
    from reyger.core import seguridad as seg
    from cryptography.fernet import InvalidToken

    orig = tmp_path / "secreto.bin"
    orig.write_bytes(b"secreto")
    enc = seg.cifrar_fichero(str(orig))

    # Sobrescribir la clave
    from cryptography.fernet import Fernet
    clave_mala = Fernet.generate_key()
    with open(seg.ruta_clave(), "wb") as f:
        f.write(clave_mala)

    with pytest.raises(InvalidToken):
        seg.descifrar_fichero(enc)


def test_existe_clave():
    """existe_clave indica correctamente si hay clave."""
    from reyger.core import seguridad as seg

    if os.path.exists(seg.ruta_clave()):
        os.unlink(seg.ruta_clave())
    assert not seg.existe_clave()

    seg.generar_clave()
    assert seg.existe_clave()


def test_backup_exportar_encriptado(tmp_path):
    """exportar_datos con encriptado=True genera un .db.enc."""
    import reyger.core.db as modulo_db
    import reyger.core.backup as mod_backup

    ruta_salida = str(tmp_path / "backup_test.db")
    resultado, tipo = mod_backup.exportar_datos(ruta_salida, encriptado=True)
    assert tipo == "db_enc"
    assert os.path.exists(ruta_salida + ".enc")


def test_backup_importar_encriptado(tmp_path):
    """importar_datos descifra un .db.enc antes de importar."""
    import reyger.core.db as modulo_db
    import reyger.core.backup as mod_backup

    # Exportar encriptado
    ruta_enc = str(tmp_path / "backup_enc.db")
    mod_backup.exportar_datos(ruta_enc, encriptado=True)
    assert os.path.exists(ruta_enc + ".enc")

    # Importar el .enc
    resultado = mod_backup.importar_datos(ruta_enc + ".enc")
    assert resultado.get("encriptado") is True
    assert resultado["modo"] == "completa"
