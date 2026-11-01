
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  Clock3,
  RefreshCcw,
  Search,
  ShieldAlert,
  Wrench,
} from 'lucide-react';


type Row = Record<string, unknown>;
type ApiList = { data?: Row[]; pagination?: { total?: number } };

const asText = (v: unknown, fallback = '—') =>
  v === null || v === undefined || v === '' ? fallback : String(v);

const first = (row: Row, keys: string[]) => {
  for (const key of keys) {
    if (row[key] !== undefined && row[key] !== null && row[key] !== '') {
      return row[key];
    }
  }
  return undefined;
};

const formatDate = (value: unknown) => {
  if (!value) return '—';

  const raw = String(value);
  const d = new Date(raw.includes('T') ? raw : raw.replace(' ', 'T'));

  return Number.isNaN(d.getTime())
    ? raw
    : d.toLocaleString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
};

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
  });

  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(
      asText(
        (body as Row).error || (body as Row).message,
        `Request failed (${response.status})`
      )
    );
  }

  return body as T;
}

function Pill({ value }: { value: unknown }) {
  const v = asText(value, 'UNKNOWN').toUpperCase();

  const tone = /OVERDUE|FAIL|CANCEL|BLOCK|CRITICAL/.test(v)
    ? 'bad'
    : /DUE_SOON|IN_PROGRESS|CONDITIONAL|WARNING|NEVER/.test(v)
      ? 'warn'
      : /UPCOMING|PASS|COMPLETED|ALLOW|ACTIVE/.test(v)
        ? 'good'
        : 'neutral';

  return <span className={`cg-pill ${tone}`}>{v.replaceAll('_', ' ')}</span>;
}

