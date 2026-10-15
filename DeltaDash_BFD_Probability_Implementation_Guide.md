# DeltaDash BFD probability analytics: evidence, implementation, and tests

**Prepared:** 2026-10-13. **Audience:** an implementation model with access to the DeltaDash repository and database. **Deliverable scope:** an engineering design and implementation handoff; this review has not installed the feature or changed production data.

## 1. The decision and the user's requirements

Build correlated Monte Carlo analytics around a versioned, validated BFD predictor. Plot the simulated distribution and empirical exceedance curve. Offer a Gaussian overlay only when it adequately describes the relevant output, especially its tail. A Gaussian process model is a different optional modeling method; it is not required to obtain a Gaussian-looking graph.

Preserve these requirements:

1. Material identities, composition order, and layer counts are fixed within each simulation. Counts are not manufacturing random variables. A different layup is a different scenario.
2. The user's example of **−2.5% strength is a specification minimum**, not a standard deviation, confidence interval, or manufacturing frequency. Store it as `lower_spec = 0.975 * reference_value` for the specifically identified strength property. Do not apply it to every property automatically.
3. Include measurable material and ballistic-test variations, their dependencies, and the selected protocol. Distinguish prescribed conditions from random variation within a condition.
4. Answer: predicted BFD distribution, probability of exceeding a selected BFD threshold, worst feasible in-spec scenario, probability of a defined near-worst region, and expected outcomes per **1,000 vests** under a defined exposure/test plan.
5. Write results in terms of virtual vests/panels receiving that plan. An arbitrary mixture of historical shots is not a population of 1,000 manufactured vests.
6. The implementation model can inspect the database. It must inspect units and missingness, rather than assume that every column contains usable measurements.

**Feasible now:** a scenario engine, specification-envelope exploration, sensitivity graphs, measured-coupon distribution ingestion, and clearly labeled exploratory prediction distributions for supported inputs.

**Not established by the attachments:** reliable probabilities for small within-spec changes in all material properties, calibrated penetration risk, or a validated complete-protocol failure rate. The feature must be able to return `unavailable` for these outputs while still providing useful supported results.

## 2. Source review and attachment evidence

### 2.1 Exact sources

The local source checkout identifies commit `11b8d677d3199805ddd25faa31de715760ed4418`, dated 2026-09-24, message `1.4.1`. Its source inventory contains 313 entries. The supplied NPOptimized-6 metadata says application version `1.1.2`; this review uses the available checkout to explain the pipeline, without assuming that the training checkout was byte-for-byte identical.

| Source | Contents | SHA-256 |
|---|---|---|
| `NPOptimized-6_20260908_172840.zip` | Metadata, preprocessor, BFD regressor, perforation classifier, pass/fail classifier | `3bfbe9675e166e5eb3cc94858083c1c6e8b5ea1af3109168cdfa61200971c934` |
| `deltadash_backup_20261013_150628.zip` | PostgreSQL SQL dump, seven test workbooks, five scanned material reports, filesystem model artifacts | `a7ad09e8cdc0d9899336d326fc483254acb8cffe03ab9fd77d159becea270d4f` |

The SQL dump was read without executing it. All COPY tables were inventoried; application tables relevant to this analysis were parsed. All seven supporting workbooks were extracted, and the ten pages across the five scanned PDFs were rendered and reviewed. Pickled model artifacts were loaded only for offline inspection/replay. No live database, model activation, training, or deployment was performed.

### 2.2 Model identity and metrics

| Field | Supplied NPOptimized-6 | Backup filesystem model |
|---|---|---|
| Version | `20260908_172840` | `20260903_151448` |
| Display name | NPOptimized-6 | NPOptimized-5 |
| Recorded rows | 3,639 | 3,790 |
| Synthetic anchor-generated rows | 1,875 | 1,750 |
| Non-anchor rows implied by subtraction | 1,764 | 2,040 |
| Raw input feature columns | 371 | 360 |
| Stored BFD MAE | 0.27846 mm | 0.24923 mm |
| Stored BFD RMSE | 0.59781 mm | 0.61404 mm |
| Stored BFD MAPE | **2.37419%** | 2.39030% |

These stored errors are fitted-data metrics in the inspected training implementation. `train_from_dataframe()` fits the preprocessor on the full input, fits each estimator on all its valid target rows, then predicts those same rows to calculate the metrics. NPOptimized-6 uses 7,444 estimators and maximum depth 22. This is not evidence of an independently measured 2.37% prediction error on new lots or new designs.

The user's reported “3.x%” could refer to the UI health calculation or a different subset. The package does not store a 3.x% holdout evaluation or the exact evaluation IDs. Preserve the user's observation, but label the available evidence accurately. The backup's database model records do not include NPOptimized-6; they include Optimized-7, Optimized-8, and NPOptimized-5. The latter has `training_avg_error = 5.36`, showing that database/UI metrics and filesystem metadata are not interchangeable. Do not silently activate NPOptimized-5 because it is the backup's filesystem default, or label it NPOptimized-6.

Synthetic rows make up approximately **51.5%** of NPOptimized-6's recorded input rows. They represent assumed boundary behavior, not observed production units. Some use zero velocity or extreme counts/thickness. Keep them out of evaluation, residual calibration, manufacturing distribution fitting, and estimates of real-data support. The `pass_fail` labels from `ShotData` are absent in the inspected fetcher; its pass/fail training labels are supplied by anchors. That classifier is not an empirical complete-protocol pass/fail model.

### 2.3 Database inventory

| Table or data element | Observed count | Consequence |
|---|---:|---|
| `shot_data` | 2,508 | This is the actual training source used by the main service |
| Numerical `trauma_mm` in `shot_data` | 1,811 | Not all shots have measured BFD |
| Numerical `velocity_m_s` | 2,146 | Missing velocity needs explicit handling |
| `test_sessions` | 267 | Parent/child sessions must be grouped for validation |
| `vests` | 40 | Catalog/design identifiers are not unique manufactured specimens |
| `vest_layers` | 129 | Provides ordered material/count relationships |
| `materials` | 27 | Catalog properties, not a lot measurement history |
| Materials with tensile strength in MPa | **0** | No trained within-material MPa strength sensitivity can be established |
| Materials with modulus in GPa | **0** | Same limitation for modulus |
| Materials with thickness tolerance | **0** | Thickness spec bounds must be supplied/recovered |
| Materials with directional breaking force | 15 | Useful after checking units and statistics |
| Materials with density in g/cm³ | **0** | Current composition-density calculation has missing inputs |
| `ammunition` | 15 | Identity must include projectile type, not caliber alone |
| `protocols` | 5 | Only three have populated levels/configurations |
| Anchor definitions / anchor layers | 125 / 125 | Separate source class |
| `shots`, `armor_panels`, `armor_panel_layers`, `predictions`, `material_documents` | **0 each** | Designed schema capabilities are not proof of populated measurement history |

The 1,811 BFD values are not 1,811 independent vests. There are front/back shots, repeated shots, wet/ambient conditions, parent/child sessions, and multiple tests of the same design. A preliminary matching-key scan found 202 extra records in 146 groups sharing date, design, vest number, side, condition, shot number, caliber, velocity, and BFD. These are **duplicate candidates**, not authorized deletions. Resolve their source identity before splitting data.

