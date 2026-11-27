import { useCallback, useEffect, useState } from 'react';
import { createPetrolPump, getPetrolPumps } from '../../api/petrolPumps';
import { useGeolocation } from '../../hooks/useGeolocation';
import AlertBanner from '../../components/AlertBanner';
import PumpCoordinatePickerMap from '../../components/PumpCoordinatePickerMap';
import { extractApiError, formatDateTime, formatNumber } from '../../utils/formatters';

export default function OwnerPetrolPumpsPage() {
  const [pumps, setPumps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');

  const [name, setName] = useState('');
  const [address, setAddress] = useState('');
  const [latitude, setLatitude] = useState('');
  const [longitude, setLongitude] = useState('');
  const [radiusMeters, setRadiusMeters] = useState('100');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  const { isLocating, error: geoError, getCurrentLocation } = useGeolocation();

  const loadPumps = useCallback(async () => {
    setLoading(true);
    setListError('');
    try {
      const data = await getPetrolPumps();
      setPumps(data);
    } catch (err) {
      setListError(extractApiError(err, 'Failed to load petrol pumps.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPumps();
  }, [loadPumps]);

  const handleCaptureCurrentLocation = async () => {
    setFormError('');
    try {
      const coords = await getCurrentLocation();
      setLatitude(String(Number(coords.latitude.toFixed(6))));
      setLongitude(String(Number(coords.longitude.toFixed(6))));
    } catch {
      // Error surfaced via geoError
    }
  };

  const handleSelectOnMap = useCallback((lat, lon) => {
    setLatitude(String(lat));
    setLongitude(String(lon));
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');

    const trimmedName = name.trim();
    const lat = Number(latitude);
    const lon = Number(longitude);
    const rad = Number(radiusMeters);

    if (!trimmedName) {
      setFormError('Petrol pump name is required.');
      return;
    }
    if (latitude === '' || !Number.isFinite(lat) || lat < -90 || lat > 90) {
      setFormError('Enter a valid latitude between -90 and 90.');
      return;
    }
    if (longitude === '' || !Number.isFinite(lon) || lon < -180 || lon > 180) {
      setFormError('Enter a valid longitude between -180 and 180.');
      return;
    }
    if (!Number.isFinite(rad) || rad <= 0) {
      setFormError('Allowed radius must be a positive number in meters.');
      return;
    }

    setSubmitting(true);
    try {
      const created = await createPetrolPump({
        name: trimmedName,
        address,
        latitude: lat,
        longitude: lon,
        radius_meters: rad,
      });
      setFormSuccess(`Petrol pump "${created.name}" registered successfully.`);
      setName('');
      setAddress('');
      setLatitude('');
      setLongitude('');
      setRadiusMeters('100');
      loadPumps();
    } catch (err) {
      setFormError(extractApiError(err, 'Failed to register petrol pump.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Authorized Petrol Pumps</h1>
        <p className="text-sm text-slate-600 mt-0.5">
          Register authorized fueling stations with GPS coordinates and allowed geofence radius.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4"
        >
          <h2 className="text-lg font-bold text-slate-900">Register Petrol Pump</h2>

          {formError && <AlertBanner variant="error">{formError}</AlertBanner>}
          {geoError && <AlertBanner variant="error">{geoError}</AlertBanner>}
          {formSuccess && <AlertBanner variant="success">{formSuccess}</AlertBanner>}

          <div>
            <label htmlFor="pump_name" className="block text-sm font-semibold text-slate-700 mb-1">
              Pump Name *
            </label>
            <input
              id="pump_name"
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. HP Highway Fuel Stop, Pune"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="pump_address" className="block text-sm font-semibold text-slate-700 mb-1">
              Address (Optional)
            </label>
            <input
              id="pump_address"
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Highway or street address"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-sm font-semibold text-slate-700">GPS Coordinates *</span>
            <button
              type="button"
              onClick={handleCaptureCurrentLocation}
              disabled={isLocating}
              className="rounded-lg bg-slate-100 border border-slate-300 px-3 py-1.5 text-xs font-bold text-slate-800 hover:bg-slate-200 disabled:opacity-60"
            >
              {isLocating ? 'Capturing GPS...' : 'Use Current Location'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label htmlFor="pump_lat" className="block text-xs font-semibold text-slate-600 mb-1">
                Latitude *
              </label>
              <input
                id="pump_lat"
                type="number"
                step="any"
                required
                value={latitude}
                onChange={(e) => setLatitude(e.target.value)}
                placeholder="18.5204"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="pump_lon" className="block text-xs font-semibold text-slate-600 mb-1">
                Longitude *
              </label>
              <input
                id="pump_lon"
                type="number"
                step="any"
                required
                value={longitude}
                onChange={(e) => setLongitude(e.target.value)}
                placeholder="73.8567"
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
              />
            </div>

            <div>
              <label htmlFor="pump_radius" className="block text-xs font-semibold text-slate-600 mb-1">
                Allowed Radius (m) *
              </label>
              <input
                id="pump_radius"
                type="number"
                step="any"
                min="1"
                required
                value={radiusMeters}
                onChange={(e) => setRadiusMeters(e.target.value)}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
              />
            </div>
          </div>

          <PumpCoordinatePickerMap
            latitude={latitude}
            longitude={longitude}
            radiusMeters={radiusMeters}
            onSelectCoordinates={handleSelectOnMap}
          />

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {submitting ? 'Registering...' : 'Register Petrol Pump'}
          </button>
        </form>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Active Petrol Pumps ({pumps.length})
            </h2>
            <button
              type="button"
              onClick={loadPumps}
              disabled={loading}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>

          {listError && <AlertBanner variant="error">{listError}</AlertBanner>}

          {loading ? (
            <p className="text-sm text-slate-500 py-6 text-center">Loading petrol pumps...</p>
          ) : pumps.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">No petrol pumps registered yet.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {pumps.map((pump) => (
                <div key={pump.id} className="py-3.5 space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-slate-900">{pump.name}</p>
                    <span className="text-xs font-semibold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-full">
                      Radius: {formatNumber(pump.radius_meters, 0)} m
                    </span>
                  </div>
                  {pump.address && <p className="text-xs text-slate-600">{pump.address}</p>}
                  <p className="text-xs font-mono text-slate-500">
                    {pump.latitude.toFixed(6)}, {pump.longitude.toFixed(6)} &bull; Added{' '}
                    {formatDateTime(pump.created_at)}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
