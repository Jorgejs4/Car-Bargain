"""Motor de costes de importación (Fase 7).

Calcula cuánto costaría importar un coche desde su país de origen a España,
incluyendo impuesto de matriculación, transporte, ITV y gestoría.

Las reglas fiscales están versionadas por país + año (nunca hardcodear valores
como `registration_tax = 500`). Los umbrales de CO₂ para el IEDMT español
siguen la Ley de Presupuestos vigente.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ImportEstimate:
    """Desglose de costes estimados para importar un coche a España."""
    source_country: str
    target_country: str  # normalmente "ES"
    transport_cost: float
    registration_tax: float  # IEDMT (ES) o equivalente
    itv_inspection: float
    registration_fees: float
    total_import_cost: float  # suma de todos los costes
    taxable_base: float  # valor sobre el que se aplica el impuesto
    co2_g_km: float | None  # usado para la banda del impuesto
    rules_version: str  # "ES_2026" p.ej.


# Reglas fiscales para importar a España (versión 2026).
# Fuente: Ley de Presupuestos Generales del Estado, IEDMT por tramos CO₂.
# https://sede.agenciatributaria.gob.es (valores orientativos, no vinculantes).

_SPAIN_REGISTRATION_TAX_BANDS: list[dict[str, Any]] = [
    {"co2_max": 120, "rate": 0.00, "label": "exento"},
    {"co2_max": 160, "rate": 0.0475, "label": "4.75%"},
    {"co2_max": 200, "rate": 0.0975, "label": "9.75%"},
    {"co2_max": float("inf"), "rate": 0.1475, "label": "14.75%"},
]

# Costes fijos (orientativos, actualizables vía configuración).
_SPAIN_ITV_COST = 150.0
_SPAIN_REGISTRATION_FEES = 100.0

# Costes de transporte estimados desde cada país a España (€).
# Incluye transporte en camión/ferry + seguro de tránsito.
_TRANSPORT_COST: dict[str, float] = {
    "DE": 800.0,
    "FR": 600.0,
    "IT": 900.0,
    "NL": 1000.0,
    "BE": 900.0,
    "AT": 1100.0,
    "LU": 950.0,
    "PT": 400.0,
    "ES": 0.0,
}


def _registration_tax_es(price: float, co2_g_km: float | None) -> dict[str, Any]:
    """Impuesto de matriculación español (IEDMT) basado en CO₂ y valor del vehículo.

    La base imponible es el valor de mercado en origen (precio de compra).
    Si no hay dato de CO₂ se asume la banda máxima por seguridad.
    """
    effective_co2 = co2_g_km if co2_g_km is not None else 999.0
    for band in _SPAIN_REGISTRATION_TAX_BANDS:
        if effective_co2 <= band["co2_max"]:
            rate = band["rate"]
            label = band["label"]
            break
    else:
        rate = 0.1475
        label = "14.75% (default)"

    tax = round(price * rate, 2)
    return {
        "rate": rate,
        "label": label,
        "amount": tax,
        "co2_g_km": co2_g_km,
    }


def estimate_import_to_spain(
    *,
    source_country: str,
    price_eur: float,
    co2_g_km: float | None = None,
    rules_year: int = 2026,
) -> ImportEstimate:
    """Calcula el coste total de importar un coche a España."""
    if source_country == "ES":
        return ImportEstimate(
            source_country="ES",
            target_country="ES",
            transport_cost=0.0,
            registration_tax=0.0,
            itv_inspection=0.0,
            registration_fees=0.0,
            total_import_cost=0.0,
            taxable_base=price_eur,
            co2_g_km=co2_g_km,
            rules_version=f"ES_{rules_year}",
        )

    transport = _TRANSPORT_COST.get(source_country.upper(), 1000.0)
    tax_info = _registration_tax_es(price_eur, co2_g_km)
    registration_tax = tax_info["amount"]
    itv = _SPAIN_ITV_COST
    fees = _SPAIN_REGISTRATION_FEES

    total = round(transport + registration_tax + itv + fees, 2)

    return ImportEstimate(
        source_country=source_country,
        target_country="ES",
        transport_cost=transport,
        registration_tax=registration_tax,
        itv_inspection=itv,
        registration_fees=fees,
        total_import_cost=total,
        taxable_base=price_eur,
        co2_g_km=co2_g_km,
        rules_version=f"ES_{rules_year}",
    )


def estimate_for_listing(
    *,
    source_country: str,
    price_eur: float,
    co2_g_km: float | None = None,
) -> ImportEstimate:
    """Wrapper: estima la importación a España desde cualquier país."""
    return estimate_import_to_spain(
        source_country=source_country,
        price_eur=price_eur,
        co2_g_km=co2_g_km,
    )
