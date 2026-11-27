import { useCallback, useEffect, useState } from 'react';
import { createVehicle, getVehicles } from '../../api/vehicles';
import AlertBanner from '../../components/AlertBanner';
import { extractApiError, formatDateTime, formatNumber } from '../../utils/formatters';

export default function OwnerVehiclesPage() {
  const [vehicles, setVehicles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');

  const [vehicleNumber, setVehicleNumber] = useState('');
  const [model, setModel] = useState('');
  const [initialOdometer, setInitialOdometer] = useState('0');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  const loadVehicles = useCallback(async () => {
    setLoading(true);
    setListError('');
    try {
      const data = await getVehicles();
      setVehicles(data);
    } catch (err) {
      setListError(extractApiError(err, 'Failed to load fleet vehicles.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadVehicles();
  }, [loadVehicles]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');

    const trimmedNumber = vehicleNumber.trim();
    const odoNum = Number(initialOdometer);

    if (!trimmedNumber) {
      setFormError('Vehicle number is required.');
      return;
    }
    if (!Number.isFinite(odoNum) || odoNum < 0) {
      setFormError('Initial odometer must be 0 or a positive number.');
      return;
    }

    setSubmitting(true);
    try {
      const created = await createVehicle({
        vehicle_number: trimmedNumber,
        model,
        initial_odometer: odoNum,
      });
      setFormSuccess(`Vehicle ${created.vehicle_number} registered successfully.`);
      setVehicleNumber('');
      setModel('');
      setInitialOdometer('0');
      loadVehicles();
    } catch (err) {
      setFormError(extractApiError(err, 'Failed to register vehicle.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Fleet Vehicles</h1>
        <p className="text-sm text-slate-600 mt-0.5">
          View active registered vehicles and add new vehicles to the fleet.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4"
        >
          <h2 className="text-lg font-bold text-slate-900">Register New Vehicle</h2>

          {formError && <AlertBanner variant="error">{formError}</AlertBanner>}
          {formSuccess && <AlertBanner variant="success">{formSuccess}</AlertBanner>}

          <div>
            <label htmlFor="vehicle_number" className="block text-sm font-semibold text-slate-700 mb-1">
              Vehicle Number *
            </label>
            <input
              id="vehicle_number"
              type="text"
              required
              value={vehicleNumber}
              onChange={(e) => setVehicleNumber(e.target.value)}
              placeholder="e.g. MH-12-AB-1234"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="vehicle_model" className="block text-sm font-semibold text-slate-700 mb-1">
              Model (Optional)
            </label>
            <input
              id="vehicle_model"
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="e.g. Tata Prima 4028.S"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="initial_odometer" className="block text-sm font-semibold text-slate-700 mb-1">
              Initial Odometer (km)
            </label>
            <input
              id="initial_odometer"
              type="number"
              step="any"
              min="0"
              required
              value={initialOdometer}
              onChange={(e) => setInitialOdometer(e.target.value)}
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {submitting ? 'Registering...' : 'Add Vehicle'}
          </button>
        </form>

        <div className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Active Vehicles ({vehicles.length})
            </h2>
            <button
              type="button"
              onClick={loadVehicles}
              disabled={loading}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>

          {listError && <AlertBanner variant="error">{listError}</AlertBanner>}

          {loading ? (
            <p className="text-sm text-slate-500 py-6 text-center">Loading vehicles...</p>
          ) : vehicles.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">No vehicles registered yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {vehicles.map((v) => (
                <div
                  key={v.id}
                  className="py-3.5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2"
                >
                  <div>
                    <p className="font-bold text-slate-900">{v.vehicle_number}</p>
                    <p className="text-xs text-slate-500">
                      {v.model || 'Standard Vehicle'} &bull; Added {formatDateTime(v.created_at)}
                    </p>
                  </div>
                  <div className="text-sm sm:text-right">
                    <p className="font-semibold text-slate-900">
                      Latest: {formatNumber(v.latest_odometer ?? v.initial_odometer)} km
                    </p>
                    <p className="text-xs text-slate-500">
                      Initial: {formatNumber(v.initial_odometer)} km
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
