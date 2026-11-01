
import { useState } from 'react';
import type { FormEvent } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  LoaderCircle,
  Search,
  ShieldAlert,
  ShieldCheck,
  XCircle,
  Activity,
  CalendarDays,
  ClipboardCheck,
  Factory,
  Fingerprint,
  Gauge,
  RefreshCw,
} from 'lucide-react';


type AuthorizationResult = {
  asset_id: string;
  asset_name?: string;
  plant_area?: string;
  lifecycle_state?: string;
  proposed_at?: string;
  decision: 'ALLOW' | 'BLOCK' | 'CONDITIONAL_ALLOW';
  reason_code: string;
  reason: string;
  calibration_id?: string;
  calibration_result?: string;
  calibration_performed_at?: string;
  due_at?: string;
  overdue?: boolean;
  certificate_id?: string;
  extension?: {
    extension_id: string;
    approved_from: string;
    approved_until: string;
    approver_reference: string;
    reason: string;
  };
  work_order?: {
    work_order_id: string;
    work_type: string;
    status: string;
  };
};

type EvaluationResponse = {
  evaluation_type: string;
  result: AuthorizationResult;
  evaluated_at: string;
};

function localDateTime() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;

  return new Date(now.getTime() - offset)
    .toISOString()
    .slice(0, 16);
}

function formatDate(value?: string) {
  if (!value) return '—';

  const parsed = new Date(value.replace(' ', 'T'));

  return Number.isNaN(parsed.getTime())
    ? value
    : parsed.toLocaleString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
}