Only 14 shot records have qualitative result text: 13 `OK` and one `PERFORO`; 2,494 are missing. Do not convert those missing results into “no penetration.” The inspected fetcher recognizes the positive token but does not recognize `OK` as a negative. A numeric BFD alone is not enough to invent a penetration label.

### 2.4 New and useful information in the scanned material reports

Reports OT 30174, OT 300175, OT 30176, OT 30177, and OT 30178 contain five coupon measurements per direction, grammage measurements, and reported mean/standard deviation. Page 1 has tensile/elongation data; page 2 has tear measurements and notes. The supplied workbook files contain ballistic test results, not a lot-linked manufacturing property history.

**Confirmed semantic mismatch:** database columns named `force_*_error_percent` contain values matching the reports' absolute standard deviations in N/cm, rather than percentages. For example, CS-3041 has longitudinal mean 1,593.6 N/cm, SD 81.2 N/cm, and the database's percent-named column stores `81.2`. Its relative SD is approximately `100 * 81.2 / 1593.6 = 5.095%`.

| Material/report | Longitudinal mean N/cm | Reported SD N/cm | Relative SD, % |
|---|---:|---:|---:|
| FLEX_KS3000 / OT 30178 | 666.8 | 22.1 | 3.314 |
| CS-2041 / OT 30174 | 1,570.0 | 63.0 | 4.013 |
| CS-3041 / OT 300175 | 1,593.6 | 81.2 | 5.095 |
| CS-302E / OT 30176 | 1,388.5 | 53.9 | 3.882 |
| CS-3021 / OT 30177 | 814.3 | 25.4 | 3.119 |

The database stores the corresponding mean breaking loads in newtons as 2.5 times the report's N/cm mean for these materials, consistent with conversion through a 2.5 cm specimen width. `fetch_material_properties()` divides those newton means by 2.5 to recover N/cm. The percent-named SD entries were not converted the same way. **Do not divide those particular SD values by width again or treat them as percent.** Preserve the original report units and provenance before choosing a canonical storage unit.

Likewise, an elongation SD such as 0.7 accompanying a mean elongation of 8.8% is 0.7 percentage points, unless the source explicitly says relative percent error. It is not automatically 0.7% of 8.8.

Five coupons from one submitted sample are useful local variation evidence. They cannot establish between-roll variation, lot-to-lot correlation, or one-in-a-thousand tails. The reports do not supply an explicit lot/roll-to-tested-panel linkage. Matching coupon index numbers across directions is not proof that longitudinal and transverse measurements are paired observations.

### 2.5 Offline replay and sensitivity checks

A read-only replay used the checkout's feature functions and backup records with the supplied artifacts. The environment used XGBoost 2.0.2, scikit-learn 1.3.2, NumPy 1.26.4, and SciPy 1.11.4; the persisted preprocessor reports scikit-learn 1.3.0. The patch-version warning remains a limitation. Reproduce in the production-pinned runtime before treating these numbers as official model metrics.

The “saved composition properties” replay uses metadata's material-property snapshot for composition features while retaining raw aggregates and other records reconstructed from the current backup. It is **not a reconstruction of the exact training snapshot**.

| Model/input route | Measured-BFD rows | Replay MAE, mm | Replay MAPE |
|---|---:|---:|---:|
| NPOptimized-6, saved composition properties/current records | 1,811 | 0.960 | 5.912% |
| NPOptimized-6, backup catalog/current records | 1,811 | 1.043 | 6.402% |
| NPOptimized-5, saved composition properties/current records | 1,811 | 0.855 | 6.640% |
| NPOptimized-5, backup catalog/current records | 1,811 | 0.903 | 6.991% |

Forty-eight measured shots were imported after September 8 and have test date September 17. NPOptimized-6's replay MAE on these was approximately **8.59 mm**, with MAPE approximately 69.4%. These shots cover only two design records and two closely related workbook groups; they are not a representative held-out manufacturing population. Low BFD values amplify MAPE. The exact training-membership manifest is missing. Investigate input/identity mapping, conditioning changes, missingness, source-version differences, and support before attributing the difference solely to model quality.

Existing catalog values also changed since the model snapshot. FLEX_KS3000's snapshot grammage is 78 g/m² versus 82 in the backup; its snapshot longitudinal force is 560.68 N/cm versus 666.8 recovered from the backup. CS-2041/3021/302E/3041 lack force entries in the supplied model snapshot but have measurements in the current database. Replaying historical tests with today's catalog changes their features without a new ballistic measurement.

Exploratory −2.5% perturbation of all available directional breaking-force means changed 1,367/1,811 predictions. −2.5% thickness changed 1,810/1,811. A tensile-strength perturbation changed **0/1,811**, including no change to the feature matrix, because MPa values were missing. +2.5% velocity changed 1,785/1,811 predictions. These are sensitivity checks across mixed historical records, **not in-spec simulations**: actual property bounds were unavailable, and the velocity perturbation can exceed protocol windows.

The force decrease and velocity increase both reduced average predicted BFD in these mixed-record checks. That is a reason to examine model response and conditional support; it is not a physical conclusion that weaker armor or faster bullets are safer. A tree model can respond to features as catalog/design proxies, and local steps or cross-material associations are not a measured within-roll response law.

## 3. Repository map and required corrections

Use the main application's paths below. A second pipeline exists under `backend/ml/`; do not silently implement the feature against that older/simpler service while the ballistic API uses the main service.

| Area | Current path | Action |
|---|---|---|
| Training data assembly | `backend/app/services/ml/data_fetcher.py` | Preserve IDs/provenance, fix labels, use as-tested property snapshots |
| Main features, training, inference | `backend/app/services/ml/ballistic_ml.py` | Shared feature contract, immutable bundles, real grouped validation |
| Ballistic API | `backend/app/api/v1/ballistic.py` | Add scenario/run endpoints with existing authentication conventions |
| App routing | `backend/app/main.py` | Register any separate risk router under `/api/v1` |
| Protocol prediction paths | `backend/ml/prediction_service.py` and ballistic API | Audit actual callers and avoid a third inconsistent implementation |
| Analytics API | `backend/app/api/v1/analytics.py` | Reuse read-only filters; do not equate chart aggregates with population estimates |
| Analytics UI | `frontend/src/pages/Analytics.tsx` | Add a probability view using existing Plotly |
| Model UI | `frontend/src/pages/ModelTraining.tsx` | Separate training-fit, replay, and independent-validation metrics |
| Protocol/material UI | `frontend/src/pages/Protocols.tsx`, `Materials.tsx` | Bounds, units, source type, and data-readiness controls |
| Existing schema | `backend/app/db/models/` | Add explicit specimen/lot measurements and simulation tables |
| Migrations | `backend/migrations/versions/` | Additive migrations with provenance-preserving backfill |
| Earlier platform specification | `ballistic_analytics_platform_spec.md` | Already calls for uncertainty/penetration separation; treat as design intent, not completed capability |

### P0: correct before publishing manufacturing probabilities

