"""
Resolve simulatable material property distributions for a vest design.

Priority per (material, property, direction):
  1. material_property_distributions row (population_scope='accepted_units',
     latest effective version)  -> provenance from the row
  2. raw measurements           -> empirical_bootstrap (provenance='measured')
  3. report-derived stats       -> truncated_normal(mu, sigma, lower=0)
                                   (provenance='report_derived')
  4. catalog value only         -> constant (provenance='catalog_nominal';
                                   reported, not varied)
  5. nothing                    -> warning; property not simulated

Missing spec windows: a material property that has no spec limits and no
distribution gets a labeled 'assumed' triangular around the catalog value
(DEFAULT_ASSUMED_REL_TOLERANCE), and a warning is recorded. Per the owner:
when a tolerance is missing the run must warn rather than silently proceed.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.db.models import (
    Material,
    MaterialPropertyDistribution,
    MaterialPropertyMeasurement,
    MaterialPropertySpec,
    Vest,
    VestLayer,
)


_SYMMETRIC_TOL_RE = re.compile(r"^\s*[±+]?\s*(\d+(?:\.\d+)?)\s*(%|mm)?\s*$")
_ASYMMETRIC_TOL_RE = re.compile(
    r"^\s*\+?\s*(\d+(?:\.\d+)?)\s*(mm)?\s*/\s*-?\s*(\d+(?:\.\d+)?)\s*(%|mm)?\s*$"
)


def _tolerance_bounds(tol_raw: Any, nominal: Optional[float]) -> Optional[Tuple[float, float]]:
    """Parse a free-text material thickness tolerance into (lower, upper) bounds.

    Supported forms: '±0.02', '0.02', '0.02 mm' (absolute mm offset),
    '5%' / '±5%' (relative to nominal), and '+0.02/-0.03' (asymmetric).
    Returns None when the value is missing or unparseable.
    """
    if not tol_raw or nominal is None or nominal <= 0:
        return None
    s = str(tol_raw).strip()

    floor = nominal * 0.01  # keep bounds physically positive

    m = _ASYMMETRIC_TOL_RE.match(s)
    if m:
        plus, _, minus, unit = float(m.group(1)), m.group(2), float(m.group(3)), m.group(4)
        if unit == "%":
            return (max(nominal * (1 - minus / 100.0), floor),
                    nominal * (1 + plus / 100.0))
        return (max(nominal - minus, floor), nominal + plus)

    m = _SYMMETRIC_TOL_RE.match(s)
    if m:
        val, unit = float(m.group(1)), m.group(2)
        offset = nominal * val / 100.0 if unit == "%" else val
        if offset > 0:
            return (max(nominal - offset, floor), nominal + offset)
    return None

from app.services.risk.sampling import SampleVariable

# Half-width of the assumed triangular tolerance when no spec exists.
DEFAULT_ASSUMED_REL_TOLERANCE = 0.05

# material_property_* keys -> the material_properties key used by the
# feature contract (ballistic_ml material snapshot keys).
PROPERTY_TO_FEATURE_KEY = {
    "thickness_mm": "thickness_mm",
    "areal_density_g_m2": "areal_density_g_m2",
    "breaking_force_n_per_cm|longitudinal": "force_longitudinal_n_per_cm",
    "breaking_force_n_per_cm|transverse": "force_transverse_n_per_cm",
    "tensile_strength_mpa": "tensile_strength_mpa",
    "modulus_gpa": "modulus_gpa",
}

# properties we simulate by default when data allows
SIMULATED_PROPERTIES = [
    ("thickness_mm", "none", "mm"),
    ("areal_density_g_m2", "none", "g/m2"),
    ("breaking_force_n_per_cm", "longitudinal", "N/cm"),
    ("breaking_force_n_per_cm", "transverse", "N/cm"),
]

# catalog column used as nominal for each simulated property
CATALOG_NOMINAL = {
    ("thickness_mm", "none"): lambda m: float(m.thickness_mm) if m.thickness_mm is not None else None,
    ("areal_density_g_m2", "none"): lambda m: float(m.areal_density_g_m2) if m.areal_density_g_m2 is not None else None,
    ("breaking_force_n_per_cm", "longitudinal"): lambda m: _force_per_cm(m, "longitudinal"),
    ("breaking_force_n_per_cm", "transverse"): lambda m: _force_per_cm(m, "transverse"),
}


def _force_per_cm(m: Material, direction: str) -> Optional[float]:
    force = getattr(m, f"force_{direction}_newtons", None)
    if force is None:
        return None
    length = str(m.stretch_test_length or "5cm")
    width = 2.5 if "2.5" in length.replace(",", ".") else 5.0
    return float(force) / width


@dataclass
class ResolvedMaterial:
    material: Material
    variables: List[SampleVariable] = field(default_factory=list)
    catalog_values: Dict[str, float] = field(default_factory=dict)


@dataclass
class ResolutionResult:
    materials: List[ResolvedMaterial]
    variables: List[SampleVariable]
    assumptions: List[Dict[str, Any]]
    warnings: List[str]
    # for the calculation trace / methodology subtab
    trace: List[Dict[str, Any]]


def _latest_effective_distribution(
    db: Session, material_id, property_key: str, direction: str
) -> Optional[MaterialPropertyDistribution]:
    rows = (
        db.query(MaterialPropertyDistribution)
        .filter(
            MaterialPropertyDistribution.material_id == material_id,
            MaterialPropertyDistribution.property_key == property_key,
            MaterialPropertyDistribution.direction == direction,
            MaterialPropertyDistribution.population_scope == "accepted_units",
        )
        .order_by(MaterialPropertyDistribution.version.desc())
        .all()
    )
    for r in rows:
        if r.effective_to is None:
            return r
    return rows[0] if rows else None


def resolve_design_distributions(db: Session, vest: Vest) -> ResolutionResult:
    """Resolve every simulatable property for every material in the design."""
    layers = (
        db.query(VestLayer)
        .filter(VestLayer.vest_id == vest.id)
        .order_by(VestLayer.layer_index)
        .all()
    )
    materials: List[Material] = []
    seen = set()
    for layer in layers:
        if layer.material_id and layer.material_id not in seen:
            mat = db.query(Material).filter(Material.id == layer.material_id).first()
            if mat:
                materials.append(mat)
                seen.add(layer.material_id)

    result = ResolutionResult(materials=[], variables=[], assumptions=[], warnings=[], trace=[])

    for mat in materials:
        rm = ResolvedMaterial(material=mat)
        for property_key, direction, unit in SIMULATED_PROPERTIES:
            nominal = CATALOG_NOMINAL[(property_key, direction)](mat)
            if nominal is not None:
                rm.catalog_values[f"{property_key}|{direction}"] = nominal

            spec_row = (
                db.query(MaterialPropertySpec)
                .filter(
                    MaterialPropertySpec.material_id == mat.id,
                    MaterialPropertySpec.property_key == property_key,
                    MaterialPropertySpec.direction == direction,
                )
                .first()
            )
            dist_row = _latest_effective_distribution(db, mat.id, property_key, direction)

            var_key = f"{mat.name}|{property_key}|{direction}"
            trace_entry: Dict[str, Any] = {
                "variable": var_key,
                "material": mat.name,
                "property_key": property_key,
                "direction": direction,
                "unit": unit,
                "catalog_nominal": nominal,
            }

            if dist_row is not None:
                spec = {"family": dist_row.family, "parameters": dict(dist_row.parameters_json)}
                provenance = dist_row.provenance
                basis = f"material_property_distributions#{dist_row.version}"
            else:
                # try measurements
                meas = (
                    db.query(MaterialPropertyMeasurement)
                    .filter(
                        MaterialPropertyMeasurement.material_id == mat.id,
                        MaterialPropertyMeasurement.property_key == property_key,
                        MaterialPropertyMeasurement.direction == direction,
                    )
                    .all()
                )
                raw = [m for m in meas if m.is_raw_measurement]
                derived = [m for m in meas if not m.is_raw_measurement and m.method == "report_derived"]

                if len(raw) >= 3:
                    spec = {"family": "empirical_bootstrap",
                            "parameters": {"values": [float(m.value) for m in raw]}}
                    provenance = "measured"
                    basis = f"{len(raw)} raw measurements"
                elif derived:
                    # report-derived mean + absolute SD
                    d0 = derived[0]
                    sigma = float(d0.measurement_uncertainty) if d0.measurement_uncertainty else None
                    if sigma and sigma > 0:
                        spec = {"family": "truncated_normal",
                                "parameters": {"mu": float(d0.value), "sigma": sigma, "lower": 0.0}}
                        provenance = "report_derived"
                        basis = "report mean + sample SD"
                    else:
                        spec = {"family": "constant", "parameters": {"value": float(d0.value)}}
                        provenance = "catalog_nominal"
                        basis = "report mean, no SD"
                elif spec_row and spec_row.lower_limit is not None and spec_row.upper_limit is not None:
                    ref = float(spec_row.reference_value) if spec_row.reference_value else nominal
                    spec = {"family": "triangular",
                            "parameters": {"a": float(spec_row.lower_limit),
                                           "b": float(spec_row.upper_limit),
                                           "c": ref}}
                    provenance = "spec_window"
                    basis = "specification limits"
                elif (property_key == "thickness_mm" and nominal is not None
                      and _tolerance_bounds(mat.thickness_tolerance_mm, nominal) is not None):
                    lo, hi = _tolerance_bounds(mat.thickness_tolerance_mm, nominal)
                    spec = {"family": "triangular",
                            "parameters": {"a": lo, "b": hi, "c": nominal}}
                    provenance = "spec_window"
                    basis = "material thickness tolerance field"
                elif nominal is not None:
                    # missing tolerance -> labeled assumed default + warning
                    lo = nominal * (1 - DEFAULT_ASSUMED_REL_TOLERANCE)
                    hi = nominal * (1 + DEFAULT_ASSUMED_REL_TOLERANCE)
                    spec = {"family": "triangular",
                            "parameters": {"a": lo, "b": hi, "c": nominal}}
                    provenance = "assumed"
                    basis = f"default ±{DEFAULT_ASSUMED_REL_TOLERANCE:.0%} triangular (no spec on record)"
                    result.warnings.append(
                        f"{mat.name} {property_key} ({direction}): no spec/tolerance on record; "
                        f"using assumed ±{DEFAULT_ASSUMED_REL_TOLERANCE:.0%} triangular around {nominal:.4g} {unit}."
                    )
                else:
                    result.warnings.append(
                        f"{mat.name} {property_key} ({direction}): no data; property not simulated."
                    )
                    trace_entry.update({"skipped": True, "reason": "no data"})
                    result.trace.append(trace_entry)
                    continue

            var = SampleVariable(
                key=var_key,
                material=mat.name,
                property_key=property_key,
                direction=direction,
                spec=spec,
                scope="unit",
                scope_id="unit",
                provenance=provenance,
            )
            rm.variables.append(var)
            result.variables.append(var)
            trace_entry.update({
                "family": spec["family"],
                "parameters": spec["parameters"],
                "provenance": provenance,
                "basis": basis,
                "spec_window": (
                    {"lower": float(spec_row.lower_limit), "upper": float(spec_row.upper_limit)}
                    if spec_row and spec_row.lower_limit is not None else None
                ),
            })
            result.trace.append(trace_entry)

        result.materials.append(rm)

    return result


def draws_to_property_overrides(
    resolution: ResolutionResult, draw: Dict[str, float]
) -> Dict[str, Dict[str, Any]]:
    """Map sampled variable draws to material_properties overrides for the
    feature contract. Derived quantities (stack thickness/mass, densities)
    are recomputed inside the contract — never sampled independently."""
    overrides: Dict[str, Dict[str, Any]] = {}
    for var in resolution.variables:
        value = draw.get(var.key)
        if value is None:
            continue
        feature_key = PROPERTY_TO_FEATURE_KEY.get(f"{var.property_key}|{var.direction}")
        if feature_key is None:
            feature_key = PROPERTY_TO_FEATURE_KEY.get(var.property_key)
        if feature_key is None:
            continue
        overrides.setdefault(var.material, {})[feature_key] = value
    return overrides
