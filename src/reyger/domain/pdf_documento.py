"""Servicio unificado de generación de PDF (A4) para Reyger.

Unifica la plantilla visual de **Albaranes**, **Presupuestos** y
**Facturas**: membrete dinámico del negocio, datos del cliente, tabla
de productos, desglose de impuestos y pie de página.

Todos los documentos A4 (los que NO se envían a la impresora térmica de
tickets) se generan a través de este módulo para garantizar coherencia
visual y lógica.
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)
from reportlab.pdfgen import canvas

from ..config import ConfigManager
from ..ui import business_profile as bp
from ..core import moneda as mod_moneda
from ..resources import get_output_path


AZUL = colors.HexColor("#0078D4")
FONDO_FILA = colors.HexColor("#F5F5F5")


class PdfDocumento:
    """Genera un documento PDF A4 estandarizado con membrete de empresa."""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager or ConfigManager()
        self.estilos = getSampleStyleSheet()
        self._crear_estilos_personalizados()

    def _crear_estilos_personalizados(self):
        s = self.estilos

        self.estilo_titulo = ParagraphStyle(
            "DocTitle",
            parent=s["Heading1"],
            fontSize=20,
            textColor=AZUL,
            spaceAfter=8,
            alignment=1,
            fontName="Helvetica-Bold",
        )
        self.estilo_subtitulo = ParagraphStyle(
            "DocSubtitle",
            parent=s["Heading2"],
            fontSize=12,
            textColor=colors.black,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        )
        self.estilo_normal = ParagraphStyle(
            "DocNormal",
            parent=s["Normal"],
            fontSize=10,
            spaceAfter=6,
        )
        self.estilo_empresa = ParagraphStyle(
            "DocEmpresa",
            parent=s["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            alignment=1,
            spaceAfter=3,
        )

    # ── API pública ──────────────────────────────────────────────

    def generar(self, output_path, titulo_documento, subtitulo_documento,
                numero, fecha, cliente_nombre, cliente_direccion=None,
                cliente_nif=None, cliente_email=None, productos=None,
                base_imponible=None, tipo_iva=None, total_iva=None,
                total=None, observaciones="", campos_firma=True,
                codigo_qr=None, pie_legal=None, columnas_productos=None,
                filas_extra=None):
        """Construye y guarda un documento PDF A4 unificado.

        Args:
            output_path: Ruta destino del PDF.
            titulo_documento: Título grande (membrete), ej. nombre empresa.
            subtitulo_documento: Subtítulo bajo el membrete, ej. 'FACTURA',
                'PRESUPUESTO' o 'ALBARÁN DE ENTREGA'.
            numero: Número del documento (texto).
            fecha: Fecha (datetime o string).
            cliente_nombre: Nombre del cliente.
            cliente_direccion: Dirección del cliente (opcional).
            cliente_nif: NIF del cliente (opcional).
            cliente_email: Email del cliente (opcional).
            productos: Lista de diccionarios. Si es ``None`` se omite la tabla.
            base_imponible, tipo_iva, total_iva, total: desglose fiscal (opcional).
            observaciones: Texto de observaciones (opcional).
            campos_firma: Si hay que añadir campos de firma (albaranes).
            codigo_qr: Flowable o None (facturas VeriFACTU).
            pie_legal: Texto legal o None.
            columnas_productos: Cabecera de la tabla de productos. Por defecto
                ['DESCRIPCIÓN', 'CANTIDAD', 'P. UNITARIO (símbolo)',
                'SUBTOTAL (símbolo)'] según la moneda global.
            filas_extra: Filas adicionales a añadir bajo la tabla.
        """
        if output_path is None:
            output_path = self._ruta_por_defecto(subtitulo_documento, numero)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2.0 * cm,
            bottomMargin=2.0 * cm,
        )

        story = []
        story.extend(self._membrete(titulo_documento))
        story.append(Spacer(1, 0.4 * cm))
        story.extend(self._info_documento(subtitulo_documento, numero, fecha))
        story.append(Spacer(1, 0.3 * cm))
        story.extend(self._datos_cliente(
            cliente_nombre, cliente_direccion, cliente_nif, cliente_email
        ))
        story.append(Spacer(1, 0.3 * cm))

        if productos:
            story.extend(self._tabla_productos(
                productos, columnas_productos=columnas_productos
            ))
            story.append(Spacer(1, 0.3 * cm))

        if filas_extra:
            story.extend(filas_extra)

        if base_imponible is not None:
            story.extend(self._tabla_totales(base_imponible, tipo_iva, total_iva, total))
            story.append(Spacer(1, 0.3 * cm))

        if codigo_qr is not None:
            story.extend(codigo_qr)

        if observaciones:
            story.extend(self._observaciones(observaciones))
            story.append(Spacer(1, 0.3 * cm))

        if pie_legal:
            story.append(Spacer(1, 0.4 * cm))
            story.append(Paragraph(pie_legal, self.estilo_normal))

        if campos_firma:
            story.append(Spacer(1, 0.4 * cm))
            story.extend(self._campos_firma())

        doc.build(story)
        return output_path

    # ── Secciones ────────────────────────────────────────────────

    def _membrete(self, titulo_documento):
        """Membrete dinámico con logo, nombre y datos de contacto."""
        elementos = []

        logo_path = (
            bp.obtener_campo("logo_path")
            or self.config_manager.get("logo_path")
        )
        if logo_path and os.path.exists(logo_path):
            try:
                # Flowable Image de reportlab (en lugar de <img> dentro de un
                # Paragraph): respeta proporción y evita que el logotipo se
                # recorte por el leading del párrafo o por el margen superior.
                img = Image(logo_path, width=2.4 * cm, height=2.4 * cm)
                img.hAlign = "LEFT"
                elementos.append(img)
                elementos.append(Spacer(1, 0.2 * cm))
            except Exception:
                pass

        elementos.append(Paragraph(
            f"<b>{titulo_documento.upper()}</b>",
            self.estilo_titulo,
        ))

        # Nombre comercial / de la tienda (p. ej. 'GIGA'), bajo la razón social.
        nombre_comercial = bp.obtener_campo("nombre_comercial")
        if nombre_comercial:
            elementos.append(
                Paragraph(str(nombre_comercial), self.estilo_empresa)
            )

        perfil = bp.obtener()
        if perfil:
            p = dict(perfil)
            lineas = []
            if p.get("nif"):
                lineas.append(f"NIF: {p['nif']}")
            if p.get("direccion"):
                d = p["direccion"]
                if p.get("codigo_postal"):
                    d += f", {p['codigo_postal']}"
                if p.get("provincia"):
                    d += f" — {p['provincia']}"
                lineas.append(d)
            if p.get("telefono"):
                lineas.append(f"Tel: {p['telefono']}")
            if p.get("email"):
                lineas.append(f"Email: {p['email']}")
            if lineas:
                elementos.append(Paragraph(" | ".join(lineas), self.estilo_empresa))

        return elementos

    def _info_documento(self, subtitulo_documento, numero, fecha):
        """Cabecera de información del documento.

        Acepta una fecha como ``datetime`` o como cadena en cualquiera de
        los formatos soportados (``%Y-%m-%d`` e ISO con hora, o el formato
        español ``dd/mm/aaaa [HH:MM]`` usado por el TPV). Si no se puede
        interpretar, se usa la fecha actual en lugar de "asumir" hoy
        silenciosamente con un formato incorrecto.
        """
        if isinstance(fecha, str):
            fecha_parseada = None
            for formato in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S",
                            "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    fecha_parseada = datetime.strptime(fecha, formato)
                    break
                except ValueError:
                    continue
            fecha = fecha_parseada if fecha_parseada is not None else datetime.now()
        fecha_str = fecha.strftime("%d/%m/%Y")

        elementos = [Paragraph(
            f"<b>{subtitulo_documento}</b>",
            self.estilo_subtitulo,
        )]

        datos = [
            ["Número:", numero],
            ["Fecha:", fecha_str],
        ]
        tabla = Table(datos, colWidths=[4 * cm, 12 * cm])
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(tabla)
        return elementos

    def _datos_cliente(self, cliente_nombre, cliente_direccion,
                       cliente_nif, cliente_email):
        """Sección de datos del cliente."""
        elementos = [Paragraph(
            "<b>DATOS DEL CLIENTE</b>",
            self.estilo_subtitulo,
        )]

        filas = [["Nombre/Empresa:", cliente_nombre or ""]]
        if cliente_nif:
            filas.append(["NIF/VAT ID:", cliente_nif])
        if cliente_direccion:
            filas.append(["Dirección:", cliente_direccion])
        if cliente_email:
            filas.append(["Email:", cliente_email])

        tabla = Table(filas, colWidths=[4 * cm, 12 * cm])
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TEXTCOLOR", (0, 0), (0, -1), AZUL),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elementos.append(tabla)
        return elementos

    def _tabla_productos(self, productos, columnas_productos=None):
        """Tabla de productos/servicios."""
        simbolo = mod_moneda.simbolo_moneda()
        columnas = columnas_productos or [
            "DESCRIPCIÓN", "CANTIDAD",
            f"P. UNITARIO ({simbolo})", f"SUBTOTAL ({simbolo})",
        ]
        n_cols = len(columnas)
        ancho_total = 16 * cm
        anchos = [ancho_total / n_cols] * n_cols

        datos_tabla = [columnas]
        for prod in productos:
            nombre = prod.get("nombre_articulo") or prod.get("nombre", "Sin nombre")
            cantidad = prod.get("cantidad", 0)
            precio = prod.get("valor_articulo", 0)
            subtotal = prod.get("subtotal", cantidad * precio)
            descripcion = prod.get("descripcion", "")

            fila = [
                nombre,
                str(cantidad),
                mod_moneda.format_currency(precio, decimales=2),
                mod_moneda.format_currency(subtotal, decimales=2),
            ]
            if descripcion:
                fila[-1] = f"{fila[-1]} ({descripcion})"
            datos_tabla.append(fila)

        tabla = Table(datos_tabla, colWidths=anchos)
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AZUL),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 11),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 10),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, FONDO_FILA]),
        ]))
        return [tabla]

    def _tabla_totales(self, base_imponible, tipo_iva, total_iva, total):
        """Tabla de totales alineada a la derecha."""
        elementos = [Spacer(1, 0.2 * cm)]
        filas = [
            ["Subtotal (Base Imponible):", mod_moneda.format_currency(base_imponible)],
        ]
        if tipo_iva is not None and total_iva is not None:
            filas.append([
                f"IVA {tipo_iva}%:", mod_moneda.format_currency(total_iva)
            ])
        filas.append(["TOTAL A PAGAR:", mod_moneda.format_currency(total)])

        tabla = Table(filas, colWidths=[9 * cm, 3 * cm])
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -2), "Helvetica"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -2), 10),
            ("FONTSIZE", (0, -1), (-1, -1), 12),
            ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
            ("TEXTCOLOR", (0, -1), (0, -1), AZUL),
            ("TEXTCOLOR", (1, -1), (1, -1), AZUL),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8F0F7")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elementos.append(tabla)
        return elementos

    def _observaciones(self, observaciones):
        elementos = [Paragraph(
            "<b>OBSERVACIONES</b>",
            self.estilo_subtitulo,
        )]
        elementos.append(Paragraph(observaciones, self.estilo_normal))
        return elementos

    def _campos_firma(self):
        """Campos de conformidad de entrega (para albaranes)."""
        elementos = [Paragraph(
            "<b>CONFORMIDAD DE ENTREGA</b>",
            self.estilo_subtitulo,
        )]
        datos_firma = [
            ["Conforme conforme entrega", "Firma y sello del cliente"],
            [" ", " "],
            [" ", " "],
            [" ", " "],
        ]
        tabla = Table(datos_firma, colWidths=[7.5 * cm, 7.5 * cm])
        tabla.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
            ("TOPPADDING", (0, 1), (-1, -1), 40),
            ("GRID", (0, 1), (-1, 3), 1, colors.black),
            ("ALIGN", (0, 1), (-1, 3), "CENTER"),
            ("VALIGN", (0, 1), (-1, 3), "TOP"),
        ]))
        elementos.append(tabla)
        return elementos

    # ── Utilidades ───────────────────────────────────────────────

    def _ruta_por_defecto(self, subtitulo, numero):
        subdir = subtitulo.lower().replace("á", "a").replace("é", "e")
        subdir = subdir.replace("í", "i").replace("ó", "o").replace("ú", "u")
        subdir = "".join(c for c in subdir if c.isalnum() or c == " ")
        subdir = subdir.strip().replace(" ", "_")
        carpeta = get_output_path(subdir or "documentos")
        return os.path.join(
            carpeta,
            f"{subtitulo}_{numero}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
