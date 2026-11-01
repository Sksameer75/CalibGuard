
import { useCallback, useEffect, useState } from 'react';
import {
  Activity, AlertTriangle, ArrowUpRight, BarChart3, Boxes,
  CalendarClock, CheckCircle2, ChevronLeft, ChevronRight,
  CircleHelp, ClipboardCheck, ClipboardList, Database, Factory, Gauge, Menu,
  RefreshCcw, Search, ShieldAlert, ShieldCheck, SlidersHorizontal, X,
} from 'lucide-react';

import AuthorizationSimulator from './AuthorizationSimulator';
import SchedulingWorkspace from './SchedulingWorkspace';
import CorrectiveActions from './CorrectiveActions';

type RecordValue = string | number | boolean | null;
type DataRow = Record<string, RecordValue>;

type Summary = {
  assets: number;
  calibrations: number;
  certificates: number;
  production_uses: number;
  open_alerts: number;
  failed_calibrations: number;
  executed_blocked_uses: number;
  conditional_uses: number;
};

type Paginated = {
  data: DataRow[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    total_pages: number;
  };
};

type View =
  | 'overview'
  | 'assets'
  | 'calibrations'
  | 'alerts'
  | 'production'
  | 'authorization'
  | 'scheduling'
  | 'corrective-actions';

const NAV: { id: View; label: string; icon: typeof Gauge }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3 },
  { id: 'assets', label: 'Asset registry', icon: Boxes },
  { id: 'calibrations', label: 'Calibrations', icon: CalendarClock },
  { id: 'alerts', label: 'Compliance alerts', icon: ShieldAlert },
  { id: 'production', label: 'Production use', icon: Factory },
  { id: 'authorization', label: 'Authorization simulator', icon: ShieldCheck },
  { id: 'scheduling', label: 'Scheduling & work orders', icon: ClipboardList },
  { id: 'corrective-actions', label: 'Corrective actions', icon: ClipboardCheck },
];

const fmt = (v: number | undefined) =>
  typeof v === 'number' ? new Intl.NumberFormat('en-IN').format(v) : '—';

const text = (v: RecordValue | undefined) =>
  v == null ? '—' : String(v);

const date = (v: RecordValue | undefined) => {
  if (!v) return '—';
  const d = new Date(String(v));

  return Number.isNaN(d.getTime())
    ? String(v)
    : d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      });
};

async function getJSON<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path, { signal });

  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(
      `API returned ${res.status}${detail ? ': ' + detail.slice(0, 160) : ''}`
    );
  }

  return res.json() as Promise<T>;
}

function Status({ value }: { value: RecordValue | undefined }) {
  const v = text(value);

  const type = /^(PASS|ACTIVE|ALLOW|ISSUED|CLOSED|RESOLVED)$/i.test(v)
    ? 'good'
    : /^(FAIL|BLOCK|OPEN|CRITICAL|HIGH|REVOKED|RETIRED)$/i.test(v)
      ? 'bad'
      : /CONDITIONAL|MEDIUM|WARNING|PENDING/i.test(v)
        ? 'warn'
        : 'neutral';

  return (
    <span className={`status status-${type}`}>
      <span className="status-dot" />
      {v.replaceAll('_', ' ')}
    </span>
  );
}

function Card({
  label,
  value,
  icon: Icon,
  tone = 'blue',
  note,
}: {
  label: string;
  value: string;
  icon: typeof Gauge;
  tone?: string;
  note?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className={`metric-icon ${tone}`}>
          <Icon size={19} />
        </span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note || 'Live database metric'}</div>
    </div>
  );
}

