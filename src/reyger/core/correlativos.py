"""Correlatividad fiscal de documentos (tickets y facturas) a prueba de retroceso.

La normativa exige que una vez emitido un número correlativo oficial,
la secuencia **nunca** retroceda. Para garantizarlo no basta con calcular
``MAX(...) + 1`` sobre las ventas: si un usuario borra físicamente la
venta con el número más alto, el máximo se reduce y se reutilizaría un
número ya emitido (invalidando la integridad fiscal).

Por eso se usa una tabla de contadores persistentes
(``contadores_documentos``) donde se guarda el **último número oficial
asignado** para cada tipo de documento y serie. El siguiente número se
calcula siempre como ``max(contador + 1, maximo_existente + 1)``, de modo
que la secuencia únicamente puede avanzar.
"""

from . import db


def _serie(tipo):
    """Serie configurada para el tipo ('ticket' o 'factura')."""
    try:
        from ..ui import business_profile as bp

        campo = "numero_serie_ticket" if tipo == "ticket" else "numero_serie_factura"
        return bp.obtener_campo(campo) or ("T-" if tipo == "ticket" else "F-")
    except Exception:
        # Base sin migrar (p. ej. en tests que instancian la UI sin llamar a
        # ensure_database()): usa la serie por defecto del tipo.
        return "T-" if tipo == "ticket" else "F-"


def _limpiar_serie(serie):
    """Deja la serie sin el número inicial (solo el prefijo literal)."""
    return "".join(ch for ch in str(serie or "") if not ch.isdigit())


def _inicio_numero(serie):
    """Extrae el número inicial embebido en la serie (p. ej. 'T-100' -> 100)."""
    try:
        return int("".join(ch for ch in str(serie or "") if ch.isdigit()) or "1")
    except (ValueError, TypeError):
        return 1


def _ultimo_registrado(tipo, prefijo):
    """Último número oficial ya asignado según la tabla de contadores."""
    try:
        fila = db.query_one(
            "SELECT ultimo_numero FROM contadores_documentos WHERE tipo = ? AND serie = ?",
            (tipo, prefijo),
        )
        return int(fila["ultimo_numero"]) if fila else 0
    except Exception:
        # Tabla aún no migrada: no hay contador persistente, se parte de 0.
        return 0


def _maximo_en_ventas(tipo, prefijo):
    """Máximo número ya usado en la tabla de ventas para este tipo/serie.

    Se usa como red de seguridad adicional (p. ej. instalaciones migradas
    donde la tabla de contadores aún no refleja datos manuales).
    """
    try:
        if tipo == "ticket":
            fila = db.query_one(
                "SELECT MAX(CAST(REPLACE(numero_ticket, ?, '') AS INTEGER)) AS maximo "
                "FROM ventas WHERE numero_ticket LIKE ? AND estado = 'emitido'",
                (prefijo, prefijo + "%"),
            )
        else:
            fila = db.query_one(
                "SELECT MAX(CAST(REPLACE(factura, ?, '') AS INTEGER)) AS maximo "
                "FROM ventas WHERE factura LIKE ? AND estado = 'emitido' "
                "AND factura NOT LIKE 'BORRADOR%'",
                (prefijo, prefijo + "%"),
            )
        return int(fila["maximo"]) if fila and fila["maximo"] is not None else 0
    except Exception:
        # Columna/estado no existentes en bases antiguas.
        return 0


def siguiente_numero(tipo):
    """Devuelve el siguiente número correlativo oficial para *tipo*.

    *tipo* es ``'ticket'`` o ``'factura'``. El resultado nunca puede
    retroceder: se toma el mayor entre (a) el contador persistente + 1,
    (b) el máximo ya presente en ventas + 1, y (c) el número inicial
    configurado en la serie.
    """
    serie_configurada = _serie(tipo)
    prefijo = _limpiar_serie(serie_configurada) or ("T-" if tipo == "ticket" else "F-")
    inicio = _inicio_numero(serie_configurada) or 1

    contador = _ultimo_registrado(tipo, prefijo)
    maximo_ventas = _maximo_en_ventas(tipo, prefijo)

    siguiente = max(contador + 1, maximo_ventas + 1, inicio)
    return prefijo, siguiente


def reservar_numero(tipo, numero, prefijo):
    """Registra *numero* como el último oficial emitido del *tipo*.

    Solo asciende: si la tabla ya guarda un número mayor (por ejemplo un
    reintento fuera de orden), no se deja bajar.
    """
    db.execute(
        "INSERT INTO contadores_documentos (tipo, serie, ultimo_numero) VALUES (?, ?, ?) "
        "ON CONFLICT(tipo, serie) DO UPDATE SET "
        "ultimo_numero = MAX(ultimo_numero, excluded.ultimo_numero)",
        (tipo, prefijo, numero),
    )


def formatear(tipo, numero):
    """Devuelve el número formateado con su serie (p. ej. 'T-0012')."""
    prefijo, _ = siguiente_numero(tipo)
    serie_configurada = prefijo
    return f"{serie_configurada}{numero:04d}"