"""Importación y exportación de la base de datos de Reyger.

Permite al usuario llevarse sus datos (o restaurarlos) en tres formatos:

- **SQLite** (``.db``/``.sqlite``/``.sqlite3``): copia binaria completa y
  fiel de la base, realizada con el API de backup de SQLite (segura aunque
  existan conexiones abiertas).
- **Excel** (``.xlsx``): un libro con una hoja por tabla. Requiere
  ``openpyxl``.
- **CSV comprimido** (``.zip``): un fichero CSV por tabla dentro de un zip.

En la importación:

- Un ``.db`` sustituye la base completa; se valida antes con
  ``PRAGMA integrity_check`` y se exige que contenga las tablas nucleo.
- Los formatos ``.zip`` (CSV) y ``.xlsx`` sustituyen únicamente el
  *contenido* de las tablas reconocidas; las tablas desconocidas se
  ignoran y se informan.

Antes de cualquier importación se genera automáticamente una copia de
seguridad de la base actual (``database_respaldo_YYYYMMDD_HHMMSS.bak``)
junto a ella; se conservan las :data:`MAX_RESPALDOS` más recientes.

Todas las funciones aceptan ``db_path`` para operar sobre otra base
(útil en tests); por defecto trabajan sobre la del usuario.

NUNCA copie ``database.db`` a mano
-----------------------------------
Con el modo **WAL** activo (lo activa ``core.db.get_connection()`` cuando el
sistema de ficheros lo permite) los datos comprometidos también se escriben
en ``database.db-wal`` y ``database.db-shm``. Copiar únicamente
``database.db`` —con el explorador de archivos, por correo, con Drive/Dropbox
sincronizada o copiando y pegando— se lleva un fichero incompleto: al
restaurarlo, las ventas, facturas o clientes más recientes aparecen como
vacíos, o SQLite avisa de que la base está dañada.

Además, WAL degrada **en silencio** a ``delete`` en sistemas de ficheros que
no lo soportan (algunas unidades de red, ciertos USB), de modo que no puede
suponerse ni por el sistema operativo. Compruébese con
``core.db.wal_activo()``.

Use siempre las funciones de este módulo (los botones «Exportar base de
datos…» de Inventario y el respaldo automático previo a cada importación):
todas usan ``sqlite3.Connection.backup()``, que vuelca el estado
consolidado incluyendo el WAL, y son seguras con la base abierta.
"""

import csv
import io
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from openpyxl import Workbook, load_workbook

    EXCEL_DISPONIBLE = True
except ImportError:  # pragma: no cover - depende del entorno
    EXCEL_DISPONIBLE = False

from .db import close as cerrar_conexion_compartida, conectar
from ..resources import get_db_path

MAX_RESPALDOS = 5

#: Subcarpeta (junto a la base) de las copias automáticas diarias, separadas
#: de los respaldos previos a importar para que una rotación no purgue la otra.
CARPETA_RESPALDOS_AUTOMATICOS = "respaldos"
#: Copias automáticas que se conservan: una por día.
DIAS_RESPALDO_AUTOMATICO = 7

EXTENSIONES_SQLITE = (".db", ".sqlite", ".sqlite3")

#: Etiquetas de formato para la interfaz (valor -> descripción/extensión).
FORMATOS_EXPORTACION = {
    "db": ("Base de datos SQLite", ".db"),
    "excel": ("Libro de Excel", ".xlsx"),
    "csv": ("CSV comprimido", ".zip"),
}

#: Objetos que identifican una base de Reyger. ``ventas`` es una tabla hasta
#: el esquema 13 y una vista desde el 14: vale cualquiera de los dos.
TABLAS_NUCLEO = {"ventas", "inventario"}

