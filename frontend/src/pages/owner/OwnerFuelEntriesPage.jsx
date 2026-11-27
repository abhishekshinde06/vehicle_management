import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getFuelEntries } from '../../api/fuelEntries';
import { getVehicles } from '../../api/vehicles';
import { getPetrolPumps } from '../../api/petrolPumps';
import AlertBanner from '../../components/AlertBanner';
import StatusBadge from '../../components/StatusBadge';
import { extractApiError, formatDateTime, formatNumber } from '../../utils/formatters';

const INITIAL_FILTERS = {
  vehicle_id: '',
  petrol_pump_id: '',
  status: '',
  start_date: '',
  end_date: '',
};

export default function OwnerFuelEntriesPage() {
  const [entries, setEntries] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [pumps, setPumps] = useState([]);

  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadReferenceData = useCallback(async () => {
    try {
      const [vehicleList, pumpList] = await Promise.all([
        getVehicles(),
        getPetrolPumps(),
      ]);
      setVehicles(vehicleList);
      setPumps(pumpList);
    } catch {
      // Non-blocking: entries list will report primary errors
    }
  }, []);

  const loadEntries = useCallback(async (activeFilters) => {
    setLoading(true);
    setError('');
    try {
      const data = await getFuelEntries(activeFilters);
      setEntries(data);
    } catch (err) {
      setError(extractApiError(err, 'Failed to load fuel entries.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReferenceData();
    loadEntries(INITIAL_FILTERS);
  }, [loadReferenceData, loadEntries]);

  const handleFilterChange = (field, value) => {
    setFilters((prev) => ({ ...prev, [field]: value }));
  };

  const handleApplyFilters = (e) => {
    e.preventDefault();
    loadEntries(filters);
  };

  const handleResetFilters = () => {
    setFilters(INITIAL_FILTERS);
    loadEntries(INITIAL_FILTERS);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Fuel Entries</h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Monitor fleet fueling logs, GPS verification, mileage, and review status.
          </p>
        </div>
        <button
          type="button"
          onClick={() => loadEntries(filters)}
          disabled={loading}
          className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Filters */}
      <form
        onSubmit={handleApplyFilters}
        className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-xs space-y-4"
      >
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label htmlFor="filter_vehicle" className="block text-xs font-semibold text-slate-600 mb-1">
              Vehicle
            </label>
            <select
              id="filter_vehicle"
              value={filters.vehicle_id}
              onChange={(e) => handleFilterChange('vehicle_id', e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            >
              <option value="">All Vehicles</option>
              {vehicles.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.vehicle_number}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="filter_pump" className="block text-xs font-semibold text-slate-600 mb-1">
              Petrol Pump
            </label>
            <select
              id="filter_pump"
              value={filters.petrol_pump_id}
              onChange={(e) => handleFilterChange('petrol_pump_id', e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            >
              <option value="">All Petrol Pumps</option>
              {pumps.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="filter_status" className="block text-xs font-semibold text-slate-600 mb-1">
              Approval Status
            </label>
            <select
              id="filter_status"
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            >
              <option value="">All Statuses</option>
              <option value="PENDING">PENDING</option>
              <option value="APPROVED">APPROVED</option>
              <option value="REJECTED">REJECTED</option>
            </select>
          </div>

          <div>
            <label htmlFor="filter_start_date" className="block text-xs font-semibold text-slate-600 mb-1">
              Start Date
            </label>
            <input
              id="filter_start_date"
              type="date"
              value={filters.start_date}
              onChange={(e) => handleFilterChange('start_date', e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="filter_end_date" className="block text-xs font-semibold text-slate-600 mb-1">
              End Date
            </label>
            <input
              id="filter_end_date"
              type="date"
              value={filters.end_date}
              onChange={(e) => handleFilterChange('end_date', e.target.value)}
              className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            Apply Filters
          </button>
          <button
            type="button"
            onClick={handleResetFilters}
            disabled={loading}
            className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Reset
          </button>
        </div>
      </form>

      {error && <AlertBanner variant="error">{error}</AlertBanner>}

      {loading ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          Loading fuel entries...
        </div>
      ) : entries.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-600">
          No fuel entries match the selected filters.
        </div>
      ) : (
        <>
          {/* Mobile / Tablet Card View */}
          <div className="space-y-3 lg:hidden">
            {entries.map((entry) => (
              <article
                key={entry.id}
                className="rounded-2xl border border-slate-200 bg-white p-4 shadow-xs space-y-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-base font-bold text-slate-900">
                      {entry.vehicle_number || '—'}
                    </h2>
                    <p className="text-xs text-slate-600">
                      {entry.petrol_pump_name || '—'} &bull; {formatDateTime(entry.created_at)}
                    </p>
                  </div>
                  <StatusBadge status={entry.status} />
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs bg-slate-50 rounded-xl p-3 border border-slate-100">
                  <div>
                    <span className="text-slate-500">Odometer</span>
                    <p className="font-semibold text-slate-900">
                      {formatNumber(entry.previous_odometer)} &rarr; {formatNumber(entry.current_odometer)} km
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-500">Distance</span>
                    <p className="font-semibold text-slate-900">
                      {entry.distance_km != null ? `${formatNumber(entry.distance_km)} km` : '—'}
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-500">Fuel</span>
                    <p className="font-semibold text-slate-900">
                      {formatNumber(entry.fuel_litres)} L ({entry.is_full_tank ? 'Full' : 'Partial'})
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-500">Mileage</span>
                    <p className="font-semibold text-slate-900">
                      {entry.mileage_kmpl != null ? `${formatNumber(entry.mileage_kmpl)} km/L` : '—'}
                    </p>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span
                    className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${
                      entry.is_location_verified
                        ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                        : 'bg-red-50 text-red-800 border-red-200'
                    }`}
                  >
                    {entry.is_location_verified ? 'GPS Verified' : 'GPS Unverified'}
                  </span>

                  <Link
                    to={`/owner/entries/${entry.id}`}
                    className="rounded-lg bg-blue-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-blue-700"
                  >
                    Inspect &amp; Review
                  </Link>
                </div>
              </article>
            ))}
          </div>

          {/* Desktop Table View */}
          <div className="hidden lg:block overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-xs">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-xs font-bold uppercase tracking-wider text-slate-600">
                  <th className="py-3.5 px-4">Vehicle</th>
                  <th className="py-3.5 px-4">Petrol Pump</th>
                  <th className="py-3.5 px-4">Date &amp; Time</th>
                  <th className="py-3.5 px-4">Odometer (Prev &rarr; Curr)</th>
                  <th className="py-3.5 px-4">Distance</th>
                  <th className="py-3.5 px-4">Fuel / Refill</th>
                  <th className="py-3.5 px-4">Mileage</th>
                  <th className="py-3.5 px-4">GPS</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {entries.map((entry) => (
                  <tr key={entry.id} className="hover:bg-slate-50/70">
                    <td className="py-3.5 px-4 font-bold text-slate-900">
                      <div>{entry.vehicle_number || '—'}</div>
                      {entry.operator_name && (
                        <div className="text-xs font-normal text-slate-500">
                          {entry.operator_name}
                        </div>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-slate-800">{entry.petrol_pump_name || '—'}</td>
                    <td className="py-3.5 px-4 text-slate-600 whitespace-nowrap">
                      {formatDateTime(entry.created_at)}
                    </td>
                    <td className="py-3.5 px-4 text-slate-800 whitespace-nowrap">
                      {formatNumber(entry.previous_odometer)} &rarr; {formatNumber(entry.current_odometer)} km
                    </td>
                    <td className="py-3.5 px-4 text-slate-800 whitespace-nowrap">
                      {entry.distance_km != null ? `${formatNumber(entry.distance_km)} km` : '—'}
                    </td>
                    <td className="py-3.5 px-4 text-slate-800 whitespace-nowrap">
                      {formatNumber(entry.fuel_litres)} L &bull;{' '}
                      <span className="text-xs font-semibold text-slate-600">
                        {entry.is_full_tank ? 'Full Tank' : 'Partial'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-semibold text-slate-900 whitespace-nowrap">
                      {entry.mileage_kmpl != null ? `${formatNumber(entry.mileage_kmpl)} km/L` : '—'}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <span
                        className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold border ${
                          entry.is_location_verified
                            ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                            : 'bg-red-50 text-red-800 border-red-200'
                        }`}
                      >
                        {entry.is_location_verified ? 'Verified' : 'Failed'}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      <StatusBadge status={entry.status} />
                    </td>
                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <Link
                        to={`/owner/entries/${entry.id}`}
                        className="inline-flex rounded-lg bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700 hover:bg-blue-100"
                      >
                        Details
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