1. **Statistical field semantics:** preserve raw report values; migrate ambiguous percent-named fields into explicit `standard_deviation`, `coefficient_of_variation`, `uncertainty`, or `specification_limit` properties with units and source. Correct only values whose source was verified. Keep an audit trail.
2. **Label mapping:** recognize negated terms before positive substring matches; map `OK` explicitly when its source semantics establish nonpenetration. Use enumerated labels and an `unknown` state. `no perforado`, `sin perforación`, and `no penetration` must not match as positive solely because they contain `perfor` or `penetr`. Distinguish partial penetration, complete penetration, and BFD-limit exceedance.
3. **Areal density:** `parse_vest_composition()` reads `areal_density_g_m2` but calculates segment areal density as `count * thickness_mm * density_g_cm3`. All 27 density entries are missing, so that path produces zero composition areal density despite recorded grammage. Prefer `count * areal_density_g_m2 / 1000` kg/m². Use thickness × volumetric density only as an explicitly sourced fallback. Retain an old feature contract for old artifacts; retrain a new version after correcting features.
4. **Training/inference parity:** `prepare_single_input()` does not pass the saved feature toggles to engineering, and its categorical-default list omits composition sequence/name features used in training. Missing-value filling can depend on the current prediction batch's median. Use the fitted training imputer; inference of a row must not change when unrelated rows are added to its batch. Test all derived fields, not only final feature count.
5. **Model selection:** `load_model_version()` writes shared current artifact files/metadata. Concurrent requests can mix models. Replace prediction-time activation with immutable in-memory bundles resolved by version. Pass metadata, feature toggles, material snapshots, preprocessor, regressor, classifiers, calibration, and hashes explicitly. Do not replace production artifacts while loading a version for simulation.
6. **Calibration/evaluation:** stored training error, training-set health checks, and synthetic anchor scores must not supply probability distributions or tail confidence. Generate real grouped out-of-sample residuals and evaluation manifests.
7. **Spec/property linkage:** populate identified material limits and as-tested lot/roll measurements. A strength variable absent from training cannot become learned merely by adding a slider or turning a feature toggle on.
8. **Joint outcomes:** keep penetration separate from numerical BFD. Do not make penetration zero millimeters or turn a raw classifier score into calibrated risk. The current `perforation_probability > 0.9` display suppression is a UI heuristic, not the probabilistic definition.
9. **Identity/support:** match ammunition by stable projectile identity; handle old names/aliases with a documented mapping, not fuzzy guesses or a caliber dictionary that overwrites multiple projectile types. Reconcile candidate duplicate imports. Keep IDs for splitting while excluding them from predictors.
10. **Protocol interpretation:** database velocity windows are stored configuration. Require a versioned interpretation of lower/upper accepted velocities, angles, shot patterns, conditioning, and decision rules. Some levels have no configuration; a “± window” must not be inferred where the rule is one-sided. Do not silently treat the stored window as a velocity SD or a certification rule.

## 4. Exactly what the probabilities mean

### 4.1 A worst case is not a probability

For continuous distributions, the exact event “strength equals the minimum, thickness equals the minimum, and velocity equals the maximum” normally has probability zero. The endpoints can nevertheless define a useful stress scenario. Measured/rounded data or real point masses can make endpoint probabilities nonzero; specify that representation explicitly.

Define a finite event for “everything goes badly,” for example:

```text
Strength lies in the lowest 5% of its accepted-unit distribution,
thickness lies in the lowest 5%,
and velocity lies in the highest 5%,
within the same scenario and manufacturing/test hierarchy.
```

With three independent factors, this event has probability `0.05^3 = 0.000125`: 0.0125%, or 0.125 expected events per 1,000 exposures. If strength and thickness share one perfectly correlated factor, it is `0.05^2 = 0.0025`: 0.25%, or 2.5 per 1,000. These are mathematical examples, not DeltaDash rates.

Alternatively define a physical band, such as the bottom 0.25% of a property's allowed numeric range. Display the event inequalities and units. A percentile band and a specification-range band are different events.

Never multiply the per-layer tail probabilities when layers come from the same roll. A roll-level weakness can affect every layer together; fixed counts do not remove common material variation.

### 4.2 Minimum outputs, separately named

For a selected threshold `T` and exposure plan, return:

| Output | Definition |
|---|---|
| Nominal prediction | Predictor at selected nominal inputs, not automatically the distribution mean |
| Input-variation distribution | Distribution of `f(X)` from sampled inputs only |
| Predictive BFD distribution | Sampled supported inputs plus validated outcome residual variability; conditional on no complete penetration |
| Per-shot BFD exceedance | `P(Y > T | no penetration)` for that shot/condition, or the specified alternative comparison |
| Unconditional stopped-but-high-BFD risk | `P(no penetration AND Y > T)` |
| Complete penetration probability | Calibrated probability if supported; otherwise `null` with reason |
| Combined per-shot unacceptable outcome | `P(penetration OR stopped-but-high-BFD)` |
| Protocol-unit unacceptable outcome | Probability of at least one defined unacceptable outcome across that virtual unit's exposure plan |
| Protocol maximum BFD | Distribution of maximum valid measured BFD among nonpenetrating shots; show penetration outcomes separately |
| Near-worst event probability | Frequency of explicitly defined finite input event |
| Stress-envelope result | Largest predicted BFD found over feasible in-spec inputs, with search/support limits |
| Per 1,000 | `1000 * p` expected count for the specifically named event/population |

For one shot, with calibrated penetration probability `p_pen(X)` and conditional BFD exceedance `p_bfd(X)`, combined risk is:

```text
E_X[p_pen(X) + (1 - p_pen(X)) * p_bfd(X)]
```

Do not add the two probabilities directly, multiply their marginal averages, or estimate a full CDF from a single conformal interval. For multi-shot plans use a joint simulation with shared factors. Conditional independence may be used only as an explicitly justified scenario assumption.

The criterion `Y > 44 mm` can be a user-selected engineering screen, but this guide does not declare it to be the entire decision rule of any named certification program. Store the threshold, strict/inclusive comparison, rule source, and protocol version. Certification sample acceptance and “probability that a vest exceeds a BFD screen” are different questions.

### 4.3 Per 1,000 and uncertainty

For a common marginal probability `p`, the expected number among 1,000 is `1000*p`, including nonintegers. If the units are independent with identical `p`, the count is binomial and:

```text
P(at least one) = 1 - (1 - p)^1000
```

For 1,000 units from shared production lots, the expected count still follows linearity of expectation, but the binomial count interval and the formula above generally fail. Draw shared lot effects once per lot, then generate units within it. Integrate the conditional count distribution or simulate replicate lots of 1,000. For varying independent `p_i`, use a Poisson-binomial count model, not a single binomial by default.

Keep these three types of uncertainty separate in API/UI:

- Monte Carlo numerical uncertainty: finite draws with fixed model and input distributions.
- Parameter/model uncertainty: finite real measurements, distribution fitting, predictor/calibration uncertainty.
- Future population variation: the possible count in another batch of 1,000.

A large Monte Carlo sample reduces only the first. It does not compensate for five material coupons or one labeled penetration result.

## 5. New data contract and additive database schema

Use UUIDs, existing timestamps/authentication, Alembic conventions, foreign keys, audit records, and units. The following are proposed additions, not existing tables. Favor normalized measurement rows and JSONB for immutable scenario snapshots/results.

### 5.1 Material property measurements

Add:

```text
material_lots
  id, material_id, supplier_lot_code, received_at, source_document_id
material_rolls
  id, material_lot_id, supplier_roll_code
material_property_measurements
  id, material_id, lot_id, roll_id, coupon_id, specimen_position
  property_key, direction, value, unit, measured_at, method
  specimen_width_mm, gauge_length_mm, test_temperature_c
  measurement_uncertainty, uncertainty_kind, coverage_factor
  source_document_id, source_page, source_table, source_row
  is_raw_measurement, review_status
material_property_specs
  id, material_id, property_key, direction, unit
  reference_value, lower_limit, upper_limit
  effective_from, effective_to, source_document_id, approved_by
```

