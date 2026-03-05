🛒 Sistema de Caja Registradora
Sistema de gestión de ventas e inventario desarrollado en Python con interfaz gráfica Tkinter. Permite realizar ventas, gestionar inventario y personalizar la aplicación mediante un panel de ajustes.

📋 Tabla de Contenidos

Características
Estructura del Proyecto
Requisitos
Instalación y Ejecución
Módulos del Sistema
Sistema de Configuración
Base de Datos
Solución de Problemas


✨ Características

🛒 Módulo de Ventas — Registro y gestión de ventas con generación de comprobantes
📦 Módulo de Inventario — Alta, edición y eliminación de productos con control de stock
⚙️ Panel de Ajustes — Personalización completa de la interfaz y datos de la empresa
🎨 Tema Claro/Oscuro — Selección de tema visual aplicado a toda la interfaz
📏 Fuente Ajustable — Tamaño de texto configurable entre 10px y 18px
🖼️ Logo Personalizado — Carga de logo empresarial con preview en vivo
💾 Configuración Persistente — Todos los ajustes se guardan en config.json


📁 Estructura del Proyecto
sales_system/
│
├── index.py              # Punto de entrada de la aplicación
├── manager.py            # Ventana principal (Tk root)
├── container.py          # Menú principal con botones de navegación
├── config.py             # Gestor de configuración (ConfigManager)
├── ventas.py             # Módulo de ventas
├── inventario.py         # Módulo de inventario
├── ajustes.py            # Panel de ajustes y configuración
│
├── database.db           # Base de datos SQLite (generada automáticamente)
├── config.json           # Configuración guardada (generada automáticamente)
├── icono.ico             # Ícono de la aplicación
└── img/
    └── logo.png          # Logo predeterminado

⚙️ Requisitos

Python 3.8 o superior
Instalar dependencias:

bashpip install pillow ttkthemes
LibreríaUsotkinterInterfaz gráfica (incluida en Python)PillowCarga y redimensionamiento de imágenesttkthemesTemas visuales (breeze / equilux)sqlite3Base de datos (incluida en Python)

🚀 Instalación y Ejecución
bashpip install pillow ttkthemes
python index.py

🗂️ Módulos del Sistema
index.py
Punto de entrada. Instancia Manager e inicia el loop principal de Tkinter.
manager.py
Ventana raíz (Tk). Crea la ventana de 800×400px, aplica el tema y los colores según la configuración, carga el ícono e instancia el frame Container. Aplica el tema TTK: breeze (claro) o equilux (oscuro).
container.py
Menú principal. Contiene los tres botones de navegación:
BotónColorAcción🛒 Ir a ventasAmarilloAbre ventana de Ventas📦 Ir a inventarioRojoAbre ventana de Inventario⚙️ AjustesAzulAbre ventana de Ajustes
Cada módulo se abre como Toplevel de 1100×650px. También gestiona la carga del logo predeterminado y del logo personalizado.
config.py
Gestor centralizado de configuración (ConfigManager). Lee y escribe config.json.
Configuración predeterminada:
json{
    "tema": "claro",
    "tamaño_fuente": 14,
    "logo_path": null,
    "nombre_empresa": "Mi Empresa",
    "mostrar_hora": true,
    "redondear_decimales": 2
}
Métodos principales:
MétodoDescripciónload_config()Carga configuración desde config.jsonsave_config()Guarda la configuración actualget(key, default)Obtiene un valorset(key, value)Establece un valor y guarda automáticamenteget_colors()Retorna paleta de colores según el tema activoget_tamaño_fuente(tipo)Retorna el tamaño de fuente para un tipo dado
Paletas de colores:
ElementoTema ClaroTema OscuroBG Principal#C6D9E3#1E1E1EBG Secundario#E8F0F7#2D2D2DTexto#000000#FFFFFFBotones#0078D4#0078D4
Tamaños de fuente:
TipoFórmulatitulobase + 16subtitulobase + 4defaultbasepequeñobase - 2
inventario.py
Módulo CRUD de productos. Tabla SQLite inventario:
CampoTipoDescripciónidINTEGERClave primaria (autoincr)nombreTEXTNombre del productoproveedorTEXTProveedorprecioREALPrecio de ventacostoREALCosto de adquisiciónstockINTEGERUnidades disponibles
Operaciones: ➕ Ingresar · ✏️ Editar · 🗑️ Eliminar · 🔄 Actualizar. Los precios se muestran en formato {:,.0f} €.
ajustes.py
Panel de configuración con 5 secciones: tema, tamaño de fuente, logo, nombre de empresa y opciones adicionales (hora en facturas, precisión decimal).

🎛️ Sistema de Configuración
Acceder desde el botón "⚙️ Ajustes" en la pantalla principal.
OpciónDescripciónTema Claro/OscuroCambia la apariencia visual de toda la appTamaño de fuenteAjustable entre 10px y 18pxLogo personalizadoPNG, JPG, JPEG, BMP — imágenes cuadradas (mín. 200×200px)Nombre de empresaAparece en comprobantes y facturasMostrar horaIncluye la hora exacta en cada comprobantePrecisión decimal2, 3 o 4 decimales para los precios

⚠️ Algunos cambios requieren reiniciar la aplicación para aplicarse completamente.


🗄️ Base de Datos
SQLite. El archivo database.db se crea automáticamente en el directorio del ejecutable o script:
pythondef get_db_path():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "database.db")

🔧 Solución de Problemas
El logo no se muestra — Verifica que el archivo exista, prueba con PNG y comprueba permisos de lectura.
No se guardan los cambios — Verifica permisos de escritura en la carpeta de la app y espacio en disco disponible.
La app se ve extraña con tema oscuro — Cierra completamente y reinicia la aplicación.
Error con la base de datos — Asegúrate de que no haya otro proceso bloqueando database.db y que el directorio tenga permisos de lectura/escritura.

🔮 Integraciones Futuras
El sistema está listo para extenderse con:

Nombre de empresa en encabezados de comprobantes
Logo en facturas PDF generadas con reportlab
Aplicación dinámica del tamaño de fuente en todos los módulos
<<<<<<< HEAD
Uso de mostrar_hora y redondear_decimales en todos los cálculos
=======
Uso de mostrar_hora y redondear_decimales en todos los cálculos
>>>>>>> 1d83f90d5298d19480b94331849373e8dbcf050e
