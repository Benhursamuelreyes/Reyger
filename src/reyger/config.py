import json
import os

from .resources import get_user_data_path


class ConfigManager:
    def __init__(self):
        self.config_file = self.get_config_path()
        self.config_data = self.load_config()

    @staticmethod
    def get_config_path():
        return os.path.join(str(get_user_data_path()), "config.json")

    def load_config(self):
        default_config = {
            "tema": "claro",
            "tamaño_fuente": 14,
            "logo_path": None,
            "nombre_empresa": "Mi Empresa",
            "mostrar_hora": True,
            "redondear_decimales": 2,
            "escaner_activo": False,
            "ancho_ticket": 80,
            "letra_ticket": "muy_grande",
        }
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return {**default_config, **config}
            except Exception as e:
                print(f"Error cargando configuración: {e}")
                return default_config
        return default_config

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error guardando configuración: {e}")
            return False

    def get(self, key, default=None):
        return self.config_data.get(key, default)

    def set(self, key, value):
        self.config_data[key] = value
        return self.save_config()

    def get_colors(self):
        if self.config_data["tema"] == "oscuro":
            return {
                "bg_principal": "#1E1E1E",
                "bg_secundario": "#2D2D2D",
                "fg_texto": "#FFFFFF",
                "fg_boton": "#FFFFFF",
                "bg_boton": "#0078D4",
                "frame_bg": "#242424",
                "entry_bg": "#3C3C3C",
                "entry_fg": "#FFFFFF",
            }
        else:
            return {
                "bg_principal": "#C6D9E3",
                "bg_secundario": "#E8F0F7",
                "fg_texto": "#000000",
                "fg_boton": "#FFFFFF",
                "bg_boton": "#0078D4",
                "frame_bg": "#C6D9E3",
                "entry_bg": "#FFFFFF",
                "entry_fg": "#000000",
            }

    def get_tamaño_fuente(self, tipo="default"):
        base = self.config_data["tamaño_fuente"]
        tamaños = {
            "titulo": base + 16,
            "subtitulo": base + 4,
            "default": base,
            "pequeño": base - 2,
        }
        return tamaños.get(tipo, base)
