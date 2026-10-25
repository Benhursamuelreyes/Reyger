"""B4: por qué no se puede copiar ``database.db`` a mano.

Con el modo **WAL** de SQLite, una transacción confirmada se escribe en
``database.db-wal`` y no en ``database.db`` hasta el siguiente checkpoint. Por
eso copiar únicamente ``database.db`` —con el explorador, por correo o con
una nube sincronizada— se lleva una copia **incompleta**: al restaurarla
faltan las ventas y facturas más recientes, sin ningún aviso.

Estos tests fijan ese comportamiento con datos reales, para que el aviso de
la interfaz y la documentación no parezcan una recomendación de estilo:

- la copia manual pierde filas recientes,
- ``core.backup.exportar_sqlite`` (que usa ``Connection.backup()``) no,
- y la interfaz avisa cuando WAL está activo.
"""

import os
import shutil
import sqlite3
import sys

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
sys.path.insert(0, SRC_DIR)


@pytest.fixture
def bd_wal(tmp_path, monkeypatch):
    """Base en WAL con una fila antigua (ya checkpointada) y otra reciente.

    Se separan con un ``wal_checkpoint(TRUNCATE)`` explícito para que la
    diferencia entre ambas copias sea determinista y no dependa del umbral
    automático de auto-checkpoint de SQLite.
    """
    import reyger.core.db as modulo_db

    ruta = str(tmp_path / "database.db")
    conn = sqlite3.connect(ruta)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("CREATE TABLE ventas (id INTEGER PRIMARY KEY, factura TEXT)")
    conn.execute("INSERT INTO ventas (factura) VALUES ('F-0001')")
    conn.commit()
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.execute("INSERT INTO ventas (factura) VALUES ('F-0009')")
    conn.commit()

    monkeypatch.setattr(modulo_db, "get_db_path", lambda: ruta)
    monkeypatch.setattr(modulo_db, "_conexion", None)
    yield ruta, conn
    conn.close()
    modulo_db._conexion = None


# ---------------------------------------------------------------------------
# 1) El riesgo es real, no teórico
# ---------------------------------------------------------------------------


class TestRiesgoDeLaCopiaManual:
    """La copia a mano pierde datos; la de la API no."""

    def test_la_bd_viva_tiene_las_dos_facturas(self, bd_wal):
        _, conn = bd_wal
        assert conn.execute("SELECT COUNT(*) FROM ventas").fetchone()[0] == 2

    def test_existe_el_fichero_wal_sin_checkpoint(self, bd_wal):
        ruta, _ = bd_wal
        assert os.path.exists(ruta + "-wal"), "Sin WAL activo el riesgo no aplica"

    def test_copiar_solo_el_db_pierde_la_factura_reciente(self, bd_wal, tmp_path):
        """Reproduce la pérdida: la copia manual no trae la factura emitida."""
        ruta, _ = bd_wal
        copia = str(tmp_path / "copia_manual.db")

        shutil.copyfile(ruta, copia)

        copiada = sqlite3.connect(copia)
        try:
            facturas = [
                f[0] for f in copiada.execute("SELECT factura FROM ventas ORDER BY id")
            ]
        finally:
            copiada.close()

        assert "F-0001" in facturas, "La fila ya consolidada debe estar"
        assert "F-0009" not in facturas, (
            "Si la copia manual trae la factura reciente, el riesgo documentado "
            "no es real y el aviso sobraría"
        )

    def test_la_exportacion_de_la_app_no_pierde_nada(self, bd_wal, tmp_path):
        """``exportar_sqlite`` vuelca el estado consolidado, WAL incluido."""
        from reyger.core.backup import exportar_sqlite

        ruta, _ = bd_wal
        destino = str(tmp_path / "exportada.db")

        exportar_sqlite(destino, db_path=ruta)

        copiada = sqlite3.connect(destino)
        try:
            facturas = {
                f[0] for f in copiada.execute("SELECT factura FROM ventas")
            }
        finally:
            copiada.close()

        assert facturas == {"F-0001", "F-0009"}, (
            "La exportación de la aplicación debe incluir los datos del WAL"
        )

    def test_la_exportacion_es_una_base_valida(self, bd_wal, tmp_path):
        """El destino se puede abrir y pasar el chequeo de integridad."""
        from reyger.core.backup import exportar_sqlite

        ruta, _ = bd_wal
        destino = str(tmp_path / "exportada.db")
        exportar_sqlite(destino, db_path=ruta)

        copiada = sqlite3.connect(destino)
        try:
            assert copiada.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            copiada.close()


# ---------------------------------------------------------------------------
# 2) El estado de WAL es consultable, no suponible
# ---------------------------------------------------------------------------


