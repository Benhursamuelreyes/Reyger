# ✅ SISTEMA DE AJUSTES - IMPLEMENTACIÓN COMPLETADA

## 📦 Archivos Creados/Modificados

### Nuevos Archivos:
1. **config.py** - Gestor central de configuración
   - Carga/guarda configuración en JSON
   - Maneja temas (claro/oscuro)
   - Genera paletas de colores dinámicamente

2. **ajustes.py** - Interfaz de configuración
   - Ventana completa con 5 secciones
   - Support para cargar logos personalizados
   - Preview en vivo del logo

3. **AJUSTES_README.md** - Documentación de usuario

### Archivos Modificados:
1. **container.py**
   - ✅ Importa ConfigManager y Ajustes
   - ✅ Nuevo botón "⚙️ Ajustes" en azul (#17A2B8)
   - ✅ Aplica colores dinámicos según configuración
   - ✅ Soporta logo personalizado

2. **manager.py**
   - ✅ Importa ConfigManager
   - ✅ Aplica colores de configuración a ventana principal
   - ✅ Establece tema (breeze para claro, equilux para oscuro)

## 🎯 Características Implementadas

### 1. Panel de Ajustes (5 secciones principales)
```
┌─────────────────────────────────────┐
│  ⚙️ AJUSTES Y CONFIGURACIÓN         │
├─────────────────────────────────────┤
│ 🎨 TEMA                             │
│   ☀️  Tema Claro                    │
│   🌙 Tema Oscuro                    │
├─────────────────────────────────────┤
│ 📏 TAMAÑO DE FUENTE                 │
│   Slider (10px a 18px)              │
├─────────────────────────────────────┤
│ 🖼️  LOGO DE LA EMPRESA              │
│   Preview + Botones (Cargar/Elim)   │
├─────────────────────────────────────┤
│ 🏢 INFORMACIÓN DE LA EMPRESA        │
│   Campo: Nombre de la empresa       │
├─────────────────────────────────────┤
│ ⚙️  OPCIONES ADICIONALES            │
│   □ Mostrar hora en facturas        │
│   Radio: Decimales (2, 3, 4)        │
├─────────────────────────────────────┤
│ [💾 Guardar cambios] [🔄 Restab.]  │
└─────────────────────────────────────┘
```

### 2. Temas Implementados
**Tema Claro:**
- BG Principal: #C6D9E3
- Botones: #0078D4
- Texto: #000000

**Tema Oscuro:**
- BG Principal: #1E1E1E
- Botones: #0078D4
- Texto: #FFFFFF

### 3. Logo Personalizado
- Cargador de imagen integrado
- Soporta: PNG, JPG, JPEG, BMP
- Auto-redimensionamiento a 280x280px
- Almacenamiento en carpeta de app
- Muestra en pantalla principal
- Usa en facturas (integración futura)

### 4. Archivo de Configuración JSON
```json
{
    "tema": "claro",
    "tamaño_fuente": 14,
    "logo_path": "ruta/al/logo.png",
    "nombre_empresa": "Mi Empresa",
    "mostrar_hora": true,
    "redondear_decimales": 2
}
```

## 🎨 Botones en Pantalla Principal

```
┌────────────────────────────────────┐
│  [Logo]  │  [Ventas Amarillo]      │
│          │  [Inventario Rojo]      │
│          │  [Ajustes Azul] ✨ NUEVO│
└────────────────────────────────────┘
```

## 🚀 Cómo Usar

1. **Ejecutar la aplicación:**
   ```bash
   python index.py
   ```

2. **Acceder a ajustes:**
   - Click en botón "⚙️ Ajustes"
   - Se abre ventana configurable

3. **Cambiar tema:**
   - Selecciona "Tema Claro" o "Tema Oscuro"
   
4. **Cargar logo:**
   - Click en "📁 Cargar Logo"
   - Selecciona imagen
   - Preview automático

5. **Guardar:**
   - Click en "💾 Guardar cambios"
   - Reinicia app para ver cambios completos

## 📝 Notas Técnicas

- **ConfigManager**: Singleton pattern para gestión de config
- **Persistencia**: JSON para portabilidad
- **Colores dinámicos**: get_colors() genera paleta según tema
- **Tamaños de fuente**: Helper para consistency
- **Logo**: Almacenado localmente, referencia en JSON

## 🔧 Integración Futura

El sistema está listo para:
- Usar nombre_empresa en comprobantes
- Usar logo_path en facturas (reportlab)
- Usar tamaño_fuente en todos los módulos
- Usar mostrar_hora en registros
- Usar redondear_decimales en cálculos

## ✨ Extra Agregado

- Emojis en botones para mejor UX
- Colores distintivos para cada módulo
- Separadores visuales en panel
- Preview con error handling
- Confirmaciones antes de acciones destructivas