function Overview({ onNavigate }: { onNavigate: (v: View) => void }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    setError('');

    getJSON<Summary>('/api/dashboard/summary')
      .then(setSummary)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const passed = summary
    ? summary.calibrations - summary.failed_calibrations
    : 0;

  const failPct = summary?.calibrations
    ? (summary.failed_calibrations / summary.calibrations) * 100
    : 0;

  return (
    <>
      <div className="heading-row">
        <div>
          <div className="eyebrow">OPERATIONS INTELLIGENCE</div>
          <h1>Compliance overview</h1>
          <p className="subheading">
            A live view of your calibration and production compliance landscape.
          </p>
        </div>
        <button className="secondary-button" onClick={reload}>
          <RefreshCcw size={16} /> Refresh data
        </button>
      </div>

      {error && (
        <div className="error">
          <AlertTriangle size={18} />
          {error}. Make sure Flask is running on port 5000.
        </div>
      )}

      {loading && !summary ? (
        <div className="loading">Loading live compliance metrics…</div>
      ) : (
        summary && (
          <>
            <div className="metric-grid">
              <Card label="Registered assets" value={fmt(summary.assets)} icon={Boxes} note="Across all plant areas" />
              <Card label="Calibration events" value={fmt(summary.calibrations)} icon={Gauge} tone="purple" note="Recorded test events" />
              <Card label="Open alerts" value={fmt(summary.open_alerts)} icon={ShieldAlert} tone="red" note="Requires review" />
              <Card label="Issued certificates" value={fmt(summary.certificates)} icon={ShieldCheck} tone="green" note="All certificate records" />
            </div>

            <div className="analytics-grid">
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>Calibration performance</h2>
                    <p>Pass and fail distribution</p>
                  </div>
                  <span className="panel-tag">{fmt(summary.calibrations)} events</span>
                </div>

                <div className="donut-layout">
                  <div
                    className="donut"
                    style={{
                      background: `conic-gradient(#ef6372 0 ${failPct}%, #4f8de9 ${failPct}% 100%)`,
                    }}
                  >
                    <div className="donut-hole">
                      <strong>{(100 - failPct).toFixed(1)}%</strong>
                      <small>Pass rate</small>
                    </div>
                  </div>

                  <div className="legend">
                    <div>
                      <i className="legend-color blue-dot" />
                      <span>Passed</span>
                      <strong>{fmt(passed)}</strong>
                    </div>
                    <div>
                      <i className="legend-color red-dot" />
                      <span>Failed</span>
                      <strong>{fmt(summary.failed_calibrations)}</strong>
                    </div>
                    <div className="legend-note">
                      Failed events may require an impact assessment and further review.
                    </div>
                  </div>
                </div>
              </section>

              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>Production authorization</h2>
                    <p>Risk indicators from usage records</p>
                  </div>
                  <Activity size={20} className="muted-icon" />
                </div>

                <div className="risk-list">
                  <div className="risk-row">
                    <div className="risk-icon red"><ShieldAlert size={21} /></div>
                    <div>
                      <span>Executed blocked uses</span>
                      <small>Production activity recorded despite BLOCK decision</small>
                    </div>
                    <strong>{fmt(summary.executed_blocked_uses)}</strong>
                  </div>

                  <div className="risk-row">
                    <div className="risk-icon amber"><CircleHelp size={21} /></div>
                    <div>
                      <span>Conditional authorizations</span>
                      <small>Use permitted under an approved exception</small>
                    </div>
                    <strong>{fmt(summary.conditional_uses)}</strong>
                  </div>

                  <div className="risk-row">
                    <div className="risk-icon blue"><ClipboardList size={21} /></div>
                    <div>
                      <span>Total production uses</span>
                      <small>Full generated event history</small>
                    </div>
                    <strong>{fmt(summary.production_uses)}</strong>
                  </div>
                </div>

                <button className="inline-link" onClick={() => onNavigate('production')}>
                  Investigate production uses <ArrowUpRight size={16} />
                </button>
              </section>
            </div>

            <section className="panel action-panel">
              <div>
                <div className="eyebrow">NEXT ACTIONS</div>
                <h2>Review compliance activity</h2>
                <p>
                  Explore operational records, investigate exceptions, and trace calibration history.
                </p>
              </div>
              <div className="action-buttons">
                <button onClick={() => onNavigate('alerts')}>
                  <AlertTriangle size={17} /> View alerts <ArrowUpRight size={15} />
                </button>
                <button onClick={() => onNavigate('assets')}>
                  <Boxes size={17} /> Explore assets <ArrowUpRight size={15} />
                </button>
                <button onClick={() => onNavigate('scheduling')}>
                  <ClipboardList size={17} /> Manage work orders <ArrowUpRight size={15} />
                </button>
                <button onClick={() => onNavigate('corrective-actions')}>
                  <ClipboardCheck size={17} /> Review corrective actions <ArrowUpRight size={15} />
                </button>
              </div>
            </section>

            <div className="footnote">
              <Database size={15} />
              Metrics reflect imported synthetic data. They are not real industrial measurements or regulatory certifications.
            </div>
          </>
        )
      )}
    </>
  );
}

