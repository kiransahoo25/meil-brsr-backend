"""Indian carbon emission factors and unit conversions.

Data sources:
- Grid Emission Factor: Central Electricity Authority (CEA), Govt of India
- Fuel factors: IPCC 2006 Guidelines + Indian Ministry of Environment (MoEFCC)
- Unit conversions: BEE (Bureau of Energy Efficiency) standards
"""

from datetime import datetime

# ---------------------------------------------------------------
# DATA VERSION — track which year's factors are in use
# ---------------------------------------------------------------
FACTORS_VERSION = "CEA 2023 · MoEFCC 2024"
LAST_UPDATED = "2026-10-05"


# ---------------------------------------------------------------
# GRID EMISSION FACTOR
# ---------------------------------------------------------------
# India's grid is dominated by coal, so the factor is high
# Updated annually by CEA. Historically:
#   2019: 0.82 tCO2e/MWh
#   2021: 0.79 tCO2e/MWh
#   2022: 0.75 tCO2e/MWh
#   2023: 0.71 tCO2e/MWh  ← current
GRID_EMISSION_FACTOR = {
    "value": 0.71,
    "unit": "tCO2e / MWh",
    "source": "Central Electricity Authority (CEA), Govt of India",
    "year": 2023,
    "notes": "Weighted average grid emission factor for India",
}


# ---------------------------------------------------------------
# FUEL EMISSION FACTORS
# Units: kg CO2e per physical unit of fuel
# ---------------------------------------------------------------
FUEL_FACTORS = {
    "diesel_litre": {
        "value": 2.68,
        "unit": "kg CO2e / litre",
        "source": "IPCC 2006 · MoEFCC",
    },
    "petrol_litre": {
        "value": 2.31,
        "unit": "kg CO2e / litre",
        "source": "IPCC 2006 · MoEFCC",
    },
    "natural_gas_m3": {
        "value": 2.02,
        "unit": "kg CO2e / m³",
        "source": "IPCC 2006 · MoEFCC",
    },
    "lpg_kg": {
        "value": 2.98,
        "unit": "kg CO2e / kg",
        "source": "IPCC 2006 · MoEFCC",
    },
    "lpg_litre": {
        "value": 1.63,
        "unit": "kg CO2e / litre",
        "source": "IPCC 2006 · MoEFCC",
    },
    "coal_kg": {
        "value": 2.86,
        "unit": "kg CO2e / kg",
        "source": "IPCC 2006 · MoEFCC",
    },
    "furnace_oil_litre": {
        "value": 3.11,
        "unit": "kg CO2e / litre",
        "source": "IPCC 2006 · MoEFCC",
    },
    "kerosene_litre": {
        "value": 2.51,
        "unit": "kg CO2e / litre",
        "source": "IPCC 2006 · MoEFCC",
    },
    "cng_kg": {
        "value": 2.75,
        "unit": "kg CO2e / kg",
        "source": "IPCC 2006 · MoEFCC",
    },
    "aviation_fuel_litre": {
        "value": 2.55,
        "unit": "kg CO2e / litre",
        "source": "IPCC 2006",
    },
}


# ---------------------------------------------------------------
# UNIT CONVERSIONS
# ---------------------------------------------------------------
UNIT_CONVERSIONS = {
    "kwh_to_gj": 0.0036,
    "mwh_to_gj": 3.6,
    "kwh_to_mwh": 0.001,
    "kl_to_litre": 1000,
    "tonne_to_kg": 1000,
    "litre_to_m3": 0.001,
    "kg_to_tonne": 0.001,
}


# ---------------------------------------------------------------
# CALCULATION FUNCTIONS
# ---------------------------------------------------------------
def calc_electricity_emissions(kwh: float) -> dict:
    """
    Convert electricity consumption (kWh) to tCO2e.

    Example:
        1000 kWh × 0.71 tCO2e/MWh × 0.001 MWh/kWh = 0.71 tCO2e
    """
    mwh = kwh * UNIT_CONVERSIONS["kwh_to_mwh"]
    tco2e = mwh * GRID_EMISSION_FACTOR["value"]
    return {
        "input": kwh,
        "input_unit": "kWh",
        "output": round(tco2e, 4),
        "output_unit": "tCO2e",
        "formula": f"{kwh} kWh × {GRID_EMISSION_FACTOR['value']} tCO2e/MWh ÷ 1000",
        "factor_used": f"Grid EF {GRID_EMISSION_FACTOR['value']} tCO2e/MWh ({GRID_EMISSION_FACTOR['year']})",
    }


