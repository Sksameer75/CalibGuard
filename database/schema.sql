CREATE DATABASE IF NOT EXISTS calibguard CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE calibguard;

CREATE TABLE instrument_types (
  instrument_type_id VARCHAR(24) PRIMARY KEY,
  type_name VARCHAR(120) NOT NULL UNIQUE,
  measurement_unit VARCHAR(24) NOT NULL,
  tolerance DECIMAL(12,4) NOT NULL,
  default_interval_days INT NOT NULL,
  CHECK (tolerance > 0),
  CHECK (default_interval_days > 0)
);

CREATE TABLE suppliers (
  supplier_id VARCHAR(24) PRIMARY KEY,
  supplier_name VARCHAR(160) NOT NULL,
  supplier_kind ENUM('MANUFACTURER','CALIBRATION_LAB','BOTH') NOT NULL,
  accreditation_reference VARCHAR(100) NULL
);

CREATE TABLE assets (
  asset_id VARCHAR(24) PRIMARY KEY,
  instrument_type_id VARCHAR(24) NOT NULL,
  supplier_id VARCHAR(24) NULL,
  serial_number VARCHAR(100) NOT NULL UNIQUE,
  asset_name VARCHAR(160) NOT NULL,
  plant_area VARCHAR(100) NOT NULL,
  commissioned_at DATETIME NOT NULL,
  retired_at DATETIME NULL,
  lifecycle_state ENUM('ACTIVE','QUARANTINED','RETIRED') NOT NULL DEFAULT 'ACTIVE',
  FOREIGN KEY (instrument_type_id) REFERENCES instrument_types(instrument_type_id),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
  CHECK (retired_at IS NULL OR retired_at >= commissioned_at)
);

CREATE TABLE calibration_plans (
  plan_id VARCHAR(30) PRIMARY KEY,
  asset_id VARCHAR(24) NOT NULL,
  interval_days INT NOT NULL,
  effective_from DATETIME NOT NULL,
  effective_to DATETIME NULL,
  policy_requires_block BOOLEAN NOT NULL DEFAULT TRUE,
  requires_certificate BOOLEAN NOT NULL DEFAULT TRUE,
  state ENUM('ACTIVE','SUPERSEDED','CANCELLED') NOT NULL DEFAULT 'ACTIVE',
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
  CHECK (interval_days > 0),
  CHECK (effective_to IS NULL OR effective_to > effective_from),
  INDEX (asset_id, effective_from)
);

CREATE TABLE calibration_events (
  calibration_id VARCHAR(64) PRIMARY KEY,
  asset_id VARCHAR(24) NOT NULL,
  plan_id VARCHAR(30) NOT NULL,
  supplier_id VARCHAR(24) NULL,
  performed_at DATETIME NOT NULL,
  reference_value DECIMAL(14,4) NOT NULL,
  measured_value DECIMAL(14,4) NOT NULL,
  absolute_error DECIMAL(14,4) NOT NULL,
  tolerance_at_test DECIMAL(14,4) NOT NULL,
  result ENUM('PASS','FAIL') NOT NULL,
  calculated_due_at DATETIME NULL,
  recorded_due_at DATETIME NULL,
  recorded_at DATETIME NOT NULL,
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
  FOREIGN KEY (plan_id) REFERENCES calibration_plans(plan_id),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
  CHECK (absolute_error >= 0),
  CHECK (tolerance_at_test > 0),
  INDEX (asset_id, performed_at)
);

CREATE TABLE certificates (
  certificate_id VARCHAR(80) PRIMARY KEY,
  calibration_id VARCHAR(64) NOT NULL UNIQUE,
  asset_id VARCHAR(24) NOT NULL,
  issued_at DATETIME NOT NULL,
  valid_until DATETIME NOT NULL,
  certificate_status ENUM('ISSUED','REVOKED') NOT NULL DEFAULT 'ISSUED',
  document_reference VARCHAR(255) NULL,
  FOREIGN KEY (calibration_id) REFERENCES calibration_events(calibration_id),
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
  CHECK (valid_until >= issued_at)
);