Suggested keys: `breaking_force_n_per_cm`, `tensile_strength_mpa`, `thickness_mm`, `areal_density_g_m2`, `elongation_percent`, `modulus_gpa`. Direction is `longitudinal`, `transverse`, or `none`. Preserve actual breaking force and specimen width if they are measured. Do not confuse width with tensile-test gauge length. MPa conversion requires a defensible cross-sectional area; a fabric breaking load per width is not automatically fiber tensile stress.

Migrate raw coupon rows from the five reports, not just their means. Store the report's mean and SD as reported summary evidence or derive them reproducibly from the rows. Check sample-SD convention and rounding; do not silently substitute population SD. Keep nominal catalog properties separate from sample averages and approved bounds.

Add `material_property_distributions` with: property/spec reference, population scope (`lot`, `roll`, `coupon`), family, parameters, latent correlation group, measured-versus-assumed provenance, measurement IDs, accepted/pre-QC population, fit diagnostics, sample/group counts, effective dates, version/hash, and approval metadata.

**Allowed distribution families:** measured empirical bootstrap, fitted normal, truncated normal, lognormal, bounded uniform, triangular, constant. Assumed distributions must remain visibly labeled. Never infer SD as tolerance/3 or infer a relative percent SD from an ambiguous `error_percent` column.

### 5.2 As-tested specimen and property linkage

Reuse/populate `armor_panels` if it can represent unique specimens; otherwise add an explicit `tested_specimens` table. In either case, add:

```text
test_specimen_id: unique physical panel identity
manufactured_unit_id / serial_number: unique vest identity where available
production_lot_id
panel_layer_material_assignments:
  panel_id, layer_start, layer_end, material_id, material_lot_id, roll_id
as_tested_property_snapshots:
  panel_id, property_key, material_id, direction, value, unit
  measurement_ids, aggregation_method, source_quality
```

Link `shot_data` to the specimen and canonical ammunition record. Retain original imported text/row identity. Keep `vest_id` as design identity. Add outcome enums (`complete_penetration`, `partial_penetration`, `stopped`, `unknown`) and a shot-validity state with reason. Distinguish “BFD not measured” from “BFD invalid,” “penetration,” and a measured zero.

Environmental measurements should distinguish clay/backing temperature, ambient temperature, conditioning procedure, and measured material moisture. A missing ambient temperature is not standard temperature. A material's catalog value edited today must not rewrite the as-tested property snapshot of a historical panel.

### 5.3 Versioned protocol exposure plan

Add or snapshot a `protocol_revision` with:

```text
protocol_id, revision_id, level, rule_source, review_status
ammunition_id/projectile_identity per threat
shot number, specimen/panel assignment, side
prescribed angle and location, allowed velocity bounds
conditioning scenario and procedure
validity/reshoot rules
BFD comparison threshold and operator, penetration criterion
```

Do not generate front/back × wet/ambient × ammunition combinations and imply that they are all shots on one physical vest. State which panels or matched specimens receive each condition. Reuse common manufacture factors across representative matched panels only when the exposure design justifies it. A multi-specimen certification plan requires its own virtual sample mapping and rule interpreter.

### 5.4 Scenarios, runs, and calibration

Add:

```text
risk_scenarios
  id, name, design_id, design_revision, protocol_revision_id
  model_version, layer_snapshot_json, distribution_snapshot_json
  dependency_snapshot_json, outcome_rule_json
  population_mode, population_size, near_worst_event_json
  created_by, created_at, revision, content_hash
risk_simulation_runs
  id, scenario_id, scenario_hash, status, seed, requested_draws
  completed_independent_draws, model_bundle_hash, data_snapshot_hash
  calibration_version, feature_contract_version, runtime_versions_json
  assumptions_json, readiness_json, result_json, failure_reason
  started_at, completed_at
model_validation_runs
  id, model_version, dataset_hash, split_manifest_hash
  group_definition, train_ids, tuning_ids, calibration_ids, test_ids
  real_metrics_json, synthetic_diagnostics_json, coverage_json
  support_summary_json, residual_artifact_path, classifier_calibration_path
```

Every saved result must be reproducible against immutable identifiers. Editing a scenario creates a new revision. A failed/unsupported output uses `null` plus a reason; it must not become zero probability or a “PASS” card.

## 6. Statistical engine

### 6.1 Select a population before sampling

Two valid modes answer different questions:

1. **Accepted units:** distributions represent properties after incoming/production QC. Prefer measurements from accepted units or a documented truncated distribution. Report probabilities conditional on that acceptance population.
2. **Pre-QC production:** sample the original joint manufacturing process and apply QC/acceptance rules; report reject rate and performance of accepted versus unfiltered units separately.

Do not independently clip each sampled value to a limit. Clipping manufactures point masses at boundaries and changes event probabilities. A copula with individually truncated marginals is a valid explicitly specified joint model, but it is not generally identical to taking a pre-QC multivariate process and conditioning it on all specs being satisfied. If acceptance is joint, rejection/sample conditioning must operate on the joint process.

### 6.2 Manufacturing and test hierarchy

Start with shared latent factors:

```text
material lot -> roll -> panel/local material positions
production lot -> unit construction -> matched front/back panels
test session -> ammunition lot / velocity bias / backing calibration
shot -> residual velocity / local placement / outcome residual
```

For a scalar property on a layer cut from roll r:

```text
property(layer) = reference
                + lot effect
                + roll effect
                + local effect
```

Use measured variance components where possible. If only a single coupon sample exists, between-lot/roll components remain unknown. Expose dependency assumptions as scenarios; do not fit unidentifiable components to create false precision. Avoid assigning the entire coupon SD separately to lot, roll, and local components, which would triple-count variance.

At minimum, share each sampled roll-level property across all layers assigned to that roll. A material-name dictionary override can support one shared value per material in an exploratory first version; it cannot represent several rolls of the same material or layer-local measurements. Production implementation must use material/lot/roll assignment IDs, not only names.

Sample source physical properties once, then derive stack properties. With `n_i` fixed:

```text
total thickness (mm) = sum_i n_i * sampled_thickness_i
total areal density (kg/m²) = sum_i n_i * sampled_grammage_i / 1000
effective density (g/cm³) = total_areal_density_kg_m² / total_thickness_mm
```

Do not sample thickness, grammage, derived density, stack mass, and stack thickness independently if they describe the same underlying state. Preserve mechanical direction/orientation and ordered layer blocks. Where a learned feature aggregate requires weighting, use the exact versioned contract; propose physically improved aggregates only in newly retrained versions.

Velocity can have a session/ammunition-lot bias plus shot variation. Protocol angle, side, conditioning, and shot number normally follow the exposure plan rather than a distribution chosen from the historical dataset. Include measured angle/location variation only where both an allowed range and model support exist.

### 6.3 Correlated bounded sampling

A practical supported-input sampler uses a Gaussian copula:

1. Validate a symmetric unit-diagonal positive-semidefinite latent correlation matrix `R`.
2. Generate correlated standard normals `Z` using an eigenfactor, including singular matrices for perfectly shared effects.
3. Convert to uniforms `U = Φ(Z)`.
4. Apply each property's inverse CDF, including bounded/truncated distributions.

