import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle2,
  ClipboardCheck,
  ClipboardList,
  Clock3,
  LoaderCircle,
  RefreshCw,
  Wrench,
} from 'lucide-react';

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5000';

type CorrectiveAction = {
  asset_id: string;
  asset_name: string;
  plant_area: string;
  lifecycle_state: string;
  calibration_id: string;
  failed_at: string;
  absolute_error: number | string | null;
  tolerance_at_test: number | string | null;
  assessment_id: string | null;
  assessment_status: 'OPEN' | 'IN_PROGRESS' | 'COMPLETED' | null;
  assessment_created_at: string | null;
  assessment_closed_at: string | null;
  assessment_notes: string | null;
  work_order_id: string | null;
  work_order_status: string | null;
  work_order_opened_at: string | null;
  work_order_started_at: string | null;
  work_order_completed_at: string | null;
  downtime_minutes: number | null;
};

type Summary = {
  failed_latest_calibrations: number;
  without_assessment: number;
  without_corrective_work_order: number;
  open_assessments: number;
  in_progress_assessments: number;
};

type ApiResponse = {
  data: CorrectiveAction[];
  summary: Summary;
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
};

const emptySummary: Summary = {
  failed_latest_calibrations: 0,
  without_assessment: 0,
  without_corrective_work_order: 0,
  open_assessments: 0,
  in_progress_assessments: 0,
};

async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  const result = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(result.error || `Request failed (${response.status})`);
  }

  return result as T;
}

function formatDate(value: string | null | undefined) {
  if (!value) return '—';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleString();
}

function formatNumber(value: number | string | null) {
  if (value === null || value === undefined) return '—';

  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(4) : String(value);
}

function statusClass(status: string | null | undefined) {
  if (!status) return 'ca-status ca-status-missing';

  return `ca-status ca-status-${status.toLowerCase()}`;
}

