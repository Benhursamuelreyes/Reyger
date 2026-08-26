"""Motor de hashing SHA-256 conforme a las especificaciones AEAT VeriFactu.

Implementa el cálculo de huellas digitales (``Huella``) según la
especificación v0.1.2 (27/08/2024) de la Agencia Tributaria.

Formato de la cadena de valores (Registro de Alta):
    ``IDEmisorFactura=NIF&NumSerieFactura=NUM&FechaExpedicionFactura=DD-MM-YYYY&TipoFactura=TIPO&CuotaTotal=CUOTA&ImporteTotal=IMPORTE&Huella=HASH_ANT&FechaHoraHusoGenRegistro=ISO8601``

Reglas:
    - Campos separados por ``&``
    - Nombre y valor separados por ``=``
    - Codificación UTF-8, salida hex mayúsculas (64 caracteres)
    - ``Huella`` vacía si es el primer registro de la cadena
    - Fecha: ``DD-MM-YYYY``
    - Timestamp: ISO 8601 con offset de timezone (``YYYY-MM-DDThh:mm:ss+hh:mm``)
"""

import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

from ..core import db
from ..ui import business_profile as bp


def _formato_fecha_aeat(fecha: str) -> str:
    """Convierte una fecha a formato AEAT ``DD-MM-YYYY``.

    Acepta ``DD/MM/YYYY``, ``DD-MM-YYYY`` o ``YYYY-MM-DD``.
    """
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(fecha, fmt).strftime("%d-%m-%Y")
        except ValueError:
            continue
    return fecha


def _formato_timestamp_aeat(fecha_hora: Optional[str] = None) -> str:
    """Genera timestamp ISO 8601 con timezone para AEAT.

    Si se proporciona *fecha_hora*, la usa; en caso contrario usa la
    hora actual con timezone de España (CET/CEST = UTC+1/+2).
    """
    if fecha_hora:
        return fecha_hora
    tz_es = timezone(timedelta(hours=2))
    ahora = datetime.now(tz_es)
    return ahora.strftime("%Y-%m-%dT%H:%M:%S+02:00")


def construir_cadena_valores(
    nif: str,
    num_serie: str,
    fecha: str,
    tipo_comprobante: str,
    cuota_total: float,
    importe_total: float,
    huella_anterior: str,
    fecha_hora_gen: Optional[str] = None,
) -> str:
    """Construye la cadena de valores exacta según la spec AEAT.

    Devuelve la cadena tal cual se hashea, sin espacios extra.
    """
    campos = [
        ("IDEmisorFactura", nif.upper().strip()),
        ("NumSerieFactura", num_serie.strip()),
        ("FechaExpedicionFactura", _formato_fecha_aeat(fecha)),
        ("TipoFactura", tipo_comprobante.upper().strip()),
        ("CuotaTotal", f"{cuota_total:.2f}"),
        ("ImporteTotal", f"{importe_total:.2f}"),
        ("Huella", huella_anterior if huella_anterior else ""),
        ("FechaHoraHusoGenRegistro", _formato_timestamp_aeat(fecha_hora_gen)),
    ]
    return "&".join(f"{nombre}={valor}" for nombre, valor in campos)


def calcular_huella(
    nif: str,
    num_serie: str,
    fecha: str,
    tipo_comprobante: str,
    cuota_total: float,
    importe_total: float,
    huella_anterior: str,
    fecha_hora_gen: Optional[str] = None,
) -> str:
    """Calcula la huella SHA-256 de un registro VeriFactu.

    Devuelve el hash en hexadecimal mayúsculas (64 caracteres).
    """
    cadena = construir_cadena_valores(
        nif, num_serie, fecha, tipo_comprobante,
        cuota_total, importe_total, huella_anterior, fecha_hora_gen,
    )
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest().upper()


