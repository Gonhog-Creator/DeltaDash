"""backfill risk analytics data (outcomes, normalization, ammo links, duplicates, measurements)

Revision ID: 20261013_1330
Revises: 20261013_1300
Create Date: 2026-10-13 13:30:00.000000

Data backfills, all writing only to the additive columns from a1b2c3d4e5f6:

1. shot_data.outcome:
   - explicit negated labels checked BEFORE positive substrings, so
     "no perforado"/"sin perforación" never match 'perfor'.
   - measurable BFD (trauma_mm > 0) implies 'stopped' (domain rule: clay
     deformation only exists on non-penetrating rounds); source='bfd_implied'.
   - everything else -> 'unknown'. Unknown is never treated as stopped.

2. normalized_side / normalized_conditioning / normalized_protection_level:
   casing and '<protocol> - <level>' prefixes normalized; raw columns untouched.

3. shot_data.ammunition_id: exact name match first, then unique caliber match.
   Multi-row calibers (e.g. two '5.56x45mm M855' entries) -> 'ambiguous',
   no guessing.

4. duplicate_group_id for rows sharing (test_date, vest_id, vest_number, side,
   conditioning, shot_number, caliber, velocity_m_s, trauma_mm). Groups are
   marked for review only; nothing is deleted or superseded automatically.

5. materials.stretch_test_length: force-bearing materials missing the flag
   are set to '2.5cm' (supplier standard for these reports).

6. material_property_measurements: register report-derived summary statistics
   for the 15 materials with directional breaking-force data. force_*_newtons /
   specimen width -> breaking_force_n_per_cm; the *_error_percent columns hold
   the reports' absolute SD in N/cm (uncertainty_kind='absolute'), NOT percent.
   Elongation error values are absolute percentage points.
"""
from alembic import op
import sqlalchemy as sa


