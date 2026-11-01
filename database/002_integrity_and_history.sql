-- CalibGuard additive migration 002: integrity and append-only state history
-- Run once against the existing calibguard database. Do not rerun blindly.
USE calibguard;

-- Composite keys ensure that a calibration plan belongs to the same asset
-- as the calibration event that references it.
ALTER TABLE calibration_plans
  ADD UNIQUE KEY uq_calibration_plan_asset (plan_id, asset_id);
ALTER TABLE calibration_events
  ADD CONSTRAINT fk_calibration_plan_same_asset
  FOREIGN KEY (plan_id, asset_id)
  REFERENCES calibration_plans(plan_id, asset_id);

-- Preserve explicit state changes as immutable historical events.
CREATE TABLE lifecycle_events (
  lifecycle_event_id VARCHAR(40) PRIMARY KEY,
  entity_name ENUM('ASSET','CALIBRATION_PLAN','CERTIFICATE','WORK_ORDER',
                   'EMERGENCY_EXTENSION','ALERT','IMPACT_ASSESSMENT') NOT NULL,
  entity_id VARCHAR(80) NOT NULL,
  from_state VARCHAR(40) NULL,
  to_state VARCHAR(40) NOT NULL,
  occurred_at DATETIME NOT NULL,
  actor_reference VARCHAR(100) NOT NULL,
  reason VARCHAR(500) NULL,
  INDEX idx_lifecycle_entity_time (entity_name, entity_id, occurred_at)
);

-- Prevent changes or deletion of recorded transitions.
DELIMITER $$
CREATE TRIGGER trg_lifecycle_no_update
BEFORE UPDATE ON lifecycle_events
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Lifecycle history is append-only';
END$$
CREATE TRIGGER trg_lifecycle_no_delete
BEFORE DELETE ON lifecycle_events
FOR EACH ROW
BEGIN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Lifecycle history is append-only';
END$$
DELIMITER ;

-- Accelerate common compliance and reporting queries.
CREATE INDEX idx_extensions_asset_window
  ON emergency_extensions (asset_id, approved_from, approved_until);
CREATE INDEX idx_uses_time_decision
  ON production_uses (used_at, decision);
CREATE INDEX idx_calibrations_result_time
  ON calibration_events (result, performed_at);