export default function SchedulingWorkspace() {
  const [schedule, setSchedule] = useState<Row[]>([]);
  const [orders, setOrders] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [days, setDays] = useState('90');
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [busyId, setBusyId] = useState('');
  const [notice, setNotice] = useState('');
  const [completion, setCompletion] = useState<Row | null>(null);
  const [downtime, setDowntime] = useState('0');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    setNotice('');

    try {
      const [s, w] = await Promise.all([
        request<ApiList>(
          `/api/scheduling?days=${encodeURIComponent(days)}`
        ),
        request<ApiList>('/api/work-orders'),
      ]);

      setSchedule(Array.isArray(s.data) ? s.data : []);
      setOrders(Array.isArray(w.data) ? w.data : []);
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Unable to load scheduling data'
      );
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    void load();
  }, [load]);

  const visibleSchedule = useMemo(
    () =>
      schedule.filter((row) => {
        const state = asText(
          first(row, [
            'schedule_state',
            'schedule_status',
            'status',
            'state',
          ]),
          ''
        ).toUpperCase();

        const matchesFilter =
          filter === 'ALL' || state.includes(filter);

        const haystack = [
          first(row, ['asset_id']),
          first(row, ['asset_name']),
          first(row, ['plant_area']),
          first(row, ['calibration_id']),
          first(row, ['instrument_type']),
        ]
          .map((v) => asText(v, ''))
          .join(' ')
          .toLowerCase();

        return (
          matchesFilter &&
          (!search || haystack.includes(search.toLowerCase()))
        );
      }),
    [schedule, filter, search]
  );

  const counts = useMemo(
    () => ({
      overdue: schedule.filter((r) =>
        /OVERDUE/.test(
          asText(
            first(r, [
              'schedule_state',
              'schedule_status',
              'status',
              'state',
            ]),
            ''
          ).toUpperCase()
        )
      ).length,

      soon: schedule.filter((r) =>
        /DUE_SOON/.test(
          asText(
            first(r, [
              'schedule_state',
              'schedule_status',
              'status',
              'state',
            ]),
            ''
          ).toUpperCase()
        )
      ).length,

      never: schedule.filter((r) =>
        /NEVER/.test(
          asText(
            first(r, [
              'schedule_state',
              'schedule_status',
              'status',
              'state',
            ]),
            ''
          ).toUpperCase()
        )
      ).length,
    }),
    [schedule]
  );

  const createOrder = async (row: Row) => {
    const assetId = asText(first(row, ['asset_id']), '');

    if (!assetId) return;

    setBusyId(assetId);
    setError('');
    setNotice('');

    try {
      await request('/api/scheduling/work-orders', {
        method: 'POST',
        body: JSON.stringify({ asset_id: assetId }),
      });

      setNotice(`Work order created for ${assetId}.`);
      await load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Could not create work order'
      );
    } finally {
      setBusyId('');
    }
  };

  const updateStatus = async (
    row: Row,
    status: string,
    downtimeMinutes?: number
  ) => {
    const id = asText(first(row, ['work_order_id']), '');

    if (!id) return;

    setBusyId(id);
    setError('');
    setNotice('');

    try {
      await request(
        `/api/work-orders/${encodeURIComponent(id)}/status`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            status,
            ...(downtimeMinutes === undefined
              ? {}
              : { downtime_minutes: downtimeMinutes }),
          }),
        }
      );

      setNotice(
        `${id} updated to ${status.replaceAll('_', ' ')}.`
      );

      setCompletion(null);
      await load();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : 'Could not update work order'
      );
    } finally {
      setBusyId('');
    }
  };

  const startCompletion = (row: Row) => {
    setCompletion(row);
    setDowntime('0');
  };

  return (
    <div className="cg-scheduling">
      <div className="heading-row">
        <div>
          <div className="eyebrow">OPERATIONAL CONTROL</div>
          <h1>Scheduling &amp; work orders</h1>
          <p className="subheading">
            Identify calibration obligations and manage maintenance execution.
          </p>
        </div>

        <button
          className="secondary-button"
          onClick={() => void load()}
          disabled={loading}
        >
          <RefreshCcw size={16} /> Refresh
        </button>
      </div>

      {error && (
        <div className="error">
          <AlertTriangle size={17} />
          {error}
        </div>
      )}

      {notice && (
        <div className="cg-notice">
          <CheckCircle2 size={17} />
          {notice}
        </div>
      )}

      <div className="cg-stat-grid">
        <div className="cg-stat">
          <span><ShieldAlert size={17} /> Overdue</span>
          <strong>{counts.overdue}</strong>
          <small>Past calculated due date</small>
        </div>

        <div className="cg-stat">
          <span><Clock3 size={17} /> Due soon</span>
          <strong>{counts.soon}</strong>
          <small>Requires scheduling attention</small>
        </div>

        <div className="cg-stat">
          <span><CalendarClock size={17} /> Never calibrated</span>
          <strong>{counts.never}</strong>
          <small>No prior calibration event</small>
        </div>

        <div className="cg-stat">
          <span><ClipboardList size={17} /> Work orders</span>
          <strong>{orders.length}</strong>
          <small>Returned work-order records</small>
        </div>
      </div>

      <section className="panel cg-section">
        <div className="cg-section-head">
          <div>
            <h2>Calibration schedule</h2>
            <p>
              Assets due now or within the selected planning horizon.
            </p>
          </div>

          <div className="cg-controls">
            <label>
              Horizon
              <select
                value={days}
                onChange={(e) => setDays(e.target.value)}
              >
                <option value="30">30 days</option>
                <option value="60">60 days</option>
                <option value="90">90 days</option>
                <option value="180">180 days</option>
                <option value="365">365 days</option>
              </select>
            </label>
          </div>
        </div>

        <div className="cg-toolbar">
          <div className="search-field">
            <Search size={16} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search asset, area or calibration ID"
            />
          </div>

          <div className="cg-filter">
            <ChevronDown size={16} />
            <select
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="ALL">All schedule states</option>
              <option value="OVERDUE">Overdue</option>
              <option value="DUE_SOON">Due soon</option>
              <option value="UPCOMING">Upcoming</option>
              <option value="NEVER">Never calibrated</option>
              <option value="FAILED">Failed calibration</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="loading">
            Loading schedule and work orders…
          </div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Asset</th>
                  <th>Last calibration</th>
                  <th>Due date</th>
                  <th>Schedule state</th>
                  <th>Active work order</th>
                  <th>Action</th>
                </tr>
              </thead>

              <tbody>
                {visibleSchedule.map((r, i) => {
                  const id = asText(
                    first(r, ['asset_id']),
                    `row-${i}`
                  );

                  const state = first(r, [
                    'schedule_state',
                    'schedule_status',
                    'status',
                    'state',
                  ]);

                  const activeOrder = first(r, [
                    'active_work_order_id',
                  ]);

                  const due = first(r, [
                    'due_at',
                    'calculated_due_at',
                    'due_date',
                  ]);

                  const last = first(r, [
                    'performed_at',
                    'last_calibration_at',
                    'last_performed_at',
                  ]);

                  const hasOrder = Boolean(activeOrder);

                  return (
                    <tr key={id}>
                      <td>
                        <strong>{id}</strong>
                        <small className="cg-cell-sub">
                          {asText(
                            first(r, [
                              'asset_name',
                              'instrument_name',
                            ])
                          )}
                        </small>
                      </td>

                      <td>{formatDate(last)}</td>
                      <td>{formatDate(due)}</td>
                      <td><Pill value={state} /></td>
                      <td>{hasOrder ? asText(activeOrder) : '—'}</td>

                      <td>
                        <button
                          className="cg-action"
                          disabled={hasOrder || busyId === id}
                          onClick={() => void createOrder(r)}
                        >
                          <Wrench size={14} />
                          {busyId === id
                            ? 'Creating…'
                            : hasOrder
                              ? 'Already assigned'
                              : 'Create work order'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {!visibleSchedule.length && (
              <div className="empty-state">
                No schedule records match this filter.
              </div>
            )}
          </div>
        )}

        <div className="cg-table-foot">
          Showing {visibleSchedule.length} of {schedule.length} returned
          schedule records. Schedule is generated from the backend's
          current planning rules.
        </div>
      </section>

      <section className="panel cg-section">
        <div className="cg-section-head">
          <div>
            <h2>Work-order register</h2>
            <p>
              Track scheduled calibration and corrective work through completion.
            </p>
          </div>
          <span className="panel-tag">{orders.length} records</span>
        </div>

        {loading ? (
          <div className="loading">Loading work orders…</div>
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Work order</th>
                  <th>Asset(s)</th>
                  <th>Type</th>
                  <th>Opened</th>
                  <th>Status</th>
                  <th>Downtime</th>
                  <th>Next action</th>
                </tr>
              </thead>

              <tbody>
                {orders.map((r, i) => {
                  const id = asText(
                    first(r, ['work_order_id']),
                    `wo-${i}`
                  );

                  const status = asText(
                    first(r, ['status']),
                    ''
                  ).toUpperCase();

                  const assetNames = first(r, [
                    'asset_names',
                    'asset_ids',
                  ]);

                  return (
                    <tr key={id}>
                      <td><strong>{id}</strong></td>
                      <td>
                        <span className="cg-asset-list">
                          {asText(assetNames)}
                        </span>
                      </td>
                      <td>
                        {asText(first(r, ['work_type'])).replaceAll('_', ' ')}
                      </td>
                      <td>
                        {formatDate(first(r, ['opened_at']))}
                      </td>
                      <td><Pill value={status} /></td>
                      <td>
                        {asText(first(r, ['downtime_minutes']), '0')} min
                      </td>

                      <td>
                        {status === 'OPEN' ? (
                          <button
                            className="cg-action"
                            disabled={busyId === id}
                            onClick={() =>
                              void updateStatus(r, 'IN_PROGRESS')
                            }
                          >
                            Start work
                          </button>
                        ) : status === 'IN_PROGRESS' ? (
                          <button
                            className="cg-action complete"
                            disabled={busyId === id}
                            onClick={() => startCompletion(r)}
                          >
                            Complete
                          </button>
                        ) : (
                          <span className="cg-muted">No action</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {!orders.length && (
              <div className="empty-state">
                No work orders returned.
              </div>
            )}
          </div>
        )}
      </section>

      {completion && (
        <div
          className="cg-modal-backdrop"
          onClick={() => setCompletion(null)}
        >
          <section
            className="cg-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Complete work order"
          >
            <div className="cg-section-head">
              <div>
                <h2>Complete work order</h2>
                <p>
                  {asText(first(completion, ['work_order_id']))}
                </p>
              </div>

              <button
                className="cg-close"
                onClick={() => setCompletion(null)}
              >
                ×
              </button>
            </div>

            <label className="cg-modal-label">
              Recorded downtime (minutes)
              <input
                type="number"
                min="0"
                step="1"
                value={downtime}
                onChange={(e) => setDowntime(e.target.value)}
              />
            </label>

            <p className="cg-modal-help">
              Enter the actual downtime associated with this work order.
              Use 0 only if no downtime occurred.
            </p>

            <div className="cg-modal-actions">
              <button
                className="secondary-button"
                onClick={() => setCompletion(null)}
              >
                Cancel
              </button>

              <button
                className="cg-primary"
                disabled={!/^\d+$/.test(downtime) || busyId !== ''}
                onClick={() =>
                  void updateStatus(
                    completion,
                    'COMPLETED',
                    Number(downtime)
                  )
                }
              >
                Confirm completion
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