#: Aviso canónico para la interfaz: no copiar ``database.db`` a mano.
#:
#: Vive aquí, y no duplicado en cada ventana, porque hay más de un punto de
#: exportación (Inventario y Ajustes) y dos textos distintos acabarían
#: divergiendo: es exactamente lo que dejó a la exportación de Ajustes sin
#: advertencia mientras la de Inventario sí la tenía.
#:
#: Solo debe mostrarse con WAL activo (``core.db.wal_activo()``): en modo
#: ``delete`` una copia normal sería válida y el aviso solo sería ruido.
AVISO_COPIA_MANUAL = (
    "La base de datos está en modo WAL: los datos más recientes se guardan "
    "también en un fichero «database.db-wal» aparte.\n\n"
    "NO copie el fichero «database.db» a mano (ni con el explorador, ni por "
    "correo, ni con una nube sincronizada): esa copia saldría incompleta y al "
    "restaurarla faltarían ventas, facturas o clientes.\n\n"
    "Use este botón, que hace la copia con la API de respaldo de SQLite "
    "(sqlite3.Connection.backup()) e incluye los datos pendientes del WAL.\n\n"
    "¿Continuar con la exportación?"
)


class BackupError(Exception):
    """Error validado durante una importación/exportación."""


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------


def _conectar(db_path=None):
    return conectar(db_path or get_db_path())


def _conectar_solo_lectura(ruta):
    """Abre una base en modo lectura pura vía URI (no crea ni recupera)."""
    try:
        return conectar(ruta, solo_lectura=True)
    except sqlite3.Error as e:
        raise BackupError(f"No se pudo abrir «{ruta}»: {e}") from e


def _tablas(conn):
    filas = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    ).fetchall()
    return [fila[0] for fila in filas]


def _leer_tabla(conn, tabla):
    cursor = conn.execute(f'SELECT * FROM "{tabla}"')
    columnas = [d[0] for d in cursor.description]
    filas = cursor.fetchall()
    cursor.close()
    return columnas, filas


def _asegurar_extension(ruta, extension):
    ruta = str(ruta)
    if os.path.splitext(ruta)[1].lower() != extension:
        ruta += extension
    return ruta


def _nombre_hoja(nombre_tabla, usados=None):
    """Nombre válido de hoja Excel: sin []:*?/\\ y de 31 caracteres máximo."""
    hoja = nombre_tabla
    for caracter in '[]:*?/\\':
        hoja = hoja.replace(caracter, "_")
    hoja = hoja[:31] or "Hoja"
    base = hoja
    indice = 2
    while usados is not None and hoja.lower() in usados:
        sufijo = f"~{indice}"
        hoja = base[: 31 - len(sufijo)] + sufijo
        indice += 1
    if usados is not None:
        usados.add(hoja.lower())
    return hoja


# ---------------------------------------------------------------------------
# Exportación
# ---------------------------------------------------------------------------


def exportar_sqlite(destino, db_path=None):
    """Copia binaria completa mediante el API de backup de SQLite.

    Es la **única** forma fiable de llevarse la base. Con WAL activo los
    datos comprometidos siguen en ``database.db-wal``, así que copiar solo
    el fichero ``database.db`` a mano produce una copia incompleta. Aquí
    ``origen_conn.backup(destino_conn)`` vuelca el estado consolidado
    (incluido el WAL) al destino, y además es seguro aunque la base tenga
    conexiones abiertas.
    """
    destino = _asegurar_extension(destino, ".db")
    origen_conn = _conectar(db_path)
    try:
        destino_conn = sqlite3.connect(destino)
        try:
            with destino_conn:
                origen_conn.backup(destino_conn)
        finally:
            destino_conn.close()
    finally:
        origen_conn.close()
    return destino


def exportar_csv_zip(destino, db_path=None):
    """Exporta todas las tablas como CSV (una por miembro) dentro de un zip."""
    destino = _asegurar_extension(destino, ".zip")
    conn = _conectar(db_path)
    try:
        tablas = _tablas(conn)
        if not tablas:
            raise BackupError("La base de datos no contiene tablas.")
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
            for tabla in tablas:
                columnas, filas = _leer_tabla(conn, tabla)
                buffer = io.StringIO()
                writer = csv.writer(buffer)
                writer.writerow(columnas)
                for fila in filas:
                    writer.writerow(["" if v is None else v for v in fila])
                zf.writestr(f"{tabla}.csv", buffer.getvalue())
    finally:
        conn.close()
    return destino


