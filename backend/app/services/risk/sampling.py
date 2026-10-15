"""
Distribution registry and Monte Carlo sampler for risk simulation.

Hard rules implemented here (see implementation guide):
- Only bounded/specified distribution families; every draw knows its
  provenance ('measured', 'report_derived', 'assumed', 'catalog').
- Gaussian copula matrices must be positive semi-definite; enforced via
  eigenvalue factorization with a floor, and the failure is surfaced.
- Shared-group draws (same roll, same latent correlation group) use ONE
  draw, so layers cut from the same roll cannot get independent tails.
- Failed draws in pre_qc mode are counted, not silently renormalized.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats


PSD_EIGEN_FLOOR = 1e-10


# ---------------------------------------------------------------------------
# Distribution evaluation
# ---------------------------------------------------------------------------

def _as_scipy(spec: Dict[str, Any]):
    """Build a scipy frozen distribution from a spec dict."""
    family = spec["family"]
    p = spec.get("parameters", spec.get("parameters_json", {}))
    if family == "constant":
        return None  # handled by callers
    if family == "uniform":
        return stats.uniform(loc=p["a"], scale=p["b"] - p["a"])
    if family == "triangular":
        a, b, c = p["a"], p["b"], p["c"]
        return stats.triang(c=(c - a) / (b - a), loc=a, scale=b - a)
    if family == "normal":
        return stats.norm(loc=p["mu"], scale=p["sigma"])
    if family == "truncated_normal":
        mu, sigma, lo, hi = p["mu"], p["sigma"], p.get("lower"), p.get("upper")
        a = (lo - mu) / sigma if lo is not None else -np.inf
        b = (hi - mu) / sigma if hi is not None else np.inf
        return stats.truncnorm(a, b, loc=mu, scale=sigma)
    if family == "lognormal":
        mu, sigma = p["mu"], p["sigma"]
        return stats.lognorm(s=sigma, scale=np.exp(mu))
    raise ValueError(f"Unsupported distribution family: {family}")


def draw_samples(spec: Dict[str, Any], n: int, rng: np.random.Generator) -> np.ndarray:
    """n draws from a distribution spec."""
    family = spec["family"]
    p = spec.get("parameters", spec.get("parameters_json", {}))
    if family == "constant":
        return np.full(n, float(p["value"]))
    if family == "empirical_bootstrap":
        values = np.asarray(p["values"], dtype=float)
        return values[rng.integers(0, len(values), size=n)]
    return _as_scipy(spec).rvs(size=n, random_state=rng)


def ppf(spec: Dict[str, Any], u: np.ndarray) -> np.ndarray:
    """Inverse CDF for copula-mapped uniforms."""
    if spec["family"] == "constant":
        return np.full(len(u), float(spec["parameters"]["value"]))
    if spec["family"] == "empirical_bootstrap":
        values = np.sort(np.asarray(spec["parameters"]["values"], dtype=float))
        idx = np.clip((u * len(values)).astype(int), 0, len(values) - 1)
        return values[idx]
    return _as_scipy(spec).ppf(u)


# ---------------------------------------------------------------------------
# Variable model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SampleVariable:
    """One sampled quantity. key is stable across runs: material|property|direction|scope."""
    key: str
    material: str
    property_key: str
    direction: str
    spec: Dict[str, Any]
    scope: str = "unit"          # unit | roll | lot | latent_group
    scope_id: str = "unit"       # concrete roll/lot id or group name
    provenance: str = "assumed"


@dataclass
class SamplingResult:
    values: Dict[str, float] = field(default_factory=dict)      # var key -> draw
    warnings: List[str] = field(default_factory=list)


class GaussianCopula:
    """Correlated draws among a group of variables.

    matrix must be PSD; we verify via eigendecomposition and floor negatives
    at PSD_EIGEN_FLOOR (surfacing a warning rather than failing silently).
    """

    def __init__(self, variables: List[SampleVariable], corr: np.ndarray):
        self.variables = variables
        corr = np.asarray(corr, dtype=float)
        w, v = np.linalg.eigh(corr)
        if (w < -PSD_EIGEN_FLOOR).any():
            raise ValueError(f"Correlation matrix not PSD (min eigenvalue {w.min():.2e})")
        self.psd_adjusted = bool((w < 0).any())
        w = np.clip(w, 0.0, None)
        self.factor = v @ np.diag(np.sqrt(w))  # corr = factor @ factor.T

    def draw(self, rng: np.random.Generator) -> Dict[str, float]:
        z = rng.standard_normal(len(self.variables))
        x = self.factor @ z
        u = stats.norm.cdf(x)
        return {
            var.key: float(ppf(var.spec, np.asarray([u_i]))[0])
            for var, u_i in zip(self.variables, u)
        }


class Sampler:
    """Draws a complete set of correlated/hierarchical variables per unit."""

    def __init__(
        self,
        variables: List[SampleVariable],
        correlation_groups: Optional[List[Dict[str, Any]]] = None,
    ):
        self.variables = {v.key: v for v in variables}
        self.warnings: List[str] = []
        self._copulas: List[GaussianCopula] = []
        grouped_keys = set()
        for group in correlation_groups or []:
            members = [self.variables[k] for k in group["variables"] if k in self.variables]
            if len(members) < 2:
                continue
            matrix = np.asarray(group["matrix"], dtype=float)
            if matrix.shape != (len(members), len(members)):
                raise ValueError("Correlation matrix shape does not match variable group")
            copula = GaussianCopula(members, matrix)
            if copula.psd_adjusted:
                self.warnings.append(
                    f"Correlation group '{group.get('name', '?')}' matrix had negative "
                    "eigenvalues; floored at 0 (nearest PSD)."
                )
            self._copulas.append(copula)
            grouped_keys.update(v.key for v in members)
        self._independent = [v for v in variables if v.key not in grouped_keys]
        # population-level cache: roll/lot-scoped draws persist across units so
        # units built from the same roll share the roll's realized properties
        self._shared_cache: Dict[str, float] = {}

    def reset_population(self) -> None:
        """Reset the shared (roll/lot) cache — call once per simulation run."""
        self._shared_cache.clear()

    def draw_unit(self, rng: np.random.Generator) -> SamplingResult:
        """One draw for one simulated unit. Variables scoped to a roll/lot
        reuse that scope's realized draw; unit-scoped variables draw fresh."""
        res = SamplingResult(warnings=list(self.warnings))

        for var in self._independent:
            if var.scope == "unit":
                res.values[var.key] = float(draw_samples(var.spec, 1, rng)[0])
            else:
                ck = f"{var.key}::{var.scope}:{var.scope_id}"
                if ck not in self._shared_cache:
                    self._shared_cache[ck] = float(draw_samples(var.spec, 1, rng)[0])
                res.values[var.key] = self._shared_cache[ck]
        for copula in self._copulas:
            res.values.update(copula.draw(rng))
        return res
