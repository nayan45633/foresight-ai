"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-19 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), unique=True, nullable=False),
        sa.Column('username', sa.String(length=100), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='analyst'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_role', 'users', ['role'])

    # 2. Auth Sessions table
    op.create_table(
        'auth_sessions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('refresh_token_hash', sa.String(length=255), unique=True, nullable=False),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_revoked', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_session_user_id', 'auth_sessions', ['user_id'])
    op.create_index('idx_session_expires', 'auth_sessions', ['expires_at'])
    op.create_index('idx_session_user_active', 'auth_sessions', ['user_id', 'is_revoked', 'expires_at'])

    # 3. Telemetry Jobs table
    op.create_table(
        'telemetry_jobs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='QUEUED'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('record_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_flow_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('anomaly_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_state', sa.String(length=1000), nullable=True),
        sa.Column('quality_summary', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_job_status_created', 'telemetry_jobs', ['status', 'created_at'])

    # 4. Telemetry Sources table
    op.create_table(
        'telemetry_sources',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('name', sa.String(length=100), unique=True, nullable=False),
        sa.Column('source_type', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 5. Network Flows table
    op.create_table(
        'network_flows',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_ip', sa.String(length=45), nullable=False),
        sa.Column('destination_ip', sa.String(length=45), nullable=False),
        sa.Column('source_port', sa.Integer(), nullable=False),
        sa.Column('destination_port', sa.Integer(), nullable=False),
        sa.Column('protocol', sa.String(length=16), nullable=False),
        sa.Column('flow_duration_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('packet_count', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('byte_count', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('packet_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('byte_rate', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tcp_flags', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('connection_state', sa.String(length=32), nullable=False, server_default='UNKNOWN'),
        sa.Column('direction', sa.String(length=16), nullable=False, server_default='ingress'),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_flows_time_src_dst', 'network_flows', ['timestamp', 'source_ip', 'destination_ip'])
    op.create_index('idx_flows_dst_port_proto', 'network_flows', ['destination_port', 'protocol'])

    # 6. Telemetry Batches table
    op.create_table(
        'telemetry_batches',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('source_identifier', sa.String(length=100), nullable=False),
        sa.Column('record_count', sa.Integer(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='SUCCESS'),
        sa.Column('error_summary', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 7. Forecast Windows table
    op.create_table(
        'forecast_windows',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_duration_seconds', sa.Integer(), nullable=False),
        sa.Column('target_entity', sa.String(length=100), nullable=False, server_default='NETWORK_GLOBAL'),
        sa.Column('flow_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('aggregated_features', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_windows_time', 'forecast_windows', ['window_start', 'window_end'])

    # 8. Attack Forecasts table
    op.create_table(
        'attack_forecasts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('window_id', sa.String(length=64), nullable=True),
        sa.Column('forecast_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('target_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('horizon_minutes', sa.Integer(), nullable=False),
        sa.Column('predicted_threat', sa.String(length=100), nullable=False),
        sa.Column('probability', sa.Float(), nullable=False),
        sa.Column('raw_probability', sa.Float(), nullable=True),
        sa.Column('decision_threshold', sa.Float(), nullable=False, server_default='0.50'),
        sa.Column('binary_alert_decision', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('anomaly_score', sa.Float(), nullable=False),
        sa.Column('risk_level', sa.String(length=32), nullable=False),
        sa.Column('conformal_prediction_set', sa.JSON(), nullable=False),
        sa.Column('uncertainty_metrics', sa.JSON(), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('calibration_version', sa.String(length=50), nullable=False, server_default='v1.0.0-isotonic'),
        sa.Column('feature_contributions', sa.JSON(), nullable=False),
        sa.Column('target_asset', sa.String(length=100), nullable=False, server_default='GLOBAL_PERIMETER'),
        sa.Column('actual_outcome', sa.String(length=100), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_forecast_time_threat', 'attack_forecasts', ['forecast_timestamp', 'predicted_threat'])
    op.create_index('idx_forecast_risk_horizon', 'attack_forecasts', ['risk_level', 'horizon_minutes'])
    op.create_index('idx_forecast_alert_time', 'attack_forecasts', ['binary_alert_decision', 'forecast_timestamp'])

    # 9. Model Versions / Model Registry tables
    op.create_table(
        'model_versions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('version_tag', sa.String(length=50), unique=True, nullable=False),
        sa.Column('model_architecture', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('brier_score', sa.Float(), nullable=True),
        sa.Column('expected_calibration_error', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.Column('hyperparameters', sa.JSON(), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'model_registry',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('version_tag', sa.String(length=50), unique=True, nullable=False),
        sa.Column('model_architecture', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('feature_schema_version', sa.String(length=32), nullable=False, server_default='v1.0.0'),
        sa.Column('calibration_version', sa.String(length=50), nullable=False),
        sa.Column('conformal_version', sa.String(length=50), nullable=False),
        sa.Column('brier_score', sa.Float(), nullable=True),
        sa.Column('expected_calibration_error', sa.Float(), nullable=True),
        sa.Column('f1_score', sa.Float(), nullable=True),
        sa.Column('precision_score', sa.Float(), nullable=True),
        sa.Column('recall_score', sa.Float(), nullable=True),
        sa.Column('roc_auc_score', sa.Float(), nullable=True),
        sa.Column('conformal_target_coverage', sa.Float(), nullable=False, server_default='0.90'),
        sa.Column('conformal_empirical_coverage', sa.Float(), nullable=True),
        sa.Column('hyperparameters', sa.JSON(), nullable=False),
        sa.Column('metrics_summary', sa.JSON(), nullable=False),
        sa.Column('artifact_path', sa.String(length=255), nullable=True),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('trained_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('activated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 10. Risk State Records & Transition Records
    op.create_table(
        'risk_state_records',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('evaluation_id', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_state', sa.String(length=32), nullable=False),
        sa.Column('previous_state', sa.String(length=32), nullable=False),
        sa.Column('max_calibrated_probability', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('triggering_horizon_minutes', sa.Integer(), nullable=True),
        sa.Column('active_alert_horizons', sa.JSON(), nullable=False),
        sa.Column('anomaly_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('uncertainty_level', sa.String(length=32), nullable=False, server_default='LOW'),
        sa.Column('evidence_summary', sa.JSON(), nullable=False),
        sa.Column('top_risk_features', sa.JSON(), nullable=False),
        sa.Column('attack_path_summary', sa.JSON(), nullable=False),
        sa.Column('is_hysteresis_dampened', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_risk_state_time', 'risk_state_records', ['current_state', 'timestamp'])

    op.create_table(
        'risk_transition_records',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('transition_id', sa.String(length=64), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('previous_state', sa.String(length=32), nullable=False),
        sa.Column('new_state', sa.String(length=32), nullable=False),
        sa.Column('forecast_probability', sa.Float(), nullable=False),
        sa.Column('anomaly_score', sa.Float(), nullable=False),
        sa.Column('uncertainty', sa.String(length=32), nullable=False, server_default='LOW'),
        sa.Column('triggering_horizon', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('triggering_evidence', sa.JSON(), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_transition_time_state', 'risk_transition_records', ['new_state', 'timestamp'])

    # 11. Counterfactual Scenarios table
    op.create_table(
        'counterfactual_scenarios',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('scenario_id', sa.String(length=64), unique=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('scenario_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('scientific_disclaimer', sa.String(length=500), nullable=False),
        sa.Column('requested_perturbations', sa.JSON(), nullable=False),
        sa.Column('applied_perturbations', sa.JSON(), nullable=False),
        sa.Column('horizon_results', sa.JSON(), nullable=False),
        sa.Column('baseline_vector_summary', sa.JSON(), nullable=False),
        sa.Column('counterfactual_vector_summary', sa.JSON(), nullable=False),
        sa.Column('any_decision_flipped', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('max_risk_reduction', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_risk_elevation', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('execution_latency_ms', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('include_shap', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_cf_user_time', 'counterfactual_scenarios', ['user_id', 'timestamp'])

    # 12. Security Alerts & Incident Cases
    op.create_table(
        'security_alerts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('severity', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='OPEN'),
        sa.Column('predicted_threat', sa.String(length=100), nullable=False),
        sa.Column('forecast_id', sa.String(length=36), nullable=True),
        sa.Column('estimated_time_to_impact_minutes', sa.Integer(), nullable=False),
        sa.Column('recommended_mitigation', sa.String(length=1000), nullable=True),
        sa.Column('context_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'incident_cases',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('assigned_to', sa.String(length=100), nullable=True),
        sa.Column('summary', sa.String(length=2000), nullable=True),
        sa.Column('indicators_of_compromise', sa.JSON(), nullable=False),
        sa.Column('timeline_events', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # 13. Audit Logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('actor_user_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=64), nullable=True),
        sa.Column('client_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='SUCCESS'),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_audit_action_time', 'audit_logs', ['action', 'created_at'])
    op.create_index('idx_audit_user_time', 'audit_logs', ['actor_user_id', 'created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('incident_cases')
    op.drop_table('security_alerts')
    op.drop_table('counterfactual_scenarios')
    op.drop_table('risk_transition_records')
    op.drop_table('risk_state_records')
    op.drop_table('model_registry')
    op.drop_table('model_versions')
    op.drop_table('attack_forecasts')
    op.drop_table('forecast_windows')
    op.drop_table('telemetry_batches')
    op.drop_table('network_flows')
    op.drop_table('telemetry_sources')
    op.drop_table('telemetry_jobs')
    op.drop_table('auth_sessions')
    op.drop_table('users')