def exportar_excel(destino, db_path=None):
    """Exporta todas las tablas a un libro Excel (una hoja por tabla)."""
    if not EXCEL_DISPONIBLE:
        raise BackupError(
            "El soporte de Excel requiere el paquete 'openpyxl', que no está "
            "instalado en este equipo."
        )
    destino = _asegurar_extension(destino, ".xlsx")
    conn = _conectar(db_path)
    try:
        usados = set()
        libro = Workbook(write_only=True)
        try:
            for tabla in _tablas(conn):
                hoja = libro.create_sheet(_nombre_hoja(tabla, usados))
                columnas, filas = _leer_tabla(conn, tabla)
                hoja.append(columnas)
                for fila in filas:
                    hoja.append(list(fila))
            libro.save(destino)
        finally:
            libro.close()
    finally:
        conn.close()
    return destino


def exportar_datos(destino, db_path=None, encriptado=False):
    """Exporta eligiendo el formato por la extensión de ``destino``.

    Si *encriptado* es ``True`` y el formato es SQLite, genera un
    fichero ``.db.enc`` encriptado con Fernet.
    """
    if encriptado:
        import tempfile
        destino_str = str(destino)
        if not destino_str.endswith(".enc"):
            destino_str += ".enc"
        fd, ruta_tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            exportar_sqlite(ruta_tmp, db_path)
            from .seguridad import cifrar_fichero
            cifrar_fichero(ruta_tmp, destino_str)
            return True, "db_enc"
        except Exception as e:
            raise BackupError(f"Error al encriptar: {e}")
        finally:
            try:
                os.unlink(ruta_tmp)
            except OSError:
                pass

    extension = os.path.splitext(str(destino))[1].lower()
    if extension in EXTENSIONES_SQLITE:
        return exportar_sqlite(destino, db_path), "db"
    if extension == ".xlsx":
        return exportar_excel(destino, db_path), "excel"
    if extension == ".zip":
        return exportar_csv_zip(destino, db_path), "csv"
    raise BackupError(
        f"Extensión no reconocida: «{extension or destino}». "
        "Use .db, .xlsx o .zip."
    )


# ---------------------------------------------------------------------------
# Respaldos automáticos previos a importar
# ---------------------------------------------------------------------------


def respaldar_bd_actual(db_path=None):
    """Copia la base actual a ``database_respaldo_<fecha>.bak``.

    Devuelve la ruta del respaldo o ``None`` si la base aún no existe.
    Conserva solo las :data:`MAX_RESPALDOS` copias más recientes.

    La copia se hace con la API de respaldo de SQLite, no copiando el
    fichero a pelo: en modo WAL los últimos datos committeados viven en
    ``database.db-wal`` hasta el siguiente checkpoint, así que
    ``shutil.copy2`` produciría un respaldo al que le faltan ventas.
    """
    origen = Path(str(db_path or get_db_path()))
    if not origen.exists():
        return None
    sello = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destino = origen.parent / f"database_respaldo_{sello}.bak"
    _volcar(origen, destino)
    _purgar_respaldos(origen.parent)
    return str(destino)


def _volcar(origen, destino):
    """Vuelca la base *origen* en el fichero *destino* (incluido el WAL)."""
    # Se reaprovecha la conexión ya viva si existe: es la que ve los
    # datos recién committeados y no fuerza un checkpoint en el WAL.
    from . import db as _db

    origen_con = getattr(_db, "_conexion", None)
    if origen_con is not None:
        destino_con = sqlite3.connect(str(destino))
        try:
            origen_con.backup(destino_con)
        finally:
            destino_con.close()
    else:
        fuente = conectar(origen)
        destino_con = sqlite3.connect(str(destino))
        try:
            fuente.backup(destino_con)
        finally:
            fuente.close()
            destino_con.close()
    shutil.copystat(origen, destino)