class TestEstadoDelJournal:
    """WAL degrada en silencio: hay que poder consultarlo."""

    def test_wal_activo_refleja_el_modo_real(self, bd_wal):
        import reyger.core.db as modulo_db

        assert modulo_db.journal_mode() == "wal"
        assert modulo_db.wal_activo() is True

    def test_sin_wal_wal_activo_es_falso(self, tmp_path):
        """El predicado distingue cualquier modo distinto de WAL.

        La conexión se pasa explícitamente porque ``get_connection()`` fuerza
        WAL en cuanto puede: consultar a la conexión compartida nunca mostraría el
        modo ``delete`` al que se degrada en un USB o una unidad de red.
        """
        import reyger.core.db as modulo_db

        ruta = str(tmp_path / "delete.db")
        conn = sqlite3.connect(ruta)
        try:
            conn.execute("PRAGMA journal_mode = DELETE")
            assert modulo_db.journal_mode(conn) == "delete"
            assert modulo_db.wal_activo(conn) is False
        finally:
            conn.close()

    def test_wal_activo_es_ciudadano_para_cualquier_modo(self, tmp_path):
        """``wal_activo`` solo es True para 'wal', sea cual sea el modo real."""
        import reyger.core.db as modulo_db

        ruta = str(tmp_path / "truncate.db")
        conn = sqlite3.connect(ruta)
        try:
            for modo in ("DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"):
                conn.execute(f"PRAGMA journal_mode = {modo}")
                actual = modulo_db.journal_mode(conn)
                assert modulo_db.wal_activo(conn) == (actual == "wal"), (
                    f"Modo {actual}: wal_activo debería ser {actual == 'wal'}"
                )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 3) La interfaz avisa
# ---------------------------------------------------------------------------


class TestAvisoEnLaInterfaz:
    """``Inventario.exportar_bd_rapido`` avisa cuando el riesgo aplica."""

    def _inventario(self):
        from reyger.ui.inventario import Inventario

        ventana = object.__new__(Inventario)
        ventana._ocupar_botones_bd = lambda _ocupado: None
        return ventana

    def _exportar(self, monkeypatch, wal):
        """Lanza la exportación y devuelve si se preguntó al usuario y qué dijo."""
        preguntas = []

        monkeypatch.setattr("reyger.ui.inventario.wal_activo", lambda: wal)
        monkeypatch.setattr(
            "reyger.ui.inventario.filedialog.asksaveasfilename",
            lambda **_k: "/tmp/exportada.db",
        )
        monkeypatch.setattr(
            "reyger.ui.inventario.en_hilo", lambda *_a, **_k: None
        )
        monkeypatch.setattr(
            "reyger.ui.inventario.messagebox.askyesno",
            lambda titulo, aviso: preguntas.append((titulo, aviso)) or True,
        )
        self._inventario().exportar_bd_rapido()
        return preguntas

    def test_con_wal_activo_avisa_de_no_copiar_el_fichero(self, monkeypatch):
        preguntas = self._exportar(monkeypatch, wal=True)

        assert len(preguntas) == 1, "Con WAL activo debe pedir confirmación"
        _, aviso = preguntas[0]
        lowered = aviso.lower()
        assert "wal" in lowered
        assert "database.db" in aviso
        assert "backup" in lowered or "botón" in lowered

    def test_el_aviso_menciona_los_riesgos_concretos(self, monkeypatch):
        _, aviso = self._exportar(monkeypatch, wal=True)[0]
        lowered = aviso.lower()
        # Lo que hace el usuario tiene que quedar en sus términos.
        assert "-wal" in lowered
        assert "nube" in lowered or "sincroniz" in lowered

    def test_sin_wal_no_avisa_y_no_molesta(self, monkeypatch):
        preguntas = self._exportar(monkeypatch, wal=False)

        assert preguntas == [], (
            "En modo delete una copia manual sería válida: el aviso solo sería ruido"
        )

    def test_si_el_usuario_cancela_no_se_exporta(self, monkeypatch):
        """El aviso es una puerta de verdad: cancelar aborta."""
        exported = []
        monkeypatch.setattr("reyger.ui.inventario.wal_activo", lambda: True)
        monkeypatch.setattr(
            "reyger.ui.inventario.filedialog.asksaveasfilename",
            lambda **_k: "/tmp/exportada.db",
        )
        monkeypatch.setattr(
            "reyger.ui.inventario.messagebox.askyesno",
            lambda *_a, **_k: False,
        )
        monkeypatch.setattr(
            "reyger.ui.inventario.en_hilo",
            lambda _self, fn, _cb: exported.append(fn),
        )

        self._inventario().exportar_bd_rapido()

        assert exported == [], "Cancelar el aviso debe impedir la exportación"