For a truncated normal, SciPy's bounds are standardized as `(lower - mu)/sigma` and `(upper - mu)/sigma`. Its `mu` and `sigma` describe the underlying untruncated normal; after truncation, the accepted-population mean and SD generally differ. Fit the right parameterization and verify resulting moments.

The latent `R` is not automatically the Pearson correlation of the transformed physical properties. Verify achieved correlations and fit the latent dependence if physical-scale correlations are the evidence supplied. Empirical joint bootstrap is preferable when adequate paired lot/roll measurements exist. A Gaussian copula can underrepresent some joint extremes; compare plausible dependency scenarios instead of claiming measured tail dependence from five coupons.

### 6.4 Predictor interface and immutable bundles

Create `backend/app/services/ml/model_bundle.py` and a new versioned shared feature builder, for example `backend/app/services/ml/feature_contract.py`:

```python
bundle = get_model_bundle(model_version, artifact_hash)
X = build_feature_batch(
    specimens=sampled_specimens,
    shots=exposure_plan,
    material_snapshot=bundle.material_snapshot,
    property_overrides=sampled_property_values,
    metadata=bundle.metadata,
    feature_contract_version=bundle.feature_contract_version,
)
prediction = bundle.predict_batch(X)  # loads once, transforms once per chunk
```

`bundle.predict_batch()` must apply the correct BFD target inverse transform exactly once. NPOptimized-6's regressor pickle is a dictionary with `model` and `use_log_transform`. Its output uses `expm1` when the flag is true. A transformed-log point prediction is not automatically the arithmetic conditional mean. If modeling residuals on the log scale, simulate those residuals before inversion or apply a validated smearing correction for a mean estimate.

Use canonical feature names/order, fitted preprocessing, stored toggles, consistent categorical values, and frozen nominal properties plus explicit measured overrides. Never read mutable global metadata during a run. Do not silently fill an unknown simulated property with zero. Return support/readiness failures for a requested variable with no learned or independently supplied response model.

Run batches in bounded chunks, initially 1,000–5,000 rows, with one loaded bundle per worker. Size draw counts against shot count and actual memory; a 100,000-unit, 24-shot simulation is 2.4 million inference rows. Cache only by immutable version/hash. Do not execute Python `predict()` and reload all files once per sample.

### 6.5 Residual uncertainty without double counting

Maintain two curves:

- `input_variation_only`: outputs of `f(X)`; identifies what the predictor does with measured/assumed input spread.
- `predictive_bfd`: outputs after a validated residual/outcome model; describes future measured BFD under its stated population.

Calibrate outcome residuals on real, nonpenetrating, valid measurements excluded from training and tuning. Use matched design/threat/condition groups and a test-session/panel hierarchy where supported. Compare a grouped residual bootstrap, hierarchical model, and conditional heteroscedastic residual model. Do not pool synthetic zero-BFD anchors or known penetrating shots into the residual distribution.

A legacy model trained on nominal catalog properties may have residual spread that already includes unobserved lot/property variation. Adding a newly sampled material distribution plus all that legacy residual spread can double-count the same variability. Until actual covariates are linked and retraining separates them, provide the exploratory input-only curve and a separately qualified empirical predictive baseline; do not merge them into a claimed calibrated manufacturing tail.

For a log-target residual model:

```text
z_pred = regressor(X)
z_future = z_pred + session/panel/shot log-residual components
BFD_future = expm1(z_future)
```

Negative simulated BFD requires an explicit nonnegative outcome model or a documented censoring/truncation rule; do not silently clip and ignore the introduced zero mass. Residual distributions can vary by threat/condition/BFD level. A single RMSE is not automatically a Gaussian SD, and MAPE is never a universal BFD SD.

Conformal prediction can be an additional interval layer when its group/exchangeability assumptions apply. It supplies coverage intervals, not a complete calibrated tail-probability distribution by itself. Evaluate interval coverage on untouched real groups and clearly distinguish a prediction interval from uncertainty in the estimated mean.

### 6.6 Penetration and multi-shot dependence

Calibrate penetration using real labeled shots with adequate positives and negatives, stable identities, and grouped validation. In this backup, labels are too sparse to support an empirical manufacturing penetration probability; return `null` with `insufficient_real_outcome_labels` unless stronger linked evidence is recovered. The existing synthetic-anchored classifier can be retained as an exploratory score clearly marked as such.

For each virtual unit, share sampled manufacture state across its panels as specified; share session/ammunition-lot state across relevant shots; vary shot-level state appropriately. Each exposure records penetration or a valid conditional BFD outcome. Any union risk uses those joint outcomes or a justified conditional probability calculation.

Do not compute protocol risk as `1-(1-p_shot)^N` from pooled shots unless independence and identical risk have actually been specified. Preserve shot order and spatial damage where data supports it. The current shot-number feature is not a validated model of arbitrary shot placement or damage evolution. Label these limitations, and return unsupported protocol risk if the requested exposure sequence exceeds validated support.

### 6.7 Worst feasible in-spec search

Return both:

1. **User-selected adverse corner:** the prescribed minimum strength/minimum thickness/maximum velocity combination, if physically feasible and supported. This is a named stress scenario, not a known frequency or mathematically proven maximum.
2. **Searched stress envelope:** evaluate feasible corners, a space-filling design, and bounded refinement to find the highest predicted BFD and highest separately defined combined-risk score.

Enforce physical constraints and distribution support. Individually in-spec marginals may form an impossible joint combination. Do not use derivatives alone for an XGBoost tree surface, or assume maximum velocity/minimum strength always maximizes BFD. Report the winning inputs, model version, feasibility check, support flags, search evaluations, and whether the result is merely the maximum found. A tree predictor flat beyond observed boundaries cannot prove safe extrapolation.

For probabilistic “worst 1 in 1,000,” report a supported 99.9th percentile of the specified outcome distribution. That is not the hard endpoint worst case or a guaranteed maximum for a batch of 1,000.

## 7. Training, validation, and readiness gates

### 7.1 Build a reproducible real-data manifest

Retain shot ID, physical specimen ID, parent test group, source file/sheet/row, design revision, manufacture lot/roll, measured properties, protocol revision, and import timestamp in an evaluation manifest. Exclude identity columns from model input but keep them for grouping and audit. Tag anchors as `synthetic_anchor`; they never count as observed panels or strengthen tail calibration.

Review duplicate candidates by provenance. Put all representations of the same physical test into the same partition; mark superseded imports rather than deleting uncertain records. Resolve inconsistent caliber names and source result meanings. Screen missing/invalid numerical values and invalid shots before defining each target population.

### 7.2 Partition by the question

For predicting new production of an existing design, split at production lot/roll and parent test group. For predicting an unseen layup, additionally hold out complete design groups. A random shot split leaks the repeated-panel and test-session state. `GroupKFold` is available in the existing scikit-learn 1.3 dependency; do not use newer API arguments such as its later-added shuffle option without upgrading explicitly.

Use separate development/tuning, calibration, and untouched test groups. Fit imputation, scaling, categorical encoding, feature selection, and any learned material distribution parameters using the appropriate development data only. Use nested group splits when hyperparameter search would otherwise reuse evaluation groups. Anchors may enter training with documented influence but never enter held-out empirical performance metrics. Compare training with and without them.