def comprobar_integridad(ruta):
    """Devuelve los problemas que encuentra ``PRAGMA integrity_check`` y las
    claves foráneas rotas en la base *ruta* (lista vacía si está bien)."""
    conn = sqlite3.connect(str(ruta))
    try:
        problemas = [
            fila[0] for fila in conn.execute("PRAGMA integrity_check") if fila[0] != "ok"
        ]
        problemas += [
            f"clave foránea rota en {fila[0]} (fila {fila[1]})"
            for fila in conn.execute("PRAGMA foreign_key_check")
        ]
        return problemas
    finally:
        conn.close()


def respaldo_automatico(db_path=None, hoy=None):
    """Guarda la copia automática del día y devuelve su ruta.

    Hay una copia por día (``respaldos/automatico_AAAAMMDD.db``): si se
    llama varias veces el mismo día se sobrescribe, de modo que la última
    incluye todas las ventas de la jornada. Se escribe en un temporal y se
    renombra al final: si el proceso se corta a medias, la copia anterior del
    día sigue intacta. Conserva las :data:`DIAS_RESPALDO_AUTOMATICO` más
    recientes. Devuelve ``None`` si la base aún no existe.

    La copia se verifica con ``PRAGMA integrity_check`` antes de sustituir a
    la anterior: si está dañada (es decir, la base lo está) se conserva la
    copia buena previa y se lanza :class:`BackupError`.
    """
    origen = Path(str(db_path or get_db_path()))
    if not origen.exists():
        return None
    carpeta = origen.parent / CARPETA_RESPALDOS_AUTOMATICOS
    carpeta.mkdir(exist_ok=True)
    dia = (hoy or datetime.now()).strftime("%Y%m%d")
    destino = carpeta / f"automatico_{dia}.db"
    temporal = destino.with_name(destino.name + ".tmp")
    try:
        _volcar(origen, temporal)
        problemas = comprobar_integridad(temporal)
        if problemas:
            raise BackupError(
                "La base de datos tiene errores de integridad; no se ha "
                "sustituido la copia anterior. Detalle: " + "; ".join(problemas[:5])
            )
        os.replace(temporal, destino)
    finally:
        if temporal.exists():
            temporal.unlink()
    for viejo in sorted(carpeta.glob("automatico_*.db"))[:-DIAS_RESPALDO_AUTOMATICO]:
        try:
            viejo.unlink()
        except OSError:
            pass
    return str(destino)


def _purgar_respaldos(carpeta):
    respaldos = sorted(carpeta.glob("database_respaldo_*.bak"))
    for viejo in respaldos[: max(0, len(respaldos) - MAX_RESPALDOS)]:
        try:
            viejo.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Importación
# ---------------------------------------------------------------------------


def _validar_bd_origen(ruta):
    try:
        conn = _conectar_solo_lectura(ruta)
    except sqlite3.Error as e:
        raise BackupError(f"«{ruta}» no es una base de datos válida ({e}).") from e
    try:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if resultado != "ok":
            raise BackupError(
                f"La base de datos está corrupta (integrity_check: {resultado})."
            )
        presentes = {
            fila[0] for fila in conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
            )
        }
        faltantes = TABLAS_NUCLEO - presentes
        if faltantes:
            raise BackupError(
                "El fichero no parece una base de datos de Reyger: faltan "
                "las tablas " + ", ".join(sorted(faltantes)) + "."
            )
        from .migrations import LATEST_VERSION

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version > LATEST_VERSION:
            raise BackupError(
                "La base pertenece a una versión más moderna de Reyger "
                f"(esquema {version} > {LATEST_VERSION}) y no puede "
                "importarse en esta instalación."
            )
    except sqlite3.DatabaseError as e:
        raise BackupError(
            f"«{ruta}» no es una base de datos SQLite válida ({e})."
        ) from e
    finally:
        conn.close()