revision = '20261013_1330'
down_revision = '20261013_1300'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ----------------------------------------------------------------------
    # 1. shot outcomes. Negated labels first so they cannot match 'perfor'.
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        UPDATE shot_data SET outcome = 'stopped', outcome_source = 'explicit_label'
        WHERE outcome IS NULL AND trauma_qualitative IS NOT NULL AND (
            lower(trauma_qualitative) ~ 'no perfor'
            OR lower(trauma_qualitative) ~ 'sin perfor'
            OR lower(trauma_qualitative) ~ 'no penetr'
            OR lower(trauma_qualitative) ~ 'no punct'
            OR lower(trauma_qualitative) ~ 'no paso'
            OR btrim(lower(trauma_qualitative)) IN
               ('ok', 'no perforado', 'no perforada', 'stopped', 'no penetration')
        )
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET outcome = 'complete_penetration', outcome_source = 'explicit_label'
        WHERE outcome IS NULL AND trauma_qualitative IS NOT NULL AND (
            lower(trauma_qualitative) ~ 'perfor'
            OR lower(trauma_qualitative) ~ 'penetr'
            OR lower(trauma_qualitative) ~ 'punct'
        )
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET outcome = 'stopped', outcome_source = 'bfd_implied'
        WHERE outcome IS NULL AND trauma_mm IS NOT NULL AND trauma_mm > 0
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET outcome = 'unknown', outcome_source = 'unresolved'
        WHERE outcome IS NULL
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET shot_validity = 'unassessed' WHERE shot_validity IS NULL
    """))

    # ----------------------------------------------------------------------
    # 2. normalized fields
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        UPDATE shot_data SET normalized_side = CASE lower(btrim(side))
            WHEN 'frente' THEN 'front'
            WHEN 'espalda' THEN 'back'
            ELSE lower(btrim(side))
        END
        WHERE side IS NOT NULL
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET normalized_conditioning = lower(btrim(conditioning))
        WHERE conditioning IS NOT NULL
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET normalized_protection_level =
            upper(regexp_replace(btrim(protection_level), '^.*-\\s*', ''))
        WHERE protection_level IS NOT NULL
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET normalized_protection_level = 'RB4'
        WHERE normalized_protection_level = 'ARG_RB4'
    """))

    # ----------------------------------------------------------------------
    # 3. canonical ammunition link
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        UPDATE shot_data sd SET ammunition_id = a.id, ammunition_match_status = 'exact_name'
        FROM ammunition a
        WHERE sd.ammunition_id IS NULL AND sd.caliber IS NOT NULL
          AND lower(btrim(sd.caliber)) = lower(btrim(a.name))
    """))
    conn.execute(sa.text("""
        UPDATE shot_data sd SET ammunition_id = a.id, ammunition_match_status = 'caliber'
        FROM ammunition a
        WHERE sd.ammunition_id IS NULL AND sd.caliber IS NOT NULL
          AND lower(btrim(sd.caliber)) = lower(btrim(a.caliber))
          AND (SELECT count(*) FROM ammunition a2
               WHERE lower(btrim(a2.caliber)) = lower(btrim(sd.caliber))) = 1
    """))
    conn.execute(sa.text("""
        UPDATE shot_data sd SET ammunition_match_status = 'ambiguous'
        WHERE sd.ammunition_id IS NULL AND sd.caliber IS NOT NULL
          AND (SELECT count(*) FROM ammunition a2
               WHERE lower(btrim(a2.caliber)) = lower(btrim(sd.caliber))) > 1
    """))
    conn.execute(sa.text("""
        UPDATE shot_data sd SET ammunition_match_status = 'unmatched'
        WHERE sd.ammunition_id IS NULL AND sd.ammunition_match_status IS NULL
    """))

    # ----------------------------------------------------------------------
    # 4. duplicate candidate groups (review flag only, nothing deleted)
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        WITH g AS (
            SELECT ts.test_date, ts.vest_id, sd.vest_number, sd.side,
                   sd.conditioning, sd.shot_number, sd.caliber,
                   sd.velocity_m_s, sd.trauma_mm
            FROM shot_data sd
            JOIN test_sessions ts ON ts.id = sd.test_session_id
            GROUP BY 1,2,3,4,5,6,7,8,9
            HAVING count(*) > 1
        ),
        ug AS (SELECT *, gen_random_uuid() AS dgid FROM g)
        UPDATE shot_data sd SET duplicate_group_id = ug.dgid
        FROM ug, test_sessions ts
        WHERE sd.test_session_id = ts.id
          AND ts.test_date    IS NOT DISTINCT FROM ug.test_date
          AND ts.vest_id      IS NOT DISTINCT FROM ug.vest_id
          AND sd.vest_number  IS NOT DISTINCT FROM ug.vest_number
          AND sd.side         IS NOT DISTINCT FROM ug.side
          AND sd.conditioning IS NOT DISTINCT FROM ug.conditioning
          AND sd.shot_number  IS NOT DISTINCT FROM ug.shot_number
          AND sd.caliber      IS NOT DISTINCT FROM ug.caliber
          AND sd.velocity_m_s IS NOT DISTINCT FROM ug.velocity_m_s
          AND sd.trauma_mm    IS NOT DISTINCT FROM ug.trauma_mm
    """))

    # ----------------------------------------------------------------------
    # 5. stretch-test length default for force-bearing materials (2.5cm)
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        UPDATE materials SET stretch_test_length = '2.5cm'
        WHERE stretch_test_length IS NULL
          AND (force_longitudinal_newtons IS NOT NULL
               OR force_transverse_newtons IS NOT NULL)
    """))

    # ----------------------------------------------------------------------
    # 6. report-derived summary measurements (mean + absolute SD)
    #    stretch_test_length '2.5cm'/'2,5cm' -> width 25mm; '5cm' -> 50mm
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        INSERT INTO material_property_measurements
            (id, material_id, property_key, direction, value, unit,
             specimen_width_mm, measurement_uncertainty, uncertainty_kind,
             is_raw_measurement, review_status, method)
        SELECT gen_random_uuid(), m.id, 'breaking_force_n_per_cm', 'longitudinal',
               m.force_longitudinal_newtons /
                   CASE WHEN m.stretch_test_length ~ '2[.,]5' THEN 2.5 ELSE 5.0 END,
               'N/cm',
               CASE WHEN m.stretch_test_length ~ '2[.,]5' THEN 25.0 ELSE 50.0 END,
               m.force_longitudinal_error_percent,
               'absolute',
               false, 'unreviewed', 'report_derived'
        FROM materials m
        WHERE m.force_longitudinal_newtons IS NOT NULL
    """))
    conn.execute(sa.text("""
        INSERT INTO material_property_measurements
            (id, material_id, property_key, direction, value, unit,
             specimen_width_mm, measurement_uncertainty, uncertainty_kind,
             is_raw_measurement, review_status, method)
        SELECT gen_random_uuid(), m.id, 'breaking_force_n_per_cm', 'transverse',
               m.force_transverse_newtons /
                   CASE WHEN m.stretch_test_length ~ '2[.,]5' THEN 2.5 ELSE 5.0 END,
               'N/cm',
               CASE WHEN m.stretch_test_length ~ '2[.,]5' THEN 25.0 ELSE 50.0 END,
               m.force_transverse_error_percent,
               'absolute',
               false, 'unreviewed', 'report_derived'
        FROM materials m
        WHERE m.force_transverse_newtons IS NOT NULL
    """))
    conn.execute(sa.text("""
        INSERT INTO material_property_measurements
            (id, material_id, property_key, direction, value, unit,
             measurement_uncertainty, uncertainty_kind,
             is_raw_measurement, review_status, method)
        SELECT gen_random_uuid(), m.id, 'elongation_percent', 'longitudinal',
               m.elongation_longitudinal_percent, 'percent',
               m.elongation_longitudinal_error_percent, 'percentage_points',
               false, 'unreviewed', 'report_derived'
        FROM materials m
        WHERE m.elongation_longitudinal_percent IS NOT NULL
    """))
    conn.execute(sa.text("""
        INSERT INTO material_property_measurements
            (id, material_id, property_key, direction, value, unit,
             measurement_uncertainty, uncertainty_kind,
             is_raw_measurement, review_status, method)
        SELECT gen_random_uuid(), m.id, 'elongation_percent', 'transverse',
               m.elongation_transverse_percent, 'percent',
               m.elongation_transverse_error_percent, 'percentage_points',
               false, 'unreviewed', 'report_derived'
        FROM materials m
        WHERE m.elongation_transverse_percent IS NOT NULL
    """))

    # ----------------------------------------------------------------------
    # 7. initial evaluation manifest: all real shot_data with grouping keys
    # ----------------------------------------------------------------------
    conn.execute(sa.text("""
        INSERT INTO evaluation_manifests
            (id, name, description, shot_entries, content_hash, created_by)
        SELECT gen_random_uuid(),
               'shot_data_snapshot_20261013',
               'All shot_data rows with grouping keys for leakage-safe evaluation splits',
               COALESCE(entries.entries, '[]'::jsonb),
               h.h,
               'migration:20261013_1330'
        FROM (SELECT md5(string_agg(id::text, ',' ORDER BY id)) AS h
              FROM shot_data) h,
             (SELECT jsonb_agg(jsonb_build_object(
                         'shot_id', sd.id,
                         'test_session_id', sd.test_session_id,
                         'parent_test_group_id', ts.parent_test_group_id,
                         'vest_id', ts.vest_id,
                         'duplicate_group_id', sd.duplicate_group_id,
                         'outcome', sd.outcome,
                         'is_synthetic', false)
                      ORDER BY sd.id) AS entries
              FROM shot_data sd
              LEFT JOIN test_sessions ts ON ts.id = sd.test_session_id) entries
    """))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM evaluation_manifests WHERE created_by = 'migration:20261013_1330'"
    ))
    conn.execute(sa.text(
        "DELETE FROM material_property_measurements WHERE method = 'report_derived'"
    ))
    conn.execute(sa.text("""
        UPDATE materials SET stretch_test_length = NULL
        WHERE stretch_test_length = '2.5cm'
          AND name IN ('KL 230', 'UD 234', 'UD 245', 'Vitelmat Antitrauma Pad (4mm)')
    """))
    conn.execute(sa.text("""
        UPDATE shot_data SET outcome = NULL, outcome_source = NULL,
               shot_validity = NULL, validity_reason = NULL,
               ammunition_id = NULL, ammunition_match_status = NULL,
               normalized_side = NULL, normalized_conditioning = NULL,
               normalized_protection_level = NULL, duplicate_group_id = NULL
    """))
