# 🛒 Sistema de Caja Registradora - Guía de Configuración

## Nuevas Características - Sistema de Ajustes

Se ha agregado un completo sistema de configura y personalización a la aplicación.

### 📋 Características Agregadas

#### 1. **🎨 Tema Claro/Oscuro**
   - Selecciona entre tema claro (predeterminado) o tema oscuro
   - Los cambios se aplican a toda la interfaz
   - La configuración se guarda automáticamente

#### 2. **📏 Tamaño de Fuente Ajustable**
   - Rango: 10px a 18px
   - Ajusta el tamaño de todos los textos de la aplicación
   - Útil para mejorar la legibilidad según preferencias

#### 3. **🖼️ Logo Personalizado**
   - Carga tu propio logo empresarial
   - El logo aparecerá en:
     - La pantalla principal
     - Las facturas/comprobantes
     - Los tickets de venta
   - Formatos soportados: PNG, JPG, JPEG, BMP
   - Preview en vivo de la imagen cargada

#### 4. **🏢 Información de la Empresa**
   - Nombre de la empresa personalizable
   - Aparecerá en todos los comprobantes
   - Se almacena en la configuración local

#### 5. **⚙️ Opciones Adicionales**
   - **Mostrar hora en facturas**: Incluye la hora exacta en cada comprobante
   - **Precisión decimal**: Elige entre 2, 3 o 4 decimales para los precios
     - 2 decimales: $10.50 (predeterminado)
     - 3 decimales: $10.505
     - 4 decimales: $10.5050

### 🔧 Cómo Acceder a los Ajustes

1. **Desde la pantalla principal**, haz clic en el botón **"⚙️ Ajustes"**
2. Se abrirá una nueva ventana con todas las opciones de configuración
3. Realiza los cambios deseados
4. Haz clic en **"💾 Guardar cambios"** para guardar

### 🔄 Opciones de Restauración

- **Restablecer**: Revierte todas las configuraciones a sus valores predeterminados
- Los cambios se guardan automáticamente al cerrar la ventana

### 📁 Archivos de Configuración

La configuración se guarda en un archivo JSON llamado `config.json` en la misma carpeta que la aplicación:

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

### 💡 Consejos de Uso

1. **Logo**: Para mejores resultados, usa imágenes cuadradas (200x200px mínimo)
2. **Nombre de empresa**: Algunos nombres muy largos pueden no caber en ciertos comprobantes
3. **Tema oscuro**: Ideal para usar la aplicación en ambientes con poca luz
4. **Tamaño de fuente**: Probablemente necesites reiniciar la aplicación para ver todos los cambios

### ⚠️ Notas Importantes

- Los cambios toman efecto completo después de reiniciar la aplicación
- Todos los archivos de configuración se almacenan localmente en tu computadora
- El logo se guarda automáticamente en la carpeta de la aplicación

### 🆘 Solución de Problemas

**El logo no se muestra:**
- Verifica que el archivo de imagen exista
- Intenta con un formato diferente (PNG funciona mejor)
- Comprueba los permisos de lectura de la carpeta

**No se guardan los cambios:**
- Verifica que la aplicación tenga permisos de escritura en su carpeta
- Comprueba que el disco tenga espacio disponible
- Intenta colocar la aplicación en una carpeta sin restricciones (ej: Documentos)

**La aplicación se ve extraña con el tema oscuro:**
- Cierra completamente la aplicación y abre de nuevo
- Algunos elementos pueden necesitar actualización manual

---

**Versión**: 1.0
**Última actualización**: Marzo 2026