export default function AuthorizationSimulator() {
  const [assetId, setAssetId] = useState('AST-000002');
  const [proposedAt, setProposedAt] = useState(localDateTime());
  const [result, setResult] = useState<AuthorizationResult | null>(null);
  const [evaluatedAt, setEvaluatedAt] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function evaluate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!assetId.trim()) {
      setError('Enter an asset ID.');
      return;
    }

    if (!proposedAt) {
      setError('Select the proposed production-use date and time.');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);
    setEvaluatedAt('');

    try {
      const response = await fetch('/api/authorization/evaluate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          asset_id: assetId.trim(),
          proposed_at: proposedAt.replace('T', ' ') + ':00',
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || `API returned ${response.status}`);
      }

      const payload = data as EvaluationResponse;

      setResult(payload.result);
      setEvaluatedAt(payload.evaluated_at);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : 'Unable to evaluate production authorization.'
      );
    } finally {
      setLoading(false);
    }
  }

  const decision = result?.decision;

  const decisionClass =
    decision === 'ALLOW'
      ? 'allow'
      : decision === 'BLOCK'
        ? 'block'
        : 'conditional';

  const decisionIcon =
    decision === 'ALLOW'
      ? <CheckCircle2 size={25} />
      : decision === 'BLOCK'
        ? <XCircle size={25} />
        : <ShieldAlert size={25} />;

  return (
    <div className="auth-page">
      <div className="heading-row auth-heading">
        <div>
          <div className="eyebrow">PRODUCTION SAFETY CONTROL</div>
          <h1>Authorization simulator</h1>
          <p className="subheading">
            Evaluate whether an industrial instrument is permitted to be used
            at a proposed production time.
          </p>
        </div>

        <div className="auth-heading-status">
          <span className="auth-live-dot" />
          Rule engine
          <strong>Active</strong>
        </div>
      </div>

      <div className="auth-layout">
        <section className="panel auth-form-panel">
          <div className="auth-panel-heading">
            <div className="auth-heading-icon">
              <ShieldCheck size={20} />
            </div>
            <div>
              <h2>Evaluate production use</h2>
              <p>Provide the instrument details to run a compliance check.</p>
            </div>
          </div>

          <form onSubmit={evaluate} className="auth-form">
            <div className="auth-field">
              <label htmlFor="asset-id">Instrument asset ID</label>
              <div className="auth-input-wrap">
                <Search size={17} />
                <input
                  id="asset-id"
                  value={assetId}
                  onChange={(event) => setAssetId(event.target.value)}
                  placeholder="Example: AST-000002"
                  autoComplete="off"
                  required
                />
              </div>
              <span className="auth-field-help">
                Enter the registered asset identifier.
              </span>
            </div>

            <div className="auth-field">
              <label htmlFor="proposed-at">Proposed production-use time</label>
              <div className="auth-input-wrap">
                <CalendarDays size={17} />
                <input
                  id="proposed-at"
                  type="datetime-local"
                  value={proposedAt}
                  onChange={(event) => setProposedAt(event.target.value)}
                  required
                />
              </div>
              <span className="auth-field-help">
                Select when the instrument is intended to be used.
              </span>
            </div>

            <button
              type="submit"
              className="auth-submit"
              disabled={loading}
            >
              {loading ? (
                <>
                  <LoaderCircle size={18} className="auth-spin" />
                  Evaluating compliance...
                </>
              ) : (
                <>
                  <ShieldCheck size={18} />
                  Evaluate authorization
                </>
              )}
            </button>
          </form>

          {error && (
            <div className="auth-error">
              <AlertTriangle size={18} />
              <div>
                <strong>Evaluation failed</strong>
                <p>{error}</p>
              </div>
            </div>
          )}

          <div className="auth-notice">
            <AlertTriangle size={17} />
            <p>
              <strong>Read-only evaluation.</strong> This simulator checks
              current database records. It does not create a production-use
              record or modify instrument data.
            </p>
          </div>

          <div className="auth-form-footer">
            <ShieldCheck size={15} />
            <span>CalibGuard compliance rule evaluation</span>
          </div>
        </section>

        <section className="panel auth-result-panel">
          <div className="auth-panel-heading auth-result-heading">
            <div className="auth-heading-icon">
              <Activity size={20} />
            </div>
            <div>
              <h2>Authorization result</h2>
              <p>Decision returned by the CalibGuard backend.</p>
            </div>
            {result && (
              <span className="auth-result-tag">Evaluation complete</span>
            )}
          </div>

          {!result && !loading && (
            <div className="auth-empty">
              <div className="auth-empty-icon">
                <Fingerprint size={34} />
              </div>
              <strong>Awaiting evaluation</strong>
              <p>
                Submit an asset ID and proposed usage time to view its
                authorization decision.
              </p>
              <span>Results will appear here</span>
            </div>
          )}

          {loading && (
            <div className="auth-empty">
              <div className="auth-loading-icon">
                <LoaderCircle size={34} className="auth-spin" />
              </div>
              <strong>Checking compliance rules</strong>
              <p>
                Reviewing calibration, certificate, work-order and exception
                records.
              </p>
              <span>Please wait while the backend evaluates this request.</span>
            </div>
          )}

          {result && (
            <div className="auth-result-content">
              <div className={`auth-decision-banner ${decisionClass}`}>
                <div className="auth-decision-icon">{decisionIcon}</div>
                <div className="auth-decision-copy">
                  <span>PRODUCTION DECISION</span>
                  <strong>{decision?.replaceAll('_', ' ')}</strong>
                  <small>{result.reason_code}</small>
                </div>
                <div className="auth-decision-mark">
                  {decision === 'ALLOW'
                    ? 'APPROVED'
                    : decision === 'BLOCK'
                      ? 'RESTRICTED'
                      : 'EXCEPTION'}
                </div>
              </div>

              <div className="auth-reason">
                <div className="auth-section-label">
                  <ClipboardCheck size={16} />
                  Decision explanation
                </div>
                <p>{result.reason}</p>
              </div>

              <div className="auth-detail-section">
                <div className="auth-section-label">
                  <Gauge size={16} />
                  Instrument information
                </div>

                <div className="auth-detail-grid">
                  <Detail label="Asset ID" value={result.asset_id} />
                  <Detail label="Instrument" value={result.asset_name} />
                  <Detail label="Plant area" value={result.plant_area} />
                  <Detail
                    label="Lifecycle state"
                    value={result.lifecycle_state}
                  />
                </div>
              </div>

              <div className="auth-detail-section">
                <div className="auth-section-label">
                  <CalendarDays size={16} />
                  Calibration and certificate
                </div>

                <div className="auth-detail-grid">
                  <Detail
                    label="Calibration ID"
                    value={result.calibration_id}
                  />
                  <Detail
                    label="Calibration result"
                    value={result.calibration_result}
                    status={result.calibration_result?.toUpperCase()}
                  />
                  <Detail
                    label="Calibration performed"
                    value={formatDate(result.calibration_performed_at)}
                  />
                  <Detail
                    label="Calibration due"
                    value={formatDate(result.due_at)}
                  />
                  <Detail
                    label="Certificate ID"
                    value={result.certificate_id}
                  />
                  <Detail
                    label="Overdue"
                    value={
                      result.overdue === undefined
                        ? '—'
                        : result.overdue
                          ? 'Yes'
                          : 'No'
                    }
                    status={
                      result.overdue === undefined
                        ? undefined
                        : result.overdue
                          ? 'YES'
                          : 'NO'
                    }
                  />
                </div>
              </div>

              {result.extension && (
                <div className="auth-extra-card">
                  <div className="auth-extra-title">
                    <ShieldCheck size={17} />
                    <h3>Approved emergency extension</h3>
                  </div>
                  <div className="auth-detail-grid">
                    <Detail
                      label="Extension ID"
                      value={result.extension.extension_id}
                    />
                    <Detail
                      label="Approver"
                      value={result.extension.approver_reference}
                    />
                    <Detail
                      label="Approved from"
                      value={formatDate(result.extension.approved_from)}
                    />
                    <Detail
                      label="Approved until"
                      value={formatDate(result.extension.approved_until)}
                    />
                  </div>
                  <p className="auth-extra-reason">
                    <strong>Reason:</strong> {result.extension.reason}
                  </p>
                </div>
              )}

              {result.work_order && (
                <div className="auth-extra-card">
                  <div className="auth-extra-title">
                    <Factory size={17} />
                    <h3>Associated work order</h3>
                  </div>
                  <div className="auth-detail-grid">
                    <Detail
                      label="Work order ID"
                      value={result.work_order.work_order_id}
                    />
                    <Detail
                      label="Work type"
                      value={result.work_order.work_type}
                    />
                    <Detail
                      label="Status"
                      value={result.work_order.status}
                    />
                  </div>
                </div>
              )}

              <div className="auth-evaluation-time">
                <Clock size={14} />
                <span>Evaluated at {formatDate(evaluatedAt)}</span>
                <button
                  type="button"
                  onClick={() => {
                    setResult(null);
                    setEvaluatedAt('');
                    setError('');
                  }}
                  title="Clear evaluation result"
                >
                  <RefreshCw size={14} />
                  Clear result
                </button>
              </div>
            </div>
          )}
        </section>
      </div>

      <section className="panel auth-guide-panel">
        <div className="auth-guide-heading">
          <div>
            <div className="eyebrow">COMPLIANCE LOGIC</div>
            <h2>Authorization decision guide</h2>
            <p>Understand how the rule engine classifies production use.</p>
          </div>
          <ShieldCheck size={23} className="auth-guide-shield" />
        </div>

        <div className="auth-guide-grid">
          <GuideItem
            type="allow"
            icon={<CheckCircle2 size={21} />}
            title="ALLOW"
            description="Applicable calibration and certificate checks pass."
            example="Example: A valid calibration and certificate cover the proposed use."
          />
          <GuideItem
            type="block"
            icon={<XCircle size={21} />}
            title="BLOCK"
            description="A mandatory compliance or availability check fails."
            example="Example: The certificate is expired or does not match the asset."
          />
          <GuideItem
            type="conditional"
            icon={<ShieldAlert size={21} />}
            title="CONDITIONAL ALLOW"
            description="An approved emergency extension covers the proposed use."
            example="Example: An authorized exception permits use within its approved window."
          />
        </div>
      </section>
    </div>
  );
}

function Detail({
  label,
  value,
  status,
}: {
  label: string;
  value?: string;
  status?: string;
}) {
  const displayValue = value || '—';

  return (
    <div className="auth-detail-item">
      <span>{label}</span>
      <strong
        className={
          status === 'YES' || status === 'FAIL'
            ? 'auth-value-danger'
            : status === 'NO' || status === 'PASS'
              ? 'auth-value-success'
              : ''
        }
      >
        {displayValue}
      </strong>
    </div>
  );
}

function GuideItem({
  type,
  icon,
  title,
  description,
  example,
}: {
  type: 'allow' | 'block' | 'conditional';
  icon: React.ReactNode;
  title: string;
  description: string;
  example: string;
}) {
  return (
    <div className={`auth-guide-item ${type}`}>
      <div className="auth-guide-icon">{icon}</div>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
        <small>{example}</small>
      </div>
    </div>
  );
}