def importar_sqlite(ruta_origen, db_path=None):
    """Sustituye la base completa por ``ruta_origen`` tras validarla.

    Cierra la conexión compartida antes de sobrescribir (imprescindible en
    Windows) y aplica las migraciones pendientes en el acto; si estas
    fallan, restaura automáticamente el estado anterior.
    """
    destino = Path(str(db_path or get_db_path()))
    _validar_bd_origen(ruta_origen)
    respaldo = respaldar_bd_actual(str(destino))
    cerrar_conexion_compartida()

    temporal = destino.with_name(destino.name + ".importando")
    shutil.copyfile(str(ruta_origen), temporal)

    from .migrations import run_migrations

    try:
        conn = sqlite3.connect(temporal)
        try:
            run_migrations(conn)
        finally:
            conn.close()
    except Exception as e:
        temporal.unlink(missing_ok=True)
        raise BackupError(
            "La base importada no pudo actualizarse al esquema actual y no "
            f"se aplicó ningún cambio ({e})."
        ) from e

    os.replace(temporal, destino)
    return respaldo


def _es_fila_vacia(fila):
    """Devuelve ``True`` si la fila no contiene ninguna celda con valor.

    Se considera vacía una fila formada solo por ``None`` o celdas en
    blanco (incluidos espacios); una celda numérica (0, False) cuenta
    como contenido.
    """
    return not any(v is not None and str(v).strip() != "" for v in fila)


def _celda_segura(fila, indice, nombre_col):
    """Lee la celda en ``indice`` de una fila sin desbordar el índice.

    Si la fila es más corta que la cabecera, la columna se trata como
    opcional y se devuelve ``None`` (no se lanza ``IndexError``). Las
    celdas vacías (``""``) también se convierten a ``None``.
    """
    if indice < 0 or indice >= len(fila):
        return None
    valor = fila[indice]
    return None if valor == "" else valor


def _leer_csv_zip(ruta):
    datos = {}
    try:
        with zipfile.ZipFile(ruta) as zf:
            for nombre in zf.namelist():
                if not nombre.lower().endswith(".csv"):
                    continue
                tabla = os.path.splitext(os.path.basename(nombre))[0]
                with zf.open(nombre) as f:
                    lector = csv.reader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                    filas = [
                        fila for fila in lector if not _es_fila_vacia(fila)
                    ]
                if filas:
                    datos[tabla] = filas
    except zipfile.BadZipFile as e:
        raise BackupError("El fichero .zip no es válido o está dañado.") from e
    if not datos:
        raise BackupError("El zip no contiene ningún fichero CSV.")
    return datos


def _leer_excel(ruta):
    if not EXCEL_DISPONIBLE:
        raise BackupError(
            "El soporte de Excel requiere el paquete 'openpyxl', que no está "
            "instalado en este equipo."
        )
    try:
        libro = load_workbook(str(ruta), read_only=True, data_only=True)
    except Exception as e:
        raise BackupError(f"No se pudo abrir el libro de Excel: {e}") from e
    try:
        if not libro.worksheets:
            raise BackupError(
                "El libro de Excel no contiene ninguna hoja de cálculo."
            )
        datos = {}
        for hoja in libro.worksheets:
            filas = [
                list(fila)
                for fila in hoja.iter_rows(values_only=True)
                if fila is not None and not _es_fila_vacia(fila)
            ]
            if filas:
                datos[hoja.title] = filas
    finally:
        libro.close()
    if not datos:
        raise BackupError(
            "El libro de Excel no contiene datos exportables "
            "(las hojas están vacías)."
        )
    return datos


