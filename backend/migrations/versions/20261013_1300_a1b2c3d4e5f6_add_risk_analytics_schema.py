"""add risk analytics schema (material provenance, specimens, protocols, scenarios, runs)

Revision ID: 20261013_1300
Revises: e7f8a9b0c1d2
Create Date: 2026-10-13 13:00:00.000000

Additive-only migration for the BFD probability analytics feature:
- material_lots / material_rolls / material_property_measurements /
  material_property_specs / material_property_distributions
- panel_layer_material_assignments / as_tested_property_snapshots
- protocol_revisions
- risk_scenarios / risk_simulation_runs / model_validation_runs
- evaluation_manifests
- armor_panels: specimen identity columns (vest link, serial, unit, lot)
- shot_data: enrichment columns (outcome, validity, canonical ammo link,
  specimen link, normalized fields, duplicate tracking)

No existing columns or rows are modified.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '20261013_1300'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- material provenance hierarchy --------------------------------------
    op.create_table(
        'material_lots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('supplier_lot_code', sa.String(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_documents.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_material_lots_material_id', 'material_lots', ['material_id'])

    op.create_table(
        'material_rolls',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('material_lot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_lots.id'), nullable=False),
        sa.Column('supplier_roll_code', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_material_rolls_material_lot_id', 'material_rolls', ['material_lot_id'])

    op.create_table(
        'material_property_measurements',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('lot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_lots.id'), nullable=True),
        sa.Column('roll_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_rolls.id'), nullable=True),
        sa.Column('coupon_id', sa.String(), nullable=True),
        sa.Column('specimen_position', sa.String(), nullable=True),
        sa.Column('property_key', sa.String(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False, server_default='none'),
        sa.Column('value', sa.Numeric(14, 4), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('measured_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('method', sa.String(), nullable=True),
        sa.Column('specimen_width_mm', sa.Numeric(10, 3), nullable=True),
        sa.Column('gauge_length_mm', sa.Numeric(10, 3), nullable=True),
        sa.Column('test_temperature_c', sa.Numeric(5, 2), nullable=True),
        sa.Column('measurement_uncertainty', sa.Numeric(14, 4), nullable=True),
        sa.Column('uncertainty_kind', sa.String(), nullable=True),
        sa.Column('coverage_factor', sa.Numeric(6, 3), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_documents.id'), nullable=True),
        sa.Column('source_page', sa.String(), nullable=True),
        sa.Column('source_table', sa.String(), nullable=True),
        sa.Column('source_row', sa.String(), nullable=True),
        sa.Column('is_raw_measurement', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('review_status', sa.String(), nullable=False, server_default='unreviewed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_material_property_measurements_material_id', 'material_property_measurements', ['material_id'])
    op.create_index('ix_material_property_measurements_lot_id', 'material_property_measurements', ['lot_id'])
    op.create_index('ix_material_property_measurements_roll_id', 'material_property_measurements', ['roll_id'])
    op.create_index('ix_material_property_measurements_property_key', 'material_property_measurements', ['property_key'])

    op.create_table(
        'material_property_specs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('property_key', sa.String(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False, server_default='none'),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('reference_value', sa.Numeric(14, 4), nullable=True),
        sa.Column('lower_limit', sa.Numeric(14, 4), nullable=True),
        sa.Column('upper_limit', sa.Numeric(14, 4), nullable=True),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_document_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_documents.id'), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_material_property_specs_material_id', 'material_property_specs', ['material_id'])

    op.create_table(
        'material_property_distributions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('spec_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_property_specs.id'), nullable=True),
        sa.Column('property_key', sa.String(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False, server_default='none'),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('population_scope', sa.String(), nullable=False, server_default='accepted_units'),
        sa.Column('family', sa.String(), nullable=False),
        sa.Column('parameters_json', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('latent_correlation_group', sa.String(), nullable=True),
        sa.Column('provenance', sa.String(), nullable=False, server_default='assumed'),
        sa.Column('measurement_ids', postgresql.JSONB(), nullable=True),
        sa.Column('fit_diagnostics_json', postgresql.JSONB(), nullable=True),
        sa.Column('sample_count', sa.Integer(), nullable=True),
        sa.Column('group_count', sa.Integer(), nullable=True),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('approved_by', sa.String(), nullable=True),
        sa.Column('review_status', sa.String(), nullable=False, server_default='unreviewed'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_material_property_distributions_material_id', 'material_property_distributions', ['material_id'])

    # --- tested specimen linkage --------------------------------------------
    op.add_column('armor_panels', sa.Column('vest_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vests.id'), nullable=True))
    op.add_column('armor_panels', sa.Column('serial_number', sa.String(), nullable=True))
    op.add_column('armor_panels', sa.Column('manufactured_unit_id', sa.String(), nullable=True))
    op.add_column('armor_panels', sa.Column('production_lot_code', sa.String(), nullable=True))
    op.create_index('ix_armor_panels_serial_number', 'armor_panels', ['serial_number'])
    op.create_index('ix_armor_panels_manufactured_unit_id', 'armor_panels', ['manufactured_unit_id'])

    op.create_table(
        'panel_layer_material_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('panel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('armor_panels.id'), nullable=False),
        sa.Column('layer_start', sa.Integer(), nullable=False),
        sa.Column('layer_end', sa.Integer(), nullable=False),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('material_lot_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_lots.id'), nullable=True),
        sa.Column('roll_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('material_rolls.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_panel_layer_material_assignments_panel_id', 'panel_layer_material_assignments', ['panel_id'])

    op.create_table(
        'as_tested_property_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('panel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('armor_panels.id'), nullable=False),
        sa.Column('material_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('materials.id'), nullable=False),
        sa.Column('property_key', sa.String(), nullable=False),
        sa.Column('direction', sa.String(), nullable=False, server_default='none'),
        sa.Column('value', sa.Numeric(14, 4), nullable=False),
        sa.Column('unit', sa.String(), nullable=False),
        sa.Column('measurement_ids', postgresql.JSONB(), nullable=True),
        sa.Column('aggregation_method', sa.String(), nullable=True),
        sa.Column('source_quality', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_as_tested_property_snapshots_panel_id', 'as_tested_property_snapshots', ['panel_id'])

    # --- protocol interpretation ---------------------------------------------
    op.create_table(
        'protocol_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('protocol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('protocols.id'), nullable=False),
        sa.Column('level', sa.String(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('rule_source', sa.String(), nullable=True),
        sa.Column('review_status', sa.String(), nullable=False, server_default='unreviewed'),
        sa.Column('shots_json', postgresql.JSONB(), nullable=True),
        sa.Column('outcome_rule_json', postgresql.JSONB(), nullable=True),
        sa.Column('content_hash', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_protocol_revisions_protocol_id', 'protocol_revisions', ['protocol_id'])

    # --- scenarios, runs, validation, manifests -------------------------------
    op.create_table(
        'risk_scenarios',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('design_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vests.id'), nullable=False),
        sa.Column('design_revision', sa.Integer(), nullable=True),
        sa.Column('protocol_revision_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('protocol_revisions.id'), nullable=True),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('feature_contract_version', sa.String(), nullable=True),
        sa.Column('layer_snapshot_json', postgresql.JSONB(), nullable=False),
        sa.Column('distribution_snapshot_json', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('dependency_snapshot_json', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('outcome_rule_json', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('near_worst_event_json', postgresql.JSONB(), nullable=True),
        sa.Column('population_mode', sa.String(), nullable=False, server_default='accepted_units'),
        sa.Column('population_size', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('layer_counts_locked', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        'risk_simulation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('scenario_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('risk_scenarios.id'), nullable=False),
        sa.Column('scenario_hash', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='queued'),
        sa.Column('seed', sa.BigInteger(), nullable=False),
        sa.Column('requested_draws', sa.Integer(), nullable=False),
        sa.Column('completed_independent_draws', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('model_bundle_hash', sa.String(), nullable=True),
        sa.Column('data_snapshot_hash', sa.String(), nullable=True),
        sa.Column('calibration_version', sa.String(), nullable=True),
        sa.Column('feature_contract_version', sa.String(), nullable=True),
        sa.Column('runtime_versions_json', postgresql.JSONB(), nullable=True),
        sa.Column('assumptions_json', postgresql.JSONB(), nullable=True),
        sa.Column('readiness_json', postgresql.JSONB(), nullable=True),
        sa.Column('result_json', postgresql.JSONB(), nullable=True),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_risk_simulation_runs_scenario_id', 'risk_simulation_runs', ['scenario_id'])

    op.create_table(
        'model_validation_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('model_version', sa.String(), nullable=False),
        sa.Column('dataset_hash', sa.String(), nullable=False),
        sa.Column('split_manifest_hash', sa.String(), nullable=False),
        sa.Column('group_definition', sa.String(), nullable=False),
        sa.Column('train_ids', postgresql.JSONB(), nullable=True),
        sa.Column('tuning_ids', postgresql.JSONB(), nullable=True),
        sa.Column('calibration_ids', postgresql.JSONB(), nullable=True),
        sa.Column('test_ids', postgresql.JSONB(), nullable=True),
        sa.Column('real_metrics_json', postgresql.JSONB(), nullable=True),
        sa.Column('synthetic_diagnostics_json', postgresql.JSONB(), nullable=True),
        sa.Column('coverage_json', postgresql.JSONB(), nullable=True),
        sa.Column('support_summary_json', postgresql.JSONB(), nullable=True),
        sa.Column('residual_artifact_path', sa.String(), nullable=True),
        sa.Column('classifier_calibration_path', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_model_validation_runs_model_version', 'model_validation_runs', ['model_version'])

    op.create_table(
        'evaluation_manifests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('shot_entries', postgresql.JSONB(), nullable=False),
        sa.Column('content_hash', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- shot_data enrichment columns (raw import columns untouched) ----------
    op.add_column('shot_data', sa.Column('outcome', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('outcome_source', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('shot_validity', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('validity_reason', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('ammunition_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shot_data', sa.Column('ammunition_match_status', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('specimen_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shot_data', sa.Column('normalized_side', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('normalized_conditioning', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('normalized_protection_level', sa.String(), nullable=True))
    op.add_column('shot_data', sa.Column('duplicate_group_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('shot_data', sa.Column('is_superseded', sa.String(), nullable=True))
    op.create_index('ix_shot_data_duplicate_group_id', 'shot_data', ['duplicate_group_id'])
    op.create_foreign_key('fk_shot_data_ammunition_id', 'shot_data', 'ammunition', ['ammunition_id'], ['id'])
    op.create_foreign_key('fk_shot_data_specimen_id', 'shot_data', 'armor_panels', ['specimen_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_shot_data_specimen_id', 'shot_data', type_='foreignkey')
    op.drop_constraint('fk_shot_data_ammunition_id', 'shot_data', type_='foreignkey')
    op.drop_index('ix_shot_data_duplicate_group_id', table_name='shot_data')
    for col in ('outcome', 'outcome_source', 'shot_validity', 'validity_reason',
                'ammunition_id', 'ammunition_match_status', 'specimen_id',
                'normalized_side', 'normalized_conditioning',
                'normalized_protection_level', 'duplicate_group_id', 'is_superseded'):
        op.drop_column('shot_data', col)

    op.drop_table('evaluation_manifests')
    op.drop_index('ix_model_validation_runs_model_version', table_name='model_validation_runs')
    op.drop_table('model_validation_runs')
    op.drop_index('ix_risk_simulation_runs_scenario_id', table_name='risk_simulation_runs')
    op.drop_table('risk_simulation_runs')
    op.drop_table('risk_scenarios')
    op.drop_index('ix_protocol_revisions_protocol_id', table_name='protocol_revisions')
    op.drop_table('protocol_revisions')
    op.drop_index('ix_as_tested_property_snapshots_panel_id', table_name='as_tested_property_snapshots')
    op.drop_table('as_tested_property_snapshots')
    op.drop_index('ix_panel_layer_material_assignments_panel_id', table_name='panel_layer_material_assignments')
    op.drop_table('panel_layer_material_assignments')
    op.drop_index('ix_armor_panels_manufactured_unit_id', table_name='armor_panels')
    op.drop_index('ix_armor_panels_serial_number', table_name='armor_panels')
    for col in ('vest_id', 'serial_number', 'manufactured_unit_id', 'production_lot_code'):
        op.drop_column('armor_panels', col)
    op.drop_index('ix_material_property_distributions_material_id', table_name='material_property_distributions')
    op.drop_table('material_property_distributions')
    op.drop_index('ix_material_property_specs_material_id', table_name='material_property_specs')
    op.drop_table('material_property_specs')
    op.drop_index('ix_material_property_measurements_property_key', table_name='material_property_measurements')
    op.drop_index('ix_material_property_measurements_roll_id', table_name='material_property_measurements')
    op.drop_index('ix_material_property_measurements_lot_id', table_name='material_property_measurements')
    op.drop_index('ix_material_property_measurements_material_id', table_name='material_property_measurements')
    op.drop_table('material_property_measurements')
    op.drop_index('ix_material_rolls_material_lot_id', table_name='material_rolls')
    op.drop_table('material_rolls')
    op.drop_index('ix_material_lots_material_id', table_name='material_lots')
    op.drop_table('material_lots')