Do not claim a membership-disjoint holdout for the supplied artifact solely because an import is recent. Recover the exact training manifest where possible; otherwise use retraining with a new immutable manifest to make separation testable. New test dates are useful chronological diagnostics but do not supply enough diverse manufacture groups by themselves.

### 7.3 Evaluate what the feature will display

Record on real untouched groups:

- MAE/RMSE/bias in millimeters and median/p80/p90/p95 absolute errors, split by threat/design/condition and manufacture group.
- MAPE only for nonzero valid BFD, with exclusion count and warnings for small denominators; never mix millimeters for zero targets with percentages into one average.
- Coverage of 80%, 95%, and justified upper-tail predictive intervals.
- Calibration of `P(BFD > T)` at the selected thresholds, with event counts and uncertainty.
- Penetration log loss/Brier score plus reliability curves, positive/negative counts, and support by threat; in-sample low Brier score alone is not calibration proof.
- Parent/lot bootstrap uncertainty rather than treating every shot as independent.
- Input sensitivity for each requested property within matched material/design contexts, including unsupported/no-response flags.

The average error over synthetic zeros, training rows, and mixed products must not choose the final probability model. Benchmarks should include a matched-group empirical baseline and a simpler regularized model. Compare a hierarchical model when data permits; do not add arbitrary complexity simply to force a Gaussian curve.

### 7.4 Explicit readiness states

Compute readiness per requested output/property:

```text
blocked: missing units/spec/property response or invalid model bundle
exploratory: explicit assumptions or unsupported within-material response
validated_within_support: specified real-data tests/calibration passed
out_of_support: requested joint state/exposure lacks empirical support
```

Show the measured sample count, number of independent lots/rolls/specimens, and calibration event count. Define acceptance criteria before tuning; do not invent universal counts or numerical accuracy thresholds as proof of rare-event readiness. A 0.1% event cannot be empirically validated from five coupons. Support checks must use real matched data, not global min/max ranges inflated by anchors or unrelated materials.

## 8. API and user interface specification

### 8.1 API routes

Proposed routes under `/api/v1/ballistic/risk`:

```text
GET  /readiness?design_id=...&model_version=...&protocol_revision=...
POST /scenarios
GET  /scenarios/{scenario_id}
POST /scenarios/{scenario_id}/runs
GET  /runs/{run_id}
POST /runs/{run_id}/cancel
GET  /runs/{run_id}/export
```

Use an authenticated asynchronous worker/run record for expensive simulations; a short request validates, stores the immutable request, and returns a run ID. Reuse an existing job mechanism only after inspecting its runtime; do not launch untracked fire-and-forget work inside a web worker. Bound compute, chunk memory, and export size. Handle cancellation between chunks. A reproducible new run must not mutate the active prediction model or any material catalog entry.

Example request shape (illustrative identifiers must be replaced by real IDs):

```json
{
  "design_id": "resolved UUID",
  "model_version": "20260908_172840",
  "protocol_revision_id": "resolved UUID",
  "mode": "accepted_units",
  "population_size": 1000,
  "simulation_units": 100000,
  "seed": 20261013,
  "layer_counts_locked": true,
  "distribution_revision_ids": ["resolved UUID"],
  "dependency_revision_id": "resolved UUID",
  "bfd_screen": {"threshold_mm": 44.0, "operator": ">"},
  "near_worst_event": {
    "type": "percentile_bands",
    "conditions": [
      {"variable": "identified_roll_strength", "percentile_lte": 0.05},
      {"variable": "identified_roll_thickness", "percentile_lte": 0.05},
      {"variable": "shot_velocity", "percentile_gte": 0.95}
    ]
  }
}
```

`simulation_units` counts independently sampled virtual unit/exposure clusters for the Monte Carlo probability estimate, not raw shot rows. When the requested population shares lots, compute population summaries through the corresponding hierarchical batch mode, and label the number of independent replicate batches. Validate correlation/spec feasibility and model support before scheduling.

Minimum response fields:

```text
run/scenario/model/feature-contract/calibration identifiers and hashes
status/readiness per output; missing assumptions and support reasons
units simulated; valid/nonpenetrating/penetrating/unknown outcomes
distribution summaries and labeled units/conditioning/exposure
histogram bin edges/counts and empirical CDF/survival points
per-shot and per-protocol event estimates, with denominators
event count, MC interval, parameter/model uncertainty if estimated
expected count per 1000; population count interval if support permits
near-worst inequalities, event probability, conditional BFD summary
corner scenario and stress-envelope inputs/results/support limits
Gaussian overlay diagnostics or reason unavailable
runtime versions and reproducibility metadata
```

Do not omit failed draws and renormalize without showing why. If no-penetration BFD is conditional, display its conditional denominator. If penetration is unavailable, combined risk is also unavailable; a conditional BFD screen may still be displayed under its exact meaning.

### 8.2 Probability view

Add an Analytics probability tab, using the existing Plotly integration. Recommended flow:

1. Select fixed armor design/revision, model, protocol/threat, and exposure/population mode. Show material/count table locked for the run.
2. Review property distributions, spec limits, measured versus assumed source, sample/group counts, and shared-roll/lot assumptions. Allow explicit assumption edits in exploratory mode.
3. Set an engineering BFD screen and define a finite near-worst event. Prescribed dry/wet conditions are separate or protocol-defined; do not assign prevalence from the historical database.
4. Run, monitor progress, and inspect outcomes.

Main graphs:

- BFD histogram in millimeters, with nominal marker, threshold, and supported p50/p95/p99/p99.9 markers.
- Empirical survival curve `P(BFD > x)` so rare-event interpretation is visible. Clearly label conditional no-penetration BFD versus unit maximum.
- Optional dashed fitted Gaussian, with fit/tail discrepancy. Never force the histogram into a normal distribution or compute the headline probability from the overlay when simulation is the authoritative result.
- Sensitivity curves by supported property, with fixed count/order and the tested range.
- Separate penetration/unknown-outcome display; never put those events into a zero-BFD bin.

Cards: expected outcomes per 1,000, probability type/population, uncertainty type, near-worst frequency, and largest searched stress prediction. Keep “assumed distributions,” “unsupported strength response,” and missing joint-risk results beside the affected outputs. A disabled result should say what measurement/calibration is needed, rather than show an apparently safe zero.

Normality checks should include Q–Q behavior and empirical-versus-Gaussian survival near decision thresholds. A global goodness-of-fit p-value alone does not validate a rare tail; with large simulations it can reject trivial departures. A mixture across conditions, a maximum of several shots, and a penetration/BFD outcome mixture need not look Gaussian even if individual input variables are normal.

## 9. Numerical precision and rare-event reporting

Start exploratory runs at 20,000 virtual units; offer 100,000 or more after benchmarking. At `p=0.001`, 100,000 independent draws give about 100 events and Monte Carlo SE about 0.00010. Display uncertainty with the actual denominator; adapt draw counts to the requested precision.

Use Wilson or exact binomial MC intervals for independent Bernoulli unit-event samples. For zero events in `N` independent draws, the one-sided 95% upper bound is:

```text
1 - 0.05^(1/N)
```

At N=100,000 it is approximately 0.00002996, or 0.02996 per 1,000. Report “zero observed simulated events; MC upper bound ... under the specified model,” not zero real-world risk. This bound says nothing about unmodeled production changes or model bias.

For pooled dependent units within a simulated lot, use independent replicate-lot event samples, cluster-aware intervals, or a hierarchical calculation. Raw shot count is never an appropriate independent-trial denominator for whole-vest event probability.