def _importar_tabla(conn, tabla, filas, existentes, ignoradas, resumen):
    """Inserta las filas de una hoja/CSV en ``tabla``.

    Las columnas se emparejan por *nombre* de la cabecera (la primera fila),
    no por su posición: el orden de columnas en el fichero no importa. Las
    columnas cuyo nombre no exista en el esquema se descartan, las filas
    más cortas que la cabecera se toleran (la celda ausente se deja en
    ``NULL``) y las tablas desconocidas se informan como ignoradas.
    """
    if tabla not in existentes:
        ignoradas.append(tabla)
        return
    if len(filas) < 2:
        return
    cabecera = [str(c) for c in filas[0]]
    if not cabecera or all(not str(c).strip() for c in cabecera):
        raise BackupError(
            f"La hoja «{tabla}» no tiene una cabecera válida en su primera "
            "fila. Escribe en la primera fila el nombre de cada columna y "
            "vuelve a intentarlo."
        )
    info = conn.execute(f'PRAGMA table_info("{tabla}")').fetchall()
    columnas_reales = [fila[1] for fila in info]
    # Excel y CSV no distinguen un texto vacío de una celda vacía: un
    # proveedor '' (los productos del registro rápido) volvía como NULL e
    # impedía restaurar la copia entera. En las columnas de texto NOT NULL
    # sin valor por defecto, la celda vacía se restaura como ''.
    # PRAGMA table_info: (cid, nombre, tipo, notnull, valor_por_defecto, pk)
    texto_obligatorio = {
        nombre for _, nombre, tipo, notnull, defecto, _ in info
        if notnull and defecto is None
        and any(t in (tipo or "").upper() for t in ("TEXT", "CHAR", "CLOB"))
    }
    mapa = [
        (indice, nombre)
        for indice, nombre in enumerate(cabecera)
        if nombre in columnas_reales
    ]
    if not mapa:
        ignoradas.append(tabla)
        return
    columnas_sql = ", ".join(f'"{c}"' for _, c in mapa)
    marcadores = ", ".join("?" for _ in mapa)
    conn.execute(f'DELETE FROM "{tabla}"')
    insertada = 0
    for fila in filas[1:]:
        valores = [
            _celda_segura(fila, indice, nombre) for indice, nombre in mapa
        ]
        valores = [
            "" if v is None and nombre in texto_obligatorio else v
            for v, (_, nombre) in zip(valores, mapa)
        ]
        conn.execute(
            f'INSERT INTO "{tabla}" ({columnas_sql}) '
            f"VALUES ({marcadores})",
            valores,
        )
        insertada += 1
    resumen[tabla] = insertada


def _importar_ventas_legado(conn, filas, resumen):
    """Convierte una hoja «ventas» del formato antiguo a documentos/líneas.

    Se hace después de importar el resto de hojas, para que los clientes y
    productos de la misma copia ya existan al enlazarlos.
    """
    from .documentos import convertir_ventas_legado

    if len(filas) < 2:
        return
    # (índice en la hoja, nombre): las columnas sin cabecera se descartan
    # sin desplazar las demás.
    cabecera = [
        (i, str(c).strip()) for i, c in enumerate(filas[0])
        if c is not None and str(c).strip()
    ]
    if not cabecera:
        return
    columnas = ", ".join(f'"{nombre}"' for _, nombre in cabecera)
    conn.execute(f"CREATE TEMP TABLE ventas_legado ({columnas})")
    try:
        conn.executemany(
            f"INSERT INTO ventas_legado VALUES ({', '.join('?' * len(cabecera))})",
            [
                [_celda_segura(fila, i, nombre) for i, nombre in cabecera]
                for fila in filas[1:]
                if not _es_fila_vacia(fila)
            ],
        )
        conn.execute("DELETE FROM lineas_documento")
        conn.execute("DELETE FROM documentos")
        convertido = convertir_ventas_legado(conn, "ventas_legado")
    finally:
        conn.execute("DROP TABLE temp.ventas_legado")
    resumen["documentos"] = convertido["documentos"]
    resumen["lineas_documento"] = convertido["lineas"]