def calc_fuel_emissions(fuel_type: str, quantity: float) -> dict:
    """
    Convert fuel consumption to tCO2e.

    fuel_type must be one of the keys in FUEL_FACTORS.
    quantity is in the unit specified by the factor.

    Example:
        1000 litres diesel × 2.68 kg CO2e/litre = 2680 kg = 2.68 tCO2e
    """
    if fuel_type not in FUEL_FACTORS:
        return {
            "error": f"Unknown fuel type '{fuel_type}'. Available: {list(FUEL_FACTORS.keys())}"
        }
    factor = FUEL_FACTORS[fuel_type]
    kg_co2e = quantity * factor["value"]
    tco2e = kg_co2e * UNIT_CONVERSIONS["kg_to_tonne"]
    return {
        "input": quantity,
        "fuel_type": fuel_type,
        "output": round(tco2e, 4),
        "output_unit": "tCO2e",
        "formula": f"{quantity} × {factor['value']} kg CO2e / 1000",
        "factor_used": f"{factor['value']} {factor['unit']} ({factor['source']})",
    }


def calc_renewable_offset(kwh: float) -> dict:
    """
    Calculate the emissions AVOIDED by using renewable electricity.

    Example:
        1000 kWh solar × 0.71 tCO2e/MWh = 0.71 tCO2e avoided
    """
    mwh = kwh * UNIT_CONVERSIONS["kwh_to_mwh"]
    avoided = mwh * GRID_EMISSION_FACTOR["value"]
    return {
        "input": kwh,
        "input_unit": "kWh (renewable)",
        "output": round(avoided, 4),
        "output_unit": "tCO2e avoided",
        "formula": f"{kwh} kWh × {GRID_EMISSION_FACTOR['value']} tCO2e/MWh ÷ 1000",
        "factor_used": f"Grid EF {GRID_EMISSION_FACTOR['value']} tCO2e/MWh (avoided emissions)",
    }


def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """
    Generic unit converter.
    Supported: kWh↔MWh↔GJ, kL↔L↔m³, kg↔tonne
    """
    conversion_map = {
        ("kWh", "MWh"): 0.001,
        ("kWh", "GJ"): 0.0036,
        ("MWh", "kWh"): 1000,
        ("MWh", "GJ"): 3.6,
        ("GJ", "kWh"): 277.78,
        ("GJ", "MWh"): 0.2778,
        ("kL", "L"): 1000,
        ("kL", "m³"): 1,
        ("L", "kL"): 0.001,
        ("L", "m³"): 0.001,
        ("m³", "kL"): 1,
        ("m³", "L"): 1000,
        ("kg", "tonne"): 0.001,
        ("tonne", "kg"): 1000,
    }
    key = (from_unit, to_unit)
    if key not in conversion_map:
        return {"error": f"Cannot convert {from_unit} to {to_unit}"}
    result = value * conversion_map[key]
    return {
        "input": value,
        "input_unit": from_unit,
        "output": round(result, 6),
        "output_unit": to_unit,
    }


def get_all_reference_data() -> dict:
    """
    Return everything the frontend needs to display the reference table
    and power the calculator.
    """
    return {
        "version": FACTORS_VERSION,
        "last_updated": LAST_UPDATED,
        "grid_emission_factor": GRID_EMISSION_FACTOR,
        "fuel_factors": FUEL_FACTORS,
        "unit_conversions": UNIT_CONVERSIONS,
        "supported_calculations": [
            {
                "id": "electricity",
                "label": "Electricity → tCO₂e",
                "input_unit": "kWh",
                "output_unit": "tCO2e",
                "description": "Convert grid electricity consumption to emissions",
            },
            {
                "id": "fuel",
                "label": "Fuel → tCO₂e",
                "input_unit": "litres / kg / m³",
                "output_unit": "tCO2e",
                "description": "Convert fuel consumption to emissions",
            },
            {
                "id": "renewable",
                "label": "Renewable → tCO₂e avoided",
                "input_unit": "kWh",
                "output_unit": "tCO2e avoided",
                "description": "Emissions saved by using renewable electricity",
            },
        ],
    }