If probabilities are too small for ordinary Monte Carlo, initially report resolution limits. A later importance-sampling implementation must preserve the joint target distribution and likelihood weights, report effective sample size, and be tested against cases with known answers. Do not generate only adverse corners and count them as ordinary population frequencies. Quasi-Monte Carlo estimates also need appropriate replicate-based uncertainty; ordinary binomial intervals are not automatically valid for dependent quasi-random draws.

## 10. Implementation sequence for the builder

Work in a branch against the actual current checkout. Preserve the existing production behavior until corrected contracts are explicitly adopted. Do not restore the entire SQL backup into production to develop this feature.

### Milestone A: evidence and data repair

1. Verify attachment hashes and current source revision; discover any applicable repository instructions.
2. Produce read-only inventory SQL/diagnostics for the counts/missingness in Section 2.
3. Create additive property/provenance tables; ingest reviewed coupon measurements and validated source units.
4. Backfill result enums with conservative mappings and unresolved states. Identify duplicate candidates and canonical ammunition mappings without dropping raw records.
5. Create a real-data snapshot manifest; preserve catalog versus as-tested values.

**Done when:** coupon SD semantics are correct, unknown outcomes remain unknown, raw report lineage is retained, and evaluation grouping IDs exist or unresolved grouping is explicitly flagged.

### Milestone B: bundle and feature consistency

1. Add immutable `ModelBundle` loading; verify artifacts, feature schema, dependency versions, and target transformation.
2. Extract a single versioned feature builder with explicit material overrides and fitted preprocessing. Preserve legacy behavior for NPOptimized-6 replay.
3. Correct grammage-based areal-density features in a new contract and train a new artifact when adopted.
4. Add parity and batch-invariance tests. Fix model-version concurrency and missing-feature defaults.

**Done when:** training/inference produce identical feature rows for the same specimen/shot, row predictions do not depend on unrelated batch members, and simultaneous versioned predictions cannot overwrite each other.

### Milestone C: useful exploratory analytics

1. Build scenario snapshots, bounded/correlated sampler, input-only simulation, event aggregator, and stress search.
2. Add async run tracking, seeds/chunk limits/cancellation, and immutable results.
3. Add histogram/survival/sensitivity views and measured-versus-assumed provenance.
4. Mark unsupported tensile/modulus responses and uncalibrated penetration risk unavailable.

**Done when:** deterministic simulated fixtures reproduce known answers, counts stay fixed, dependencies behave correctly, and no UI card calls exploratory outputs validated manufacturing risk.

### Milestone D: validated predictive distributions

1. Collect/link actual lot/roll properties to panels; sample several independent manufacture groups, spanning accepted-property variation rather than changing only nominal catalog materials.
2. Retrain with real grouped partitions and immutable feature/property manifests; compare simpler baselines and anchor influence.
3. Fit residual distributions on separate calibration groups; calibrate penetration only after adequate labeled data is available.
4. Validate threshold/tail/protocol behavior on untouched groups and enable only outputs meeting predefined acceptance criteria within support.

**Done when:** every displayed validation statement points to an independent manifest and measured evaluation; unsupported rare tails remain explicitly limited.

### Milestone E: production hardening

Benchmark worst requested exposure sizes, memory, cancellations, permissions, and simultaneous versions. Run shadow comparisons with actual held-out tests. Release behind a feature flag. Document rollback and immutable model/schema compatibility. No automatic retraining, catalog edits, or model activation should occur merely because someone runs a scenario.

## 11. Acceptance tests and failure cases

### 11.1 Source and feature correctness

| Test | Required result |
|---|---|
| CS-3041 report SD ingestion | 81.2 N/cm SD; about 5.095% CV; never 81.2% SD |
| Width normalization | 3,984 N / 2.5 cm = 1,593.6 N/cm; do not renormalize an already N/cm SD |
| Elongation spread | Absolute percentage points versus relative percent preserved |
| Stack units | 40 × 130 g/m² = 5.2 kg/m²; absent volumetric density does not zero it |
| Fixed construction | Counts, IDs, ordered layer groups identical before/after every draw |
| Same roll | Shared roll factor across all assigned layers, plus only defined local variation |
| Several rolls, same material | Different assignment IDs preserve different sampled roll states |
| Missing MPa strength | Returns unsupported response; no fabricated sensitivity or fake measured zero |
| Labels | Positive/negative/negated/`OK`/unknown cases tested; missing BFD cannot imply penetration |
| Batch invariance | A row's features and prediction unchanged when another row is added/reordered |
| Legacy/new contracts | Legacy bundle replay stable; corrected feature contract cannot load an incompatible artifact silently |
| Target transform | `expm1` used exactly once when flagged; no untransformed log-BFD output |
| Model concurrency | A/B simultaneous runs use their own bundle hashes and predictions; no shared-file writes |
| Historical catalog edit | As-tested features unchanged; new scenario revisions reflect approved new values |

### 11.2 Sampler and mathematical tests

1. Constant distributions produce deterministic inputs. Positive SD with zero-width bounds is rejected. Invalid/nonfinite parameters fail before a run.
2. Truncated samples remain within specification without artificial clipped boundary masses. Validate their empirical moments against SciPy's theoretical values.
3. Non-PSD, nonsymmetric, non-unit-diagonal, and incorrectly sized correlation matrices are rejected. Exact perfect-correlation/singular matrices are accepted without arbitrary noise.
4. For `Y = a + beta.T * X` with multivariate-normal X, verify mean, variance `beta.T * Sigma * beta`, and threshold probabilities against analytic answers with statistical tolerances.
5. Lowest-5% strength/thickness/highest-5% velocity event gives about `0.05³` when independent and `0.05²` when the first two share one factor.
6. A shared roll variance contribution to sum-of-layer strength does not vanish by multiplying independent-layer probabilities; compare common-factor versus independent-layer analytical variance.
7. Finite near-worst regions are distinguished from exact endpoints and from outcome exceedance events.
8. For `p=0.002`, 1,000 identical independent unit exposures give expected count 2, plus the correct binomial count range and at-least-one probability. Repeat with shared lots and verify the count distribution changes.
9. Zero-event intervals use independent unit/lot-replicate counts, not raw number of shots. Test p=0, p=1, and small-p numerics.
10. Joint one-shot example `p_pen=0.02`, `p_bfd_given_no_pen=0.01` yields combined risk `0.0298`, not `0.03` or `0.0002`.
11. For two perfectly dependent identical shot-event states, protocol union risk equals the single-shot risk; it must not become `1-(1-p)^2`.
12. Gaussian copula tests distinguish latent correlation from transformed physical correlation and accepted-marginal sampling from joint pre-QC acceptance conditioning.

### 11.3 Validation, support, and product tests