def obtener_huella_anterior(numero_series: Optional[str] = None) -> tuple[str, str, str]:
    """Obtiene la huella, número de serie y fecha de la última factura de la serie.

    Devuelve ``(huella, numero_serie, fecha)`` de la factura más reciente.
    Si no hay facturas previas, devuelve cadenas vacías.
    """
    serie = numero_series or bp.obtener_campo("numero_series") or "A"
    fila = db.query_one(
        "SELECT numero_factura, fecha, huella FROM facturas_verifactu "
        "WHERE numero_factura LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{serie}-%",),
    )
    if fila is None:
        return "", "", ""
    return (fila["huella"] or "", fila["numero_factura"], fila["fecha"])


def calcular_huella_para_factura(
    nif: str,
    num_serie: str,
    fecha: str,
    tipo_comprobante: str,
    cuota_total: float,
    importe_total: float,
    fecha_hora_gen: Optional[str] = None,
) -> tuple[str, str, str, str]:
    """Calcula huella completa para una factura: hash, cadena, huella anterior y orden.

    Devuelve ``(huella, cadena_valores, huella_anterior, fecha_generacion)``.
    """
    huella_ant, _, _ = obtener_huella_anterior()
    fecha_gen = _formato_timestamp_aeat(fecha_hora_gen)

    cadena = construir_cadena_valores(
        nif, num_serie, fecha, tipo_comprobante,
        cuota_total, importe_total, huella_ant, fecha_gen,
    )
    huella = hashlib.sha256(cadena.encode("utf-8")).hexdigest().upper()

    return huella, cadena, huella_ant, fecha_gen


def generar_url_qr(
    nif: str,
    num_serie: str,
    fecha: str,
    importe_total: float,
    produccion: bool = False,
) -> str:
    """Genera la URL del código QR según la spec AEAT VeriFactu.

    Producción:  https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?...
    Preproducción: https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR?...
    """
    base = (
        "https://www2.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR"
        if produccion
        else "https://prewww2.aeat.es/wlpl/TIKE-CONT/ValidarQR"
    )
    num_serie_qr = num_serie.replace("&", "%26")
    fecha_aeat = _formato_fecha_aeat(fecha)
    return (
        f"{base}?nif={nif.upper()}"
        f"&numserie={num_serie_qr}"
        f"&fecha={fecha_aeat}"
        f"&importe={importe_total:.2f}"
    )


def verificar_cadena() -> list[dict]:
    """Verifica la integridad de toda la cadena de hash.

    Devuelve una lista de diccionarios con el resultado de la
    verificación de cada factura. Si ``ok`` es ``False``, la cadena
    está rota en esa factura.
    """
    filas = db.query(
        "SELECT id, numero_factura, fecha, huella, huella_anterior, "
        "nif_emisor, tipo_comprobante, total_iva, total, "
        "cadena_valores, numero_ord, fecha_generacion "
        "FROM facturas_verifactu ORDER BY numero_ord ASC, id ASC"
    )
    resultados = []
    hash_esperado_anterior = ""

    for fila in filas:
        ok = True
        errores = []

        if fila["huella_anterior"] != hash_esperado_anterior:
            ok = False
            errores.append(
                f"huella_anterior mismatch: esperado '{hash_esperado_anterior}', "
                f"obtenido '{fila['huella_anterior']}'"
            )

        cadena_recalculada = construir_cadena_valores(
            fila["nif_emisor"],
            fila["numero_factura"],
            fila["fecha"],
            fila["tipo_comprobante"],
            fila["total_iva"],
            fila["total"],
            fila["huella_anterior"],
            fila["fecha_generacion"],
        )
        hash_recalculado = hashlib.sha256(
            cadena_recalculada.encode("utf-8")
        ).hexdigest().upper()

        if hash_recalculado != fila["huella"]:
            ok = False
            errores.append(
                f"huella mismatch: recalculado '{hash_recalculado}', "
                f"almacenado '{fila['huella']}'"
            )

        resultados.append({
            "id": fila["id"],
            "numero_factura": fila["numero_factura"],
            "numero_ord": fila["numero_ord"],
            "ok": ok,
            "errores": errores,
        })

        hash_esperado_anterior = fila["huella"]

    return resultados