const CONFIG: Record<
  Exclude<View, 'overview' | 'authorization' | 'scheduling' | 'corrective-actions'>,
  {
    title: string;
    subtitle: string;
    path: string;
    columns: { key: string; label: string; format?: 'date' | 'status' }[];
    filters: { key: string; label: string; options: string[] }[];
  }
> = {
  assets: {
    title: 'Asset registry',
    subtitle: 'Browse and inspect registered industrial instruments.',
    path: '/api/assets',
    columns: [
      { key: 'asset_id', label: 'Asset ID' },
      { key: 'asset_name', label: 'Instrument' },
      { key: 'plant_area', label: 'Plant area' },
      { key: 'serial_number', label: 'Serial number' },
      { key: 'lifecycle_state', label: 'State', format: 'status' },
    ],
    filters: [
      { key: 'state', label: 'All states', options: ['ACTIVE', 'RETIRED', 'INACTIVE', 'QUARANTINED'] },
    ],
  },
  calibrations: {
    title: 'Calibration history',
    subtitle: 'Review recorded measurements, outcomes, and due dates.',
    path: '/api/calibrations',
    columns: [
      { key: 'calibration_id', label: 'Event ID' },
      { key: 'asset_id', label: 'Asset' },
      { key: 'performed_at', label: 'Performed', format: 'date' },
      { key: 'absolute_error', label: 'Absolute error' },
      { key: 'result', label: 'Result', format: 'status' },
      { key: 'recorded_due_at', label: 'Recorded due', format: 'date' },
    ],
    filters: [{ key: 'result', label: 'All results', options: ['PASS', 'FAIL'] }],
  },
  alerts: {
    title: 'Compliance alerts',
    subtitle: 'Inspect alert severity and outstanding compliance issues.',
    path: '/api/alerts',
    columns: [
      { key: 'alert_id', label: 'Alert ID' },
      { key: 'asset_id', label: 'Asset' },
      { key: 'severity', label: 'Severity', format: 'status' },
      { key: 'alert_state', label: 'State', format: 'status' },
      { key: 'created_at', label: 'Created', format: 'date' },
    ],
    filters: [
      { key: 'state', label: 'All states', options: ['OPEN', 'CLOSED'] },
      { key: 'severity', label: 'All severities', options: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] },
    ],
  },
  production: {
    title: 'Production-use monitoring',
    subtitle: 'Trace usage decisions and identify executed blocked events.',
    path: '/api/production-uses',
    columns: [
      { key: 'use_id', label: 'Use ID' },
      { key: 'asset_id', label: 'Asset' },
      { key: 'used_at', label: 'Used at', format: 'date' },
      { key: 'decision', label: 'Decision', format: 'status' },
      { key: 'was_executed', label: 'Executed' },
    ],
    filters: [{ key: 'decision', label: 'All decisions', options: ['ALLOW', 'BLOCK', 'CONDITIONAL_ALLOW'] }],
  },
};

