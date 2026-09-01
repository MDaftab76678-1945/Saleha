"""
Saleha Skills: Unit Converter Skill (Built-in Skill)

Fast, precise, deterministic unit conversion for Temperature, Distance/Length,
Mass/Weight, Digital Storage, and Speed without LLM calls.
"""

import re

from saleha.core.skill_base import Skill, SkillResult


class UnitConverterSkill(Skill):
    name = "unit_converter"
    description = "Fast unit conversion for temperature (C/F/K), distance (km/m/mi/ft), weight (kg/lb/g), digital storage (MB/GB/TB), and speed (kmh/mph)."

    # Pattern: "convert 100 celsius to fahrenheit" or "50 km to miles" or "1024 mb in gb"
    _PATTERN = re.compile(
        r"(?:convert\s+)?([-+]?\d+(?:\.\d+)?)\s*([a-zA-Z°]+)\s*(?:to|in|into|\->|=)\s*([a-zA-Z°]+)",
        re.IGNORECASE
    )

    def can_handle(self, task: str) -> bool:
        # Coding requests should go to CoderAgent
        if any(kw in task.lower() for kw in ["function", "class", "script", "program", "code", "write", "likho"]):
            return False
        match = self._PATTERN.search(task)
        if not match:
            return False
        _, from_unit, to_unit = match.groups()
        return self._is_supported_conversion(from_unit.lower(), to_unit.lower())

    def execute(self, task: str) -> SkillResult:
        match = self._PATTERN.search(task)
        if not match:
            return SkillResult(success=False, output="", error="No supported conversion expression found.")

        val_str, from_u, to_u = match.groups()
        try:
            val = float(val_str)
            from_u = from_u.lower().strip("°")
            to_u = to_u.lower().strip("°")

            res, canonical_to = self._convert(val, from_u, to_u)
            # Format nicely
            if res.is_integer():
                res_formatted = f"{int(res)}"
            else:
                res_formatted = f"{res:.4f}".rstrip('0').rstrip('.')

            return SkillResult(
                success=True,
                output=f"{val_str} {from_u} = {res_formatted} {canonical_to}"
            )
        except Exception as e:
            return SkillResult(success=False, output="", error=f"Conversion failed: {e}")

    def _is_supported_conversion(self, u1: str, u2: str) -> bool:
        u1 = u1.strip("°")
        u2 = u2.strip("°")
        for category in [self._TEMP_UNITS, self._LENGTH_UNITS, self._MASS_UNITS, self._STORAGE_UNITS, self._SPEED_UNITS]:
            if u1 in category and u2 in category:
                return True
        return False

    _TEMP_UNITS = {"c", "celsius", "centigrade", "f", "fahrenheit", "k", "kelvin"}

    _LENGTH_UNITS = {
        "m": 1.0, "meter": 1.0, "meters": 1.0,
        "km": 1000.0, "kilometer": 1000.0, "kilometers": 1000.0,
        "cm": 0.01, "centimeter": 0.01, "centimeters": 0.01,
        "mm": 0.001, "millimeter": 0.001, "millimeters": 0.001,
        "mi": 1609.344, "mile": 1609.344, "miles": 1609.344,
        "ft": 0.3048, "foot": 0.3048, "feet": 0.3048,
        "in": 0.0254, "inch": 0.0254, "inches": 0.0254,
        "yd": 0.9144, "yard": 0.9144, "yards": 0.9144,
    }

    _MASS_UNITS = {
        "kg": 1.0, "kilogram": 1.0, "kilograms": 1.0,
        "g": 0.001, "gram": 0.001, "grams": 0.001,
        "mg": 0.000001, "milligram": 0.000001, "milligrams": 0.000001,
        "lb": 0.45359237, "lbs": 0.45359237, "pound": 0.45359237, "pounds": 0.45359237,
        "oz": 0.028349523125, "ounce": 0.028349523125, "ounces": 0.028349523125,
    }

    _STORAGE_UNITS = {
        "b": 1.0, "byte": 1.0, "bytes": 1.0,
        "kb": 1024.0, "kilobyte": 1024.0, "kilobytes": 1024.0,
        "mb": 1024.0 ** 2, "megabyte": 1024.0 ** 2, "megabytes": 1024.0 ** 2,
        "gb": 1024.0 ** 3, "gigabyte": 1024.0 ** 3, "gigabytes": 1024.0 ** 3,
        "tb": 1024.0 ** 4, "terabyte": 1024.0 ** 4, "terabytes": 1024.0 ** 4,
    }

    _SPEED_UNITS = {
        "m/s": 1.0, "mps": 1.0,
        "km/h": 1.0 / 3.6, "kmh": 1.0 / 3.6, "kph": 1.0 / 3.6,
        "mph": 0.44704, "mi/h": 0.44704,
    }

    def _convert(self, val: float, from_u: str, to_u: str) -> tuple[float, str]:
        # 1. Temperature
        if from_u in self._TEMP_UNITS:
            return self._convert_temp(val, from_u, to_u)

        # 2. Length
        if from_u in self._LENGTH_UNITS and to_u in self._LENGTH_UNITS:
            base_m = val * self._LENGTH_UNITS[from_u]
            return (base_m / self._LENGTH_UNITS[to_u], to_u)

        # 3. Mass
        if from_u in self._MASS_UNITS and to_u in self._MASS_UNITS:
            base_kg = val * self._MASS_UNITS[from_u]
            return (base_kg / self._MASS_UNITS[to_u], to_u)

        # 4. Storage
        if from_u in self._STORAGE_UNITS and to_u in self._STORAGE_UNITS:
            base_b = val * self._STORAGE_UNITS[from_u]
            return (base_b / self._STORAGE_UNITS[to_u], to_u)

        # 5. Speed
        if from_u in self._SPEED_UNITS and to_u in self._SPEED_UNITS:
            base_mps = val * self._SPEED_UNITS[from_u]
            return (base_mps / self._SPEED_UNITS[to_u], to_u)

        raise ValueError(f"Incompatible unit conversion from '{from_u}' to '{to_u}'")

    def _convert_temp(self, val: float, from_u: str, to_u: str) -> tuple[float, str]:
        # Normalize to Celsius
        if from_u in ("c", "celsius", "centigrade"):
            c = val
        elif from_u in ("f", "fahrenheit"):
            c = (val - 32.0) * (5.0 / 9.0)
        elif from_u in ("k", "kelvin"):
            c = val - 273.15
        else:
            raise ValueError(f"Unknown temp unit: {from_u}")

        # From Celsius to target
        if to_u in ("c", "celsius", "centigrade"):
            return (c, "celsius")
        elif to_u in ("f", "fahrenheit"):
            return (c * (9.0 / 5.0) + 32.0, "fahrenheit")
        elif to_u in ("k", "kelvin"):
            return (c + 273.15, "kelvin")
        else:
            raise ValueError(f"Unknown temp unit: {to_u}")