CREATE TABLE work_orders (
  work_order_id VARCHAR(32) PRIMARY KEY,
  calibration_id VARCHAR(64) NULL,
  work_type ENUM('SCHEDULED_CALIBRATION','CORRECTIVE_ACTION','INSPECTION') NOT NULL,
  status ENUM('OPEN','IN_PROGRESS','COMPLETED','CANCELLED') NOT NULL DEFAULT 'OPEN',
  opened_at DATETIME NOT NULL,
  started_at DATETIME NULL,
  completed_at DATETIME NULL,
  downtime_minutes INT NOT NULL DEFAULT 0,
  FOREIGN KEY (calibration_id) REFERENCES calibration_events(calibration_id),
  CHECK (downtime_minutes >= 0),
  CHECK (completed_at IS NULL OR completed_at >= opened_at)
);

CREATE TABLE work_order_assets (
  work_order_id VARCHAR(32) NOT NULL,
  asset_id VARCHAR(24) NOT NULL,
  PRIMARY KEY (work_order_id, asset_id),
  FOREIGN KEY (work_order_id) REFERENCES work_orders(work_order_id),
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
);

CREATE TABLE emergency_extensions (
  extension_id VARCHAR(32) PRIMARY KEY,
  asset_id VARCHAR(24) NOT NULL,
  approved_from DATETIME NOT NULL,
  approved_until DATETIME NOT NULL,
  approval_state ENUM('REQUESTED','APPROVED','REJECTED','REVOKED') NOT NULL,
  approver_reference VARCHAR(100) NULL,
  reason VARCHAR(500) NOT NULL,
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
  CHECK (approved_until > approved_from)
);

CREATE TABLE production_uses (
  use_id VARCHAR(80) PRIMARY KEY,
  asset_id VARCHAR(24) NOT NULL,
  used_at DATETIME NOT NULL,
  batch_reference VARCHAR(64) NOT NULL,
  decision ENUM('ALLOW','CONDITIONAL_ALLOW','BLOCK') NOT NULL,
  was_executed BOOLEAN NOT NULL,
  evaluated_at DATETIME NOT NULL,
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
  INDEX (asset_id, used_at)
);

CREATE TABLE impact_assessments (
  assessment_id VARCHAR(32) PRIMARY KEY,
  calibration_id VARCHAR(64) NOT NULL,
  status ENUM('OPEN','IN_PROGRESS','COMPLETED') NOT NULL,
  created_at DATETIME NOT NULL,
  closed_at DATETIME NULL,
  notes VARCHAR(1000) NULL,
  FOREIGN KEY (calibration_id) REFERENCES calibration_events(calibration_id)
);

CREATE TABLE alerts (
  alert_id VARCHAR(32) PRIMARY KEY,
  asset_id VARCHAR(24) NOT NULL,
  calibration_id VARCHAR(64) NULL,
  use_id VARCHAR(80) NULL,
  issue_type VARCHAR(64) NOT NULL,
  severity ENUM('INFO','WARNING','CRITICAL') NOT NULL,
  alert_state ENUM('OPEN','ACKNOWLEDGED','RESOLVED') NOT NULL DEFAULT 'OPEN',
  created_at DATETIME NOT NULL,
  FOREIGN KEY (asset_id) REFERENCES assets(asset_id),
  FOREIGN KEY (calibration_id) REFERENCES calibration_events(calibration_id),
  FOREIGN KEY (use_id) REFERENCES production_uses(use_id)
);

CREATE TABLE audit_records (
  audit_id VARCHAR(32) PRIMARY KEY,
  entity_name VARCHAR(64) NOT NULL,
  entity_id VARCHAR(80) NOT NULL,
  action VARCHAR(64) NOT NULL,
  actor_reference VARCHAR(100) NOT NULL,
  occurred_at DATETIME NOT NULL,
  details JSON NOT NULL,
  INDEX (entity_name, entity_id, occurred_at)
);