- Every real specimen/source duplicate group appears in only one partition. Preprocessor and distribution fitting never consume untouched evaluation groups.
- Anchors do not change real-data counts, calibration residuals, or support limits. Global extremes from anchors cannot make a new material/velocity combination look supported.
- The UI refuses calibrated manufacturing claims for assumed spread, missing strength response, insufficient penetration labels, or absent test rules.
- Conditional BFD output, stopped-but-high-BFD probability, penetration probability, and combined protocol probability have distinct definitions and denominators.
- Empty/unsupported results remain `null` with reasons. No exception path returns a zero-BFD point or zero-risk “PASS.”
- Parent/child records, front/back conditions, and conditioning specimen assignment are visible in the exposure plan. Per-shot statistics are never mislabeled per-vest.
- Exact seed, snapshot, bundle, and runtime reproduce results in the supported runtime; changes to unrelated active models do not affect a queued run.
- Cancellation leaves a canceled status and documented partial draw count; incomplete runs are not shown as final estimates.
- Scenario edits change hash/revision and invalidate result caches. Exported metadata matches graph/card definitions.
- Probability displays react correctly when threshold/operator changes and include the relevant MC/parameter/population uncertainty label.
- Stress-search results respect constraints and report maximum found; discontinuous/nonmonotone fixtures demonstrate why assumed corners are insufficient.

## 12. Verified mathematical reference kernel

The following dependency-light reference is **not the production feature** and produces no DeltaDash risk estimate. It verifies the sampler/count mathematics. It was run successfully during this review with 500,000 synthetic samples. The builder can copy it into a numerical test fixture and extend it with the production feature/validation tests above.

```python
import math
import numpy as np
from scipy.stats import norm, truncnorm, binom

def truncated_normal_ppf(u, mu, sigma, lo, hi):
    if not (math.isfinite(mu) and math.isfinite(lo) and math.isfinite(hi)):
        raise ValueError('nonfinite parameters')
    if lo > hi or sigma < 0 or not math.isfinite(sigma):
        raise ValueError('invalid bounds or sigma')
    u = np.asarray(u, dtype=float)
    if sigma == 0:
        if not lo <= mu <= hi:
            raise ValueError('point mass outside specification')
        return np.full_like(u, mu)
    if lo == hi:
        raise ValueError('positive sigma with zero-width bounds')
    if np.any(~np.isfinite(u)) or np.any((u <= 0) | (u >= 1)):
        raise ValueError('uniform inputs must be strictly inside (0,1)')
    a, b = (lo - mu) / sigma, (hi - mu) / sigma
    return truncnorm.ppf(u, a, b, loc=mu, scale=sigma)

def validate_correlation(r):
    r = np.asarray(r, dtype=float)
    if r.ndim != 2 or r.shape[0] != r.shape[1] or not np.isfinite(r).all():
        raise ValueError('invalid correlation dimensions')
    if not np.allclose(r, r.T) or not np.allclose(np.diag(r), 1):
        raise ValueError('correlation must be symmetric with unit diagonal')
    values, vectors = np.linalg.eigh(r)
    if values.min() < -1e-10:
        raise ValueError('correlation is not positive semidefinite')
    return vectors @ np.diag(np.sqrt(np.maximum(values, 0)))

def joint_uniforms(rng, n, correlation):
    factor = validate_correlation(correlation)
    z = rng.standard_normal((n, factor.shape[0])) @ factor.T
    return np.clip(norm.cdf(z), np.nextafter(0.0, 1.0),
                   np.nextafter(1.0, 0.0))

def zero_event_upper_bound(n, alpha=0.05):
    if n < 1 or not 0 < alpha < 1:
        raise ValueError('invalid n or alpha')
    return -math.expm1(math.log(alpha) / n)

def iid_population_summary(p, population=1000):
    if not 0 <= p <= 1 or population < 1:
        raise ValueError('invalid population or probability')
    at_least_one = 1.0 if p == 1 else -math.expm1(
        population * math.log1p(-p))
    lo, hi = binom.ppf([0.025, 0.975], population, p)
    return {'expected': population * p,
            'probability_at_least_one': at_least_one,
            'count_prediction_interval_95': [int(lo), int(hi)]}

def reference_checks():
    rng = np.random.default_rng(20261013)
    n = 500_000
    r = np.array([[1, .4, .2], [.4, 1, -.1], [.2, -.1, 1.]])
    z = rng.standard_normal((n, 3)) @ validate_correlation(r).T
    beta = np.array([2., 3., -1.])
    y = 30. + z @ beta
    variance = float(beta @ r @ beta)
    p = float(norm.sf((40.-30.)/math.sqrt(variance)))
    sampled = float(np.mean(y > 40.))
    assert abs(y.mean()-30.) < 5*math.sqrt(variance/n)
    assert abs(y.var()-variance) < .2
    assert abs(sampled-p) < 5*math.sqrt(p*(1-p)/n)
    u = joint_uniforms(rng, 10000, r)
    x = truncated_normal_ppf(u[:,0], 100., 1., 97.5, 102.5)
    assert ((x > 97.5) & (x < 102.5)).all()
    shared = joint_uniforms(rng, 10000, np.ones((2,2)))
    assert np.allclose(shared[:,0], shared[:,1])
    assert abs((.02+(1-.02)*.01)-.0298) < 1e-12
    assert iid_population_summary(0)['expected'] == 0
    assert iid_population_summary(1)['probability_at_least_one'] == 1
    assert 0 < zero_event_upper_bound(100000) < .00003
    return {'analytic_variance': variance,
            'sampled_variance': float(y.var()),
            'analytic_tail': p, 'sampled_tail': sampled,
            'checks': 'PASS'}

if __name__ == '__main__':
    print(reference_checks())
```

The initial reference verification produced analytic variance 18.6 versus sampled 18.6062, analytic tail probability 0.0102058 versus sampled 0.010174, and the expected independent/shared-factor near-corner behavior. These validate the mathematics on synthetic fixtures; they do not validate the supplied model's manufacturing probabilities.

## 13. Targeted measurements needed next

The most useful next work is a linked dataset, rather than another hyperparameter optimization on catalog values:

1. Identify which strength metric carries the −2.5% requirement: longitudinal/transverse breaking force per width, MPa tensile stress, or another specified property. Attach its reference value and approved bounds.
2. Obtain thickness and grammage specs and raw accepted-roll QC measurements, including multiple independent lots/rolls and sampling positions. Preserve paired-property information where measurements actually share a coupon or location.
3. Record lot/roll assignments for the layers in each tested panel and preserve unique physical specimen/vest IDs. Recover available shipment/production records for older tests where feasible.
4. Link actual measured properties and QC selection to matched ballistic panels under a fixed threat/exposure. Include useful variation within specification so a model can distinguish same-material property effects from material identity.
5. Collect explicit penetration/nonpenetration labels, valid-shot status, measured velocities, conditioning, and backing/test-session measurements. Do not infer those labels from blank fields.
6. Reserve new manufacture/test groups for untouched validation and threshold calibration before inspecting their model errors.

Proceed with exploratory mechanics while collecting these data. The builder must not fabricate missing distributions, assume independence across layers, or claim that the current small fitted error fills these evidence gaps.

## 14. Technical references

Use the installed-version API rather than copying newest examples blindly:

- scikit-learn GroupKFold, 1.3 documentation: https://scikit-learn.org/1.3/modules/generated/sklearn.model_selection.GroupKFold.html
- scikit-learn probability calibration: https://scikit-learn.org/stable/modules/calibration.html
- scikit-learn common pitfalls/data leakage: https://scikit-learn.org/stable/common_pitfalls.html
- SciPy truncated-normal distribution, 1.11.3: https://docs.scipy.org/doc/scipy-1.11.3/reference/generated/scipy.stats.truncnorm.html

Repository/attachment findings above come from the actual source and supplied files. The references support the general sampling/validation methods; they do not establish DeltaDash-specific probabilities or compliance decisions.