function DataExplorer({
  view,
  onAsset,
}: {
  view: Exclude<View, 'overview' | 'authorization' | 'scheduling' | 'corrective-actions'>;
  onAsset: (id: string) => void;
}) {
  const cfg = CONFIG[view];

  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [result, setResult] = useState<Paginated | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reloadId, setReloadId] = useState(0);

  useEffect(() => {
    setPage(1);
    setFilters({});
    setSearch('');
    setDebouncedSearch('');
    setResult(null);
  }, [view]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setDebouncedSearch(search.trim());
    }, 300);

    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();

    const params = new URLSearchParams({
      page: String(page),
      limit: '20',
    });

    if (debouncedSearch) params.set('q', debouncedSearch);

    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });

    setLoading(true);
    setError('');

    getJSON<Paginated>(
      `${cfg.path}?${params.toString()}`,
      controller.signal
    )
      .then(setResult)
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [cfg.path, page, filters, debouncedSearch, reloadId]);

  return (
    <>
      <div className="heading-row">
        <div>
          <div className="eyebrow">RECORD MANAGEMENT</div>
          <h1>{cfg.title}</h1>
          <p className="subheading">{cfg.subtitle}</p>
        </div>
        <button className="secondary-button" onClick={() => setReloadId((x) => x + 1)}>
          <RefreshCcw size={16} /> Refresh
        </button>
      </div>

      <section className="panel data-panel">
        <div className="table-toolbar">
          <div className="search-field">
            <Search size={17} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={`Search all ${cfg.title.toLowerCase()}…`}
              aria-label={`Search all ${cfg.title}`}
            />
            {search && (
              <button
                className="icon-button"
                onClick={() => setSearch('')}
                aria-label="Clear search"
                type="button"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <div className="filter-group">
            <SlidersHorizontal size={17} />
            {cfg.filters.map((f) => (
              <select
                key={f.key}
                aria-label={f.label}
                value={filters[f.key] || ''}
                onChange={(e) => {
                  setPage(1);
                  setFilters((old) => ({ ...old, [f.key]: e.target.value }));
                }}
              >
                <option value="">{f.label}</option>
                {f.options.map((o) => (
                  <option key={o} value={o}>{o.replaceAll('_', ' ')}</option>
                ))}
              </select>
            ))}
          </div>
        </div>

        <div className="table-caption">
          <span>
            {loading
              ? 'Searching database…'
              : `${fmt(result?.pagination.total)} matching records`}
          </span>
          <span>
            {debouncedSearch
              ? `Global search: "${debouncedSearch}"`
              : 'Search covers all database records'}
          </span>
        </div>

        {error && (
          <div className="error">
            <AlertTriangle size={17} /> {error}
          </div>
        )}

        <div className="table-scroll">
          <table>
            <thead>
              <tr>{cfg.columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
            </thead>
            <tbody>
              {(result?.data ?? []).map((r, i) => (
                <tr key={String(r[cfg.columns[0].key] ?? i)}>
                  {cfg.columns.map((c) => (
                    <td key={c.key}>
                      {c.format === 'status' ? (
                        <Status value={r[c.key]} />
                      ) : c.format === 'date' ? (
                        date(r[c.key])
                      ) : c.key === 'asset_id' && r[c.key] ? (
                        <button className="text-link" onClick={() => onAsset(String(r[c.key]))}>
                          {text(r[c.key])}
                        </button>
                      ) : c.key === 'was_executed' ? (
                        <Status value={r[c.key] === 1 || r[c.key] === true ? 'YES' : 'NO'} />
                      ) : (
                        text(r[c.key])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>

          {!loading && !(result?.data.length) && (
            <div className="empty-state">
              No records found for this search or filter.
            </div>
          )}
        </div>

        <div className="pagination">
          <span>
            Page {result?.pagination.page ?? page} of {result?.pagination.total_pages ?? '—'}
          </span>
          <div>
            <button
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => p - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft size={18} />
            </button>
            <button
              disabled={!result || loading || page >= result.pagination.total_pages}
              onClick={() => setPage((p) => p + 1)}
              aria-label="Next page"
            >
              <ChevronRight size={18} />
            </button>
          </div>
        </div>
      </section>
    </>
  );
}

function AssetDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const [data, setData] = useState<{
    asset: DataRow;
    recent_calibrations: DataRow[];
  } | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    const c = new AbortController();

    getJSON<{
      asset: DataRow;
      recent_calibrations: DataRow[];
    }>(`/api/assets/${encodeURIComponent(id)}`, c.signal)
      .then(setData)
      .catch((e) => {
        if (e.name !== 'AbortError') setError(e.message);
      });

    return () => c.abort();
  }, [id]);

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside
        className="drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Asset details"
      >
        <div className="drawer-header">
          <div>
            <span className="eyebrow">ASSET DETAILS</span>
            <h2>{id}</h2>
          </div>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X size={21} />
          </button>
        </div>

        {error && <div className="error">{error}</div>}
        {!data && !error && <div className="loading">Loading asset…</div>}

        {data && (
          <>
            <h3>{text(data.asset.asset_name)}</h3>
            <div className="detail-grid">
              {Object.entries(data.asset).map(([k, v]) => (
                <div key={k}>
                  <span>{k.replaceAll('_', ' ')}</span>
                  <strong>{k.endsWith('_at') ? date(v) : text(v)}</strong>
                </div>
              ))}
            </div>

            <h3>Recent calibrations</h3>
            <div className="drawer-events">
              {data.recent_calibrations.length ? (
                data.recent_calibrations.map((c, i) => (
                  <div className="drawer-event" key={String(c.calibration_id ?? i)}>
                    <div>
                      <strong>{text(c.calibration_id)}</strong>
                      <small>{date(c.performed_at)}</small>
                    </div>
                    <Status value={c.result} />
                  </div>
                ))
              ) : <p>No calibration records.</p>}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

function App() {
  const [view, setView] = useState<View>('overview');
  const [assetId, setAssetId] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    getJSON<{ status: string }>('/api/health')
      .then((r) => setOnline(r.status === 'ok'))
      .catch(() => setOnline(false));
  }, []);

  const navigate = (v: View) => {
    setView(v);
    setMenu(false);
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menu ? 'sidebar-open' : ''}`}>
        <div className="brand">
          <div className="brand-mark"><ShieldCheck size={25} /></div>
          <div>
            <strong>CalibGuard</strong>
            <span>COMPLIANCE PLATFORM</span>
          </div>
        </div>

        <div className="sidebar-section">WORKSPACE</div>
        <nav>
          {NAV.map((n) => {
            const Icon = n.icon;
            return (
              <button
                key={n.id}
                className={`nav-item ${view === n.id ? 'active' : ''}`}
                onClick={() => navigate(n.id)}
              >
                <Icon size={19} />
                {n.label}
                {view === n.id && <span className="nav-indicator" />}
              </button>
            );
          })}
        </nav>

        <div className="sidebar-bottom">
          <div className="side-info">
            <Database size={18} />
            <div>
              <strong>calibguard_demo</strong>
              <small>MySQL 8.4 · Synthetic</small>
            </div>
          </div>
          <div className="side-version">CALIBGUARD / v1.0</div>
        </div>
      </aside>

      {menu && (
        <button
          className="mobile-backdrop"
          aria-label="Close navigation"
          onClick={() => setMenu(false)}
        />
      )}

      <div className="main-shell">
        <header className="topbar">
          <div className="top-left">
            <button
              className="mobile-menu icon-button"
              onClick={() => setMenu(true)}
              aria-label="Open menu"
            >
              <Menu size={22} />
            </button>
            <span>Workspace</span>
            <ChevronRight size={15} />
            <strong>{NAV.find((n) => n.id === view)?.label}</strong>
          </div>

          <div className="top-right">
            <span className={`connection ${online === true ? 'connected' : online === false ? 'disconnected' : ''}`}>
              <span className="connection-dot" />
              {online === null ? 'Checking API' : online ? 'API connected' : 'API offline'}
            </span>
            <div className="avatar">CG</div>
          </div>
        </header>

        <main className="content">
          {view === 'overview' ? (
            <Overview onNavigate={navigate} />
          ) : view === 'authorization' ? (
            <AuthorizationSimulator />
          ) : view === 'scheduling' ? (
            <SchedulingWorkspace />
          ) : view === 'corrective-actions' ? (
            <CorrectiveActions />
          ) : (
            <DataExplorer view={view} onAsset={setAssetId} />
          )}
        </main>

        <footer className="footer">
          <span>CalibGuard · Synthetic industrial calibration environment</span>
          <span><CheckCircle2 size={14} /> Operational monitoring</span>
        </footer>
      </div>

      {assetId && <AssetDrawer id={assetId} onClose={() => setAssetId(null)} />}
    </div>
  );
}

export default App;
