"""B4: el aviso de copia manual debe existir en TODAS las rutas de exportación.

Con WAL activo los datos comprometidos viven también en ``database.db-wal``.
Copiar solo ``database.db`` a mano produce una copia incompleta, así que la
interfaz debe advertirlo y remitir a la API de respaldo de SQLite.

El fallo concreto que cubre: la advertencia solo estaba en Inventario. La
sección «Base de datos» de **Ajustes** exporta el mismo ``.db`` con el mismo
código y se exportaba sin ninguna advertencia, porque el texto estaba escrito
a mano dentro de un método en vez de en un sitio compartido. Estos tests
comprueban las dos rutas, no solo una.

Además comprueban que el aviso NO aparezca sin WAL: en modo ``delete`` una
copia manual es válida y el aviso solo sería ruido.
"""

import os
import sys
from unittest.mock import patch

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "src"))


# ---------------------------------------------------------------------------
# El texto canónico
# ---------------------------------------------------------------------------


class TestAvisoCanónico:
    """``core.backup.AVISO_COPIA_MANUAL`` es la fuente única del aviso."""

    def test_el_texto_existe_y_no_esta_vacio(self):
        from reyger.core.backup import AVISO_COPIA_MANUAL

        assert AVISO_COPIA_MANUAL.strip(), "El aviso no puede estar vacío"

    def test_explica_el_motivo_en_modo_wal(self):
        """Tiene que decir POR QUÉ falla la copia manual."""
        from reyger.core.backup import AVISO_COPIA_MANUAL

        assert "WAL" in AVISO_COPIA_MANUAL
        assert "database.db-wal" in AVISO_COPIA_MANUAL

    def test_prohibe_explicitamente_copiar_a_mano(self):
        """Sin una prohibición clara el usuario no cambia de costumbre."""
        from reyger.core.backup import AVISO_COPIA_MANUAL

        mayusculas = AVISO_COPIA_MANUAL.upper()
        assert "NO COPIE" in mayusculas
        assert "DATABASE.DB" in mayusculas

    def test_deriva_a_la_api_de_respaldo_de_sqlite(self):
        """El encargo pide nombrar ``Connection.backup()`` explícitamente."""
        from reyger.core.backup import AVISO_COPIA_MANUAL

        assert "Connection.backup()" in AVISO_COPIA_MANUAL

    def test_el_texto_es_una_unica_fuente(self):
        """Las dos ventanas usan el símbolo, no una copia del texto."""
        import inspect

        import reyger.ui.ajustes as mod_ajustes
        import reyger.ui.inventario as mod_inventario

        assert hasattr(mod_inventario, "AVISO_COPIA_MANUAL"), (
            "Inventario debe usar el texto compartido de core.backup"
        )
        fuente = inspect.getsource(mod_inventario)
        # El texto largo no debe estar escrito dentro del módulo.
        assert "los datos más recientes" not in fuente, (
            "Inventario tiene el aviso duplicado en vez de usar "
            "core.backup.AVISO_COPIA_MANUAL"
        )
        fuente_ajustes = inspect.getsource(mod_ajustes)
        assert "los datos más recientes" not in fuente_ajustes, (
            "Ajustes tiene el aviso duplicado en vez de usar "
            "core.backup.AVISO_COPIA_MANUAL"
        )


# ---------------------------------------------------------------------------
# Inventario: el aviso se muestra solo con WAL
# ---------------------------------------------------------------------------


class TestExportarDesdeInventario:
    """``Inventario.exportar_bd_rapido``."""

    def _inventario(self):
        from reyger.ui.inventario import Inventario

        ventana = object.__new__(Inventario)
        ventana.btn_exportar_bd = _WidgetFalso()
        ventana.btn_importar_bd = _WidgetFalso()
        return ventana

    def test_con_wal_activo_pregunta_antes_de_exportar(self):
        from reyger.core.backup import AVISO_COPIA_MANUAL

        ventana = self._inventario()
        with patch("reyger.ui.inventario.wal_activo", return_value=True), \
             patch("reyger.ui.inventario.filedialog.asksaveasfilename",
                   return_value="/tmp/x.db"), \
             patch("reyger.ui.inventario.messagebox") as caja, \
             patch("reyger.ui.inventario.exportar_sqlite") as exportar, \
             patch("reyger.ui.inventario.en_hilo", _en_hilo_sincrono):
            caja.askyesno.return_value = False
            ventana.exportar_bd_rapido()

        caja.askyesno.assert_called_once()
        assert caja.askyesno.call_args.args[1] == AVISO_COPIA_MANUAL
        exportar.assert_not_called(), "Si se cancela, no se exporta"

    def test_sin_wal_no_muestra_el_aviso(self):
        """En modo ``delete`` una copia manual es válida: el aviso sería ruido."""
        ventana = self._inventario()
        with patch("reyger.ui.inventario.wal_activo", return_value=False), \
             patch("reyger.ui.inventario.filedialog.asksaveasfilename",
                   return_value="/tmp/x.db"), \
             patch("reyger.ui.inventario.messagebox") as caja, \
             patch("reyger.ui.inventario.exportar_sqlite") as exportar, \
             patch("reyger.ui.inventario.en_hilo", _en_hilo_sincrono):
            ventana.exportar_bd_rapido()

        caja.askyesno.assert_not_called()
        exportar.assert_called_once()

    def test_aceptando_el_aviso_se_exporta(self):
        ventana = self._inventario()
        with patch("reyger.ui.inventario.wal_activo", return_value=True), \
             patch("reyger.ui.inventario.filedialog.asksaveasfilename",
                   return_value="/tmp/x.db"), \
             patch("reyger.ui.inventario.messagebox") as caja, \
             patch("reyger.ui.inventario.exportar_sqlite") as exportar, \
             patch("reyger.ui.inventario.en_hilo", _en_hilo_sincrono):
            caja.askyesno.return_value = True
            ventana.exportar_bd_rapido()

        exportar.assert_called_once()