def importar_tablas(datos, db_path=None):
    """Sustituye el contenido de las tablas reconocidas en ``datos``.

    ``datos`` mapea ``{tabla: [[cabecera], [fila], ...]}``. Las columnas se
    emparejan por nombre; las que no existan en el esquema actual se
    descartan y las tablas desconocidas se informan. Todo se ejecuta en una
    única transacción: si algo falla, no se altera nada.
    """
    destino = str(db_path or get_db_path())
    respaldo = respaldar_bd_actual(destino)
    conn = conectar(destino)
    resumen = {}
    ignoradas = []
    # Copias anteriores al esquema 14 traen una hoja «ventas» (una fila por
    # línea). Hoy ``ventas`` es una vista: se convierte a documentos/líneas
    # en vez de ignorarla, salvo que la copia ya traiga «documentos».
    ventas_legado = datos.get("ventas") if "documentos" not in datos else None
    datos = {tabla: filas for tabla, filas in datos.items() if tabla != "ventas"}
    try:
        existentes = set(_tablas(conn))

        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            tabla_actual = ""
            for tabla, filas in datos.items():
                tabla_actual = tabla
                _importar_tabla(
                    conn, tabla, filas, existentes, ignoradas, resumen
                )
            if ventas_legado:
                tabla_actual = "ventas"
                _importar_ventas_legado(conn, ventas_legado, resumen)
            conn.commit()
        except (IndexError, KeyError) as e:
            conn.rollback()
            raise BackupError(
                "El fichero tiene una estructura no válida en la hoja "
                f"«{tabla_actual}»: a alguna fila le falta una columna. "
                "Comprueba que la primera fila sea la cabecera con los "
                "nombres de las columnas."
            ) from e
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute("PRAGMA foreign_keys = ON")
    except sqlite3.IntegrityError as e:
        raise BackupError(
            "El fichero contiene celdas vacías o valores no válidos para "
            "alguna columna obligatoria de la base. Revísalo e inténtalo de "
            "nuevo (no se ha modificado nada)."
        ) from e
    except sqlite3.Error as e:
        raise BackupError(f"Error importando datos: {e}") from e
    finally:
        conn.close()
    return resumen, ignoradas, respaldo


def importar_datos(ruta_origen, db_path=None):
    """Importa ``ruta_origen`` detectando el formato por su extensión.

    Devuelve un diccionario normalizado::

        {"modo": "completa"|"tablas", "respaldo": str|None,
         "resumen": {tabla: filas}, "ignoradas": [tablas]}
    """
    ruta_origen = str(ruta_origen)
    if not os.path.exists(ruta_origen):
        raise BackupError(f"No existe el fichero «{ruta_origen}».")

    if ruta_origen.endswith(".enc"):
        try:
            from .seguridad import descifrar_fichero
            ruta_descifrada = descifrar_fichero(ruta_origen)
            resultado = importar_datos(ruta_descifrada, db_path)
            try:
                os.unlink(ruta_descifrada)
            except OSError:
                pass
            resultado["encriptado"] = True
            return resultado
        except Exception as e:
            raise BackupError(f"Error al descifrar el backup: {e}")

    extension = os.path.splitext(ruta_origen)[1].lower()
    if extension in EXTENSIONES_SQLITE:
        respaldo = importar_sqlite(ruta_origen, db_path)
        return {
            "modo": "completa",
            "respaldo": respaldo,
            "resumen": {},
            "ignoradas": [],
        }
    try:
        if extension == ".zip":
            datos = _leer_csv_zip(ruta_origen)
        elif extension == ".xlsx":
            datos = _leer_excel(ruta_origen)
        else:
            raise BackupError(
                f"Formato no reconocido («{extension}»). Use .db, .sqlite, "
                ".sqlite3, .xlsx o .zip."
            )
        resumen, ignoradas, respaldo = importar_tablas(datos, db_path)
    except (IndexError, KeyError) as e:
        raise BackupError(
            "El archivo no tiene la estructura esperada (faltan columnas u "
            "hojas). Comprueba que la primera fila de cada hoja sea la "
            "cabecera con los nombres de las columnas."
        ) from e
    return {
        "modo": "tablas",
        "respaldo": respaldo,
        "resumen": resumen,
        "ignoradas": ignoradas,
    }