export default function CorrectiveActions() {
  const [records, setRecords] = useState<CorrectiveAction[]>([]);
  const [summary, setSummary] = useState<Summary>(emptySummary);
  const [selected, setSelected] = useState<CorrectiveAction | null>(null);
  const [filter, setFilter] = useState('ALL');
  const [notes, setNotes] = useState('');
  const [createNote, setCreateNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const loadRecords = useCallback(async () => {
    setLoading(true);
    setError('');

    try {
      const query = new URLSearchParams({
        page: '1',
        limit: '100',
      });

      if (filter !== 'ALL') {
        query.set('status', filter);
      }

      const result = await apiRequest<ApiResponse>(
        `/api/corrective-actions?${query.toString()}`,
      );

      setRecords(result.data || []);
      setSummary(result.summary || emptySummary);

      setSelected((current) => {
        if (!current) return null;

        return (
          result.data.find(
            (item) => item.calibration_id === current.calibration_id,
          ) || null
        );
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to load corrective actions.',
      );
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  useEffect(() => {
    setNotes(selected?.assessment_notes || '');
    setCreateNote('');
    setMessage('');
  }, [selected?.calibration_id, selected?.assessment_id]);

  async function createCorrectiveWorkOrder(record: CorrectiveAction) {
    setSaving(true);
    setError('');
    setMessage('');

    try {
      await apiRequest('/api/corrective-actions/work-orders', {
        method: 'POST',
        body: JSON.stringify({
          asset_id: record.asset_id,
          calibration_id: record.calibration_id,
          note: createNote,
          actor_reference: 'QUALITY_ENGINEER',
        }),
      });

      setMessage('Corrective work order and impact assessment created.');
      await loadRecords();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to create corrective work order.',
      );
    } finally {
      setSaving(false);
    }
  }

  async function updateAssessment(
    record: CorrectiveAction,
    nextStatus: 'IN_PROGRESS' | 'COMPLETED',
  ) {
    if (!record.assessment_id) {
      setError('Create the corrective work order first.');
      return;
    }

    if (!notes.trim()) {
      setError('Enter investigation notes before changing the assessment status.');
      return;
    }

    if (
      nextStatus === 'COMPLETED' &&
      !window.confirm(
        'Mark this impact assessment as completed? This status cannot be reopened.',
      )
    ) {
      return;
    }

    setSaving(true);
    setError('');
    setMessage('');

    try {
      await apiRequest(`/api/impact-assessments/${record.assessment_id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status: nextStatus,
          notes: notes.trim(),
          actor_reference: 'QUALITY_ENGINEER',
        }),
      });

      setMessage(`Impact assessment moved to ${nextStatus}.`);
      await loadRecords();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to update impact assessment.',
      );
    } finally {
      setSaving(false);
    }
  }

  async function updateWorkOrder(
    record: CorrectiveAction,
    nextStatus: 'IN_PROGRESS' | 'COMPLETED',
  ) {
    if (!record.work_order_id) return;

    if (
      nextStatus === 'COMPLETED' &&
      !window.confirm(
        'Complete this corrective work order? The linked impact assessment must already be completed.',
      )
    ) {
      return;
    }

    let downtime = record.downtime_minutes || 0;

    if (nextStatus === 'COMPLETED') {
      const entered = window.prompt(
        'Enter total downtime in minutes:',
        String(downtime),
      );

      if (entered === null) return;

      downtime = Number(entered);

      if (!Number.isInteger(downtime) || downtime < 0) {
        setError('Downtime must be a non-negative whole number.');
        return;
      }
    }

    setSaving(true);
    setError('');
    setMessage('');

    try {
      await apiRequest(
        `/api/work-orders/${record.work_order_id}/status`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            status: nextStatus,
            downtime_minutes: downtime,
            actor_reference: 'QUALITY_ENGINEER',
          }),
        },
      );

      setMessage(`Corrective work order moved to ${nextStatus}.`);
      await loadRecords();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Unable to update work order.',
      );
    } finally {
      setSaving(false);
    }
  }

  const activeRecord =
    records.find(
      (record) =>
        record.calibration_id === selected?.calibration_id,
    ) || selected;

  return (
    <section className="ca-workspace">
      <div className="ca-header">
        <div>
          <div className="ca-eyebrow">QUALITY MANAGEMENT</div>
          <h1>Corrective Actions</h1>
          <p>
            Investigate failed calibrations, record impact assessments, and
            track corrective work orders.
          </p>
        </div>

        <button
          className="ca-refresh"
          onClick={() => void loadRecords()}
          disabled={loading || saving}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      <div className="ca-metrics">
        <div className="ca-metric">
          <span>Failed latest calibrations</span>
          <strong>{summary.failed_latest_calibrations}</strong>
        </div>
        <div className="ca-metric">
          <span>Without assessment</span>
          <strong>{summary.without_assessment}</strong>
        </div>
        <div className="ca-metric">
          <span>Without corrective work order</span>
          <strong>{summary.without_corrective_work_order}</strong>
        </div>
        <div className="ca-metric">
          <span>Open assessments</span>
          <strong>{summary.open_assessments}</strong>
        </div>
        <div className="ca-metric">
          <span>In-progress assessments</span>
          <strong>{summary.in_progress_assessments}</strong>
        </div>
      </div>

      {error && (
        <div className="ca-message ca-error">
          <AlertCircle size={17} />
          {error}
        </div>
      )}

      {message && (
        <div className="ca-message ca-success">
          <CheckCircle2 size={17} />
          {message}
        </div>
      )}

      <div className="ca-toolbar">
        <div>
          <h2>Failed calibration register</h2>
          <p>Assets whose latest recorded calibration result is FAIL.</p>
        </div>

        <select
          value={filter}
          onChange={(event) => {
            setSelected(null);
            setFilter(event.target.value);
          }}
          aria-label="Filter by assessment status"
        >
          <option value="ALL">All assessments</option>
          <option value="OPEN">Open</option>
          <option value="IN_PROGRESS">In progress</option>
          <option value="COMPLETED">Completed</option>
        </select>
      </div>

      {loading ? (
        <div className="ca-empty">
          <LoaderCircle className="ca-spin" size={24} />
          Loading corrective actions...
        </div>
      ) : records.length === 0 ? (
        <div className="ca-empty">
          <ClipboardCheck size={28} />
          <strong>No failed latest calibrations found</strong>
          <span>Try another assessment filter.</span>
        </div>
      ) : (
        <div className="ca-content">
          <div className="ca-table-wrap">
            <table className="ca-table">
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Plant area</th>
                  <th>Failed at</th>
                  <th>Assessment</th>
                  <th>Work order</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr
                    key={record.calibration_id}
                    className={
                      activeRecord?.calibration_id === record.calibration_id
                        ? 'ca-selected-row'
                        : ''
                    }
                    onClick={() => setSelected(record)}
                  >
                    <td>
                      <strong>{record.asset_name}</strong>
                      <small>{record.asset_id}</small>
                    </td>
                    <td>{record.plant_area || '—'}</td>
                    <td>{formatDate(record.failed_at)}</td>
                    <td>
                      <span className={statusClass(record.assessment_status)}>
                        {record.assessment_status || 'MISSING'}
                      </span>
                    </td>
                    <td>
                      <span className={statusClass(record.work_order_status)}>
                        {record.work_order_status || 'MISSING'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {activeRecord && (
            <aside className="ca-detail">
              <div className="ca-detail-heading">
                <div>
                  <span className="ca-eyebrow">CASE DETAILS</span>
                  <h2>{activeRecord.asset_name}</h2>
                  <small>{activeRecord.asset_id}</small>
                </div>
                <span className="ca-fail-tag">CALIBRATION FAILED</span>
              </div>

              <div className="ca-facts">
                <div>
                  <span>Calibration ID</span>
                  <strong>{activeRecord.calibration_id}</strong>
                </div>
                <div>
                  <span>Failure date</span>
                  <strong>{formatDate(activeRecord.failed_at)}</strong>
                </div>
                <div>
                  <span>Measured error</span>
                  <strong>{formatNumber(activeRecord.absolute_error)}</strong>
                </div>
                <div>
                  <span>Test tolerance</span>
                  <strong>{formatNumber(activeRecord.tolerance_at_test)}</strong>
                </div>
              </div>

              <div className="ca-section-title">
                <ClipboardList size={17} />
                Impact assessment
              </div>

              <div className="ca-status-line">
                <span>Assessment status</span>
                <span className={statusClass(activeRecord.assessment_status)}>
                  {activeRecord.assessment_status || 'NOT CREATED'}
                </span>
              </div>

              {activeRecord.assessment_id ? (
                <>
                  <div className="ca-id-line">
                    Assessment ID: {activeRecord.assessment_id}
                  </div>

                  <label className="ca-label" htmlFor="ca-notes">
                    Investigation notes
                  </label>
                  <textarea
                    id="ca-notes"
                    value={notes}
                    onChange={(event) => setNotes(event.target.value)}
                    maxLength={1000}
                    rows={5}
                    placeholder="Record the investigation findings and potential production impact..."
                    disabled={
                      saving ||
                      activeRecord.assessment_status === 'COMPLETED'
                    }
                  />

                  <div className="ca-note-count">{notes.length}/1000</div>

                  {activeRecord.assessment_status === 'OPEN' && (
                    <button
                      className="ca-primary-button"
                      disabled={saving || !notes.trim()}
                      onClick={() =>
                        void updateAssessment(activeRecord, 'IN_PROGRESS')
                      }
                    >
                      <ClipboardCheck size={16} />
                      Start investigation
                    </button>
                  )}

                  {activeRecord.assessment_status === 'IN_PROGRESS' && (
                    <button
                      className="ca-primary-button"
                      disabled={saving || !notes.trim()}
                      onClick={() =>
                        void updateAssessment(activeRecord, 'COMPLETED')
                      }
                    >
                      <CheckCircle2 size={16} />
                      Complete assessment
                    </button>
                  )}

                  {activeRecord.assessment_status === 'COMPLETED' && (
                    <div className="ca-locked-note">
                      <CheckCircle2 size={16} />
                      Assessment completed and locked.
                    </div>
                  )}
                </>
              ) : (
                <div className="ca-create-box">
                  <p>
                    No impact assessment is linked to this failed calibration.
                    Create a corrective work order to open one.
                  </p>
                  <textarea
                    value={createNote}
                    onChange={(event) => setCreateNote(event.target.value)}
                    maxLength={500}
                    rows={3}
                    placeholder="Initial observation or reason for investigation..."
                    disabled={saving}
                  />
                  <button
                    className="ca-primary-button"
                    disabled={saving}
                    onClick={() =>
                      void createCorrectiveWorkOrder(activeRecord)
                    }
                  >
                    <Wrench size={16} />
                    Create corrective work order
                  </button>
                </div>
              )}

              <div className="ca-section-title ca-work-order-title">
                <Clock3 size={17} />
                Corrective work order
              </div>

              {activeRecord.work_order_id ? (
                <>
                  <div className="ca-status-line">
                    <span>Work order status</span>
                    <span className={statusClass(activeRecord.work_order_status)}>
                      {activeRecord.work_order_status}
                    </span>
                  </div>

                  <div className="ca-id-line">
                    Work order ID: {activeRecord.work_order_id}
                  </div>

                  <div className="ca-work-order-meta">
                    <span>
                      Opened: {formatDate(activeRecord.work_order_opened_at)}
                    </span>
                    <span>
                      Downtime: {activeRecord.downtime_minutes ?? 0} minutes
                    </span>
                  </div>

                  {activeRecord.work_order_status === 'OPEN' && (
                    <button
                      className="ca-secondary-button"
                      disabled={saving}
                      onClick={() =>
                        void updateWorkOrder(activeRecord, 'IN_PROGRESS')
                      }
                    >
                      Start work order
                    </button>
                  )}

                  {activeRecord.work_order_status === 'IN_PROGRESS' && (
                    <button
                      className="ca-secondary-button"
                      disabled={saving}
                      onClick={() =>
                        void updateWorkOrder(activeRecord, 'COMPLETED')
                      }
                    >
                      Complete work order
                    </button>
                  )}

                  {activeRecord.work_order_status === 'COMPLETED' && (
                    <div className="ca-locked-note">
                      <CheckCircle2 size={16} />
                      Corrective work order completed.
                    </div>
                  )}
                </>
              ) : (
                <p className="ca-muted">
                  No corrective work order has been created for this case.
                </p>
              )}

              {saving && (
                <div className="ca-saving">
                  <LoaderCircle className="ca-spin" size={15} />
                  Saving changes...
                </div>
              )}
            </aside>
          )}
        </div>
      )}
    </section>
  );
}