class _WidgetFalso:
    def config(self, **_kwargs):
        pass


def _en_hilo_sincrono(_self, trabajo, _al_terminar=None):
    """Ejecuta el trabajo en el acto.

    Parchear ``en_hilo`` a un no-op haría que ``trabajo`` nunca se llamase y
    las aserciones sobre la exportación no significarían nada.
    """
    return trabajo()


class _VarFalso:
    """Sustituto de ``tk.StringVar``.

    No se usa el real porque crear una ``Variable`` de Tk exige una ventana
    raíz, que en la suite headless no existe.
    """

    def __init__(self, valor):
        self._valor = valor

    def get(self):
        return self._valor


# ---------------------------------------------------------------------------
# Ajustes: la ruta que se quedaba sin aviso
# ---------------------------------------------------------------------------


class TestExportarDesdeAjustes:
    """Ajustes → Base de datos → Exportar, formato ``db``."""

    def _ajustes(self):
        from reyger.ui.ajustes import Ajustes

        ventana = object.__new__(Ajustes)
        ventana.btn_exportar_bd = _WidgetFalso()
        ventana.btn_importar_bd = _WidgetFalso()
        # ``_ocupar_botones_bd`` recorre esta lista al lanzar el trabajo.
        ventana.botones_datos = []
        return ventana

    def _exportar(self, formato, wal, confirmar):
        """Dispara ``Ajustes.exportar_base_datos`` con el formato dado."""
        from reyger.core import backup as mod_backup

        ventana = self._ajustes()
        ventana.var_formato_bd = _VarFalso(formato)
        ventana.var_encriptar_bd = _VarFalso(False)
        with patch("reyger.ui.ajustes.filedialog.asksaveasfilename",
                   return_value="/tmp/x.db"), \
             patch("reyger.ui.ajustes.messagebox") as caja, \
             patch("reyger.core.db.wal_activo", return_value=wal), \
             patch.object(mod_backup, "exportar_sqlite") as exportar, \
             patch.object(mod_backup, "exportar_excel"), \
             patch.object(mod_backup, "exportar_csv_zip"), \
             patch("reyger.ui.ajustes.en_hilo", _en_hilo_sincrono):
            caja.askyesno.return_value = confirmar
            ventana.exportar_base_datos()
        return caja, exportar

    def test_con_wal_activo_avisa_antes_de_exportar_la_base(self):
        from reyger.core.backup import AVISO_COPIA_MANUAL

        caja, exportar = self._exportar("db", True, False)

        caja.askyesno.assert_called_once()
        assert caja.askyesno.call_args.args[1] == AVISO_COPIA_MANUAL
        exportar.assert_not_called(), "Si se cancela, no se exporta"

    def test_sin_wal_no_avisa(self):
        caja, exportar = self._exportar("db", False, True)

        caja.askyesno.assert_not_called()
        exportar.assert_called_once()

    def test_el_aviso_no_bloquea_los_otros_formatos(self):
        """Excel y CSV no son copias binarias: el aviso de WAL no aplica."""
        caja, exportar = self._exportar("excel", True, True)

        caja.askyesno.assert_not_called()


# ---------------------------------------------------------------------------
# La copia interna es realmente segura
# ---------------------------------------------------------------------------


class TestLaCopiaInternaEsSegura:
    """Lo que la UI promete tiene que ser verdad: usar ``backup()``."""

    def test_exportar_sqlite_usa_la_api_de_respaldo(self, tmp_path):
        """La exportación ``.db`` no copia el fichero a pelo."""
        import sqlite3

        from reyger.core import backup as mod_backup
        import reyger.core.db as mod_db

        origen = tmp_path / "origen.db"
        conexion = sqlite3.connect(origen)
        conexion.execute("CREATE TABLE prueba (id INTEGER PRIMARY KEY, v TEXT)")
        conexion.execute("INSERT INTO prueba (v) VALUES ('dato')")
        conexion.commit()
        # WAL activo y una fila solo en el WAL: copiar el fichero a mano la
        # perdería, la API de respaldo no.
        conexion.execute("PRAGMA journal_mode = WAL")
        conexion.execute("INSERT INTO prueba (v) VALUES ('solo-en-wal')")
        conexion.commit()

        destino = tmp_path / "destino.db"
        # backup.py hace ``from ..resources import get_db_path``: el símbolo
        # está ligado en ese módulo, así que hay que parchearlo ahí.
        anterior = mod_backup.get_db_path
        mod_backup.get_db_path = lambda: str(origen)
        try:
            mod_backup.exportar_sqlite(str(destino))
        finally:
            mod_backup.get_db_path = anterior
            conexion.close()

        copia = sqlite3.connect(destino)
        try:
            filas = {
                f[0] for f in copia.execute("SELECT v FROM prueba")
            }
        finally:
            copia.close()

        assert "dato" in filas
        assert "solo-en-wal" in filas, (
            "La exportación perdió lo que solo estaba en el WAL: la copia "
            "no se hizo con la API de respaldo"
        )
