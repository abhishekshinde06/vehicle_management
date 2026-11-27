import { useCallback, useEffect, useState } from 'react';
import { getFuelEntries } from '../../api/fuelEntries';
import AlertBanner from '../../components/AlertBanner';
import StatusBadge from '../../components/StatusBadge';
import { extractApiError, formatDateTime, formatNumber } from '../../utils/formatters';

export default function OperatorHistoryPage() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getFuelEntries();
      setEntries(data);
    } catch (err) {
      setError(extractApiError(err, 'Failed to load your fuel entry history.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">My Fuel Entry History</h2>
          <p className="text-sm text-slate-600 mt-0.5">
            Track your submitted fuel entries and their owner review status.
          </p>
        </div>

        <button
          type="button"
          onClick={loadHistory}
          disabled={loading}
          className="rounded-xl border border-slate-300 bg-white px-5 py-3 text-sm font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {error && <AlertBanner variant="error">{error}</AlertBanner>}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Loading your fuel entries...
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600">
          You have not submitted any fuel entries yet.
        </div>
      ) : (
        <div className="space-y-4">
          {entries.map((entry) => (
            <article
              key={entry.id}
              className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">
                    {entry.vehicle_number || 'Unknown Vehicle'}
                  </h3>
                  <p className="text-sm text-slate-600">
                    {entry.petrol_pump_name || 'Unknown Pump'} &bull;{' '}
                    {formatDateTime(entry.created_at)}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className={`px-2.5 py-1 rounded-full text-xs font-semibold border ${
                      entry.is_location_verified
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                        : 'bg-red-50 text-red-800 border-red-200'
                    }`}
                  >
                    {entry.is_location_verified ? 'GPS Verified' : 'GPS Unverified'}
                  </span>
                  <StatusBadge status={entry.status} />
                </div>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl bg-slate-50 border border-slate-100 p-3.5 text-sm">
                <div>
                  <p className="text-xs text-slate-500">Odometer</p>
                  <p className="font-semibold text-slate-900">
                    {formatNumber(entry.previous_odometer)} &rarr; {formatNumber(entry.current_odometer)} km
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Distance</p>
                  <p className="font-semibold text-slate-900">
                    {entry.distance_km != null ? `${formatNumber(entry.distance_km)} km` : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Fuel Filled</p>
                  <p className="font-semibold text-slate-900">
                    {formatNumber(entry.fuel_litres)} L ({entry.is_full_tank ? 'Full' : 'Partial'})
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Mileage</p>
                  <p className="font-semibold text-slate-900">
                    {entry.mileage_kmpl != null ? `${formatNumber(entry.mileage_kmpl)} km/L` : '—'}
                  </p>
                </div>
              </div>

              {entry.status === 'REJECTED' && entry.rejection_reason && (
                <AlertBanner variant="error" title="Rejection Reason">
                  {entry.rejection_reason}
                </AlertBanner>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
