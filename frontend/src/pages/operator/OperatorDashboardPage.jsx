import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { getVehicles } from '../../api/vehicles';
import { getPetrolPumps } from '../../api/petrolPumps';
import { createFuelEntry, verifyLocation } from '../../api/fuelEntries';
import { uploadFuelPhoto } from '../../api/photoUpload';
import { useGeolocation } from '../../hooks/useGeolocation';
import AlertBanner from '../../components/AlertBanner';
import CameraCaptureCard from '../../components/CameraCaptureCard';
import StatusBadge from '../../components/StatusBadge';
import { extractApiError, formatDateTime, formatNumber } from '../../utils/formatters';

const PHOTO_SLOTS = [
  {
    photoType: 'PLATE',
    label: '1. Vehicle Number Plate',
    instruction: 'Capture a clear, readable live photo of the vehicle license plate.',
  },
  {
    photoType: 'ODOMETER',
    label: '2. Odometer Reading',
    instruction: 'Capture the vehicle dashboard showing the current odometer reading.',
  },
  {
    photoType: 'RECEIPT',
    label: '3. Pump Display or Receipt',
    instruction: 'Capture the fuel dispenser meter or printed fuel receipt.',
  },
];

export default function OperatorDashboardPage() {
  const [vehicles, setVehicles] = useState([]);
  const [pumps, setPumps] = useState([]);
  const [loadingMaster, setLoadingMaster] = useState(true);
  const [masterError, setMasterError] = useState('');

  const [selectedVehicleId, setSelectedVehicleId] = useState('');
  const [selectedPumpId, setSelectedPumpId] = useState('');

  const {
    position: gpsPosition,
    error: gpsError,
    isLocating,
    getCurrentLocation,
    resetLocation,
  } = useGeolocation();

  const [isVerifyingLocation, setIsVerifyingLocation] = useState(false);
  const [locationVerification, setLocationVerification] = useState(null);
  const [locationVerifyError, setLocationVerifyError] = useState('');
  const [verificationClock, setVerificationClock] = useState(Date.now());

  const [photos, setPhotos] = useState({
    PLATE: null,
    ODOMETER: null,
    RECEIPT: null,
  });
  const photosRef = useRef(photos);
  photosRef.current = photos;

  const [currentOdometer, setCurrentOdometer] = useState('');
  const [fuelLitres, setFuelLitres] = useState('');
  const [isFullTank, setIsFullTank] = useState(true);

  const [formError, setFormError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submittedEntry, setSubmittedEntry] = useState(null);

  const loadMasterData = useCallback(async () => {
    setLoadingMaster(true);
    setMasterError('');
    try {
      const [vehicleList, pumpList] = await Promise.all([
        getVehicles(),
        getPetrolPumps(),
      ]);
      setVehicles(vehicleList);
      setPumps(pumpList);
    } catch (err) {
      setMasterError(extractApiError(err, 'Failed to load vehicles and petrol pumps.'));
    } finally {
      setLoadingMaster(false);
    }
  }, []);

  useEffect(() => {
    loadMasterData();
  }, [loadMasterData]);

  useEffect(() => {
    if (!locationVerification?.expires_at) return undefined;
    const timer = window.setInterval(() => setVerificationClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [locationVerification]);

  useEffect(() => {
    return () => {
      Object.values(photosRef.current).forEach((item) => {
        if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
      });
    };
  }, []);

  const selectedVehicle = useMemo(
    () => vehicles.find((v) => v.id === selectedVehicleId) || null,
    [vehicles, selectedVehicleId]
  );

  const selectedPump = useMemo(
    () => pumps.find((p) => p.id === selectedPumpId) || null,
    [pumps, selectedPumpId]
  );

  const handleSelectPump = (pumpId) => {
    if (pumpId !== selectedPumpId) {
      setSelectedPumpId(pumpId);
      setLocationVerification(null);
      setLocationVerifyError('');
      resetLocation();
    }
  };

  const handleVerifyLocation = async () => {
    setLocationVerifyError('');
    setLocationVerification(null);

    if (!selectedPumpId) {
      setLocationVerifyError('Please select an authorized petrol pump first.');
      return;
    }

    let coords;
    try {
      coords = await getCurrentLocation();
    } catch {
      return;
    }

    setIsVerifyingLocation(true);
    try {
      const result = await verifyLocation({
        petrol_pump_id: selectedPumpId,
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy_m: coords.accuracy_m,
      });
      const expiresIn = Number(result?.expires_in);
      if (
        typeof result?.gps_verification_token !== 'string' ||
        !result.gps_verification_token ||
        !Number.isFinite(expiresIn) ||
        expiresIn <= 0
      ) {
        setLocationVerifyError('The server did not return a valid GPS verification token.');
        return;
      }
      setVerificationClock(Date.now());
      setLocationVerification({
        ...result,
        expires_at: Date.now() + expiresIn * 1000,
      });
    } catch (err) {
      setLocationVerification(null);
      const status = err.response?.status;
      if (status === 403) {
        setLocationVerifyError(
          `${extractApiError(err)} (Measured GPS accuracy: ±${Math.round(coords.accuracy_m)} m)`
        );
      } else {
        setLocationVerifyError(extractApiError(err, 'Location verification failed.'));
      }
    } finally {
      setIsVerifyingLocation(false);
    }
  };

  const handleCapturePhoto = useCallback((photoType, captureData) => {
    setPhotos((prev) => {
      if (prev[photoType]?.previewUrl) {
        URL.revokeObjectURL(prev[photoType].previewUrl);
      }
      return { ...prev, [photoType]: captureData };
    });
  }, []);

  const handleClearPhoto = useCallback((photoType) => {
    setPhotos((prev) => {
      if (prev[photoType]?.previewUrl) {
        URL.revokeObjectURL(prev[photoType].previewUrl);
      }
      return { ...prev, [photoType]: null };
    });
  }, []);

  const allThreePhotosCaptured = Boolean(
    photos.PLATE?.blob && photos.ODOMETER?.blob && photos.RECEIPT?.blob
  );
  const secondsUntilExpiry = locationVerification?.expires_at
    ? Math.max(0, Math.ceil((locationVerification.expires_at - verificationClock) / 1000))
    : 0;
  const isLocationVerified = Boolean(
    locationVerification?.is_location_verified &&
      locationVerification?.gps_verification_token &&
      secondsUntilExpiry > 0
  );

  const validateFuelDetails = () => {
    const odo = Number(currentOdometer);
    const litres = Number(fuelLitres);

    if (!selectedVehicleId) return 'Step 1: Please select a vehicle.';
    if (!selectedPumpId) return 'Step 2: Please select an authorized petrol pump.';
    if (!isLocationVerified) return 'Step 3: Live GPS location must be verified before submitting.';
    if (!allThreePhotosCaptured) {
      return 'Step 4: All three mandatory live photos (PLATE, ODOMETER, RECEIPT) must be captured.';
    }
    if (!currentOdometer.trim() || !Number.isFinite(odo) || odo <= 0) {
      return 'Step 5: Enter a valid positive current odometer reading.';
    }
    if (!fuelLitres.trim() || !Number.isFinite(litres) || litres <= 0) {
      return 'Step 5: Enter a valid positive fuel quantity in litres.';
    }
    return '';
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setSubmitError('');

    if (
      locationVerification?.is_location_verified &&
      (!locationVerification.gps_verification_token || secondsUntilExpiry <= 0)
    ) {
      setLocationVerification(null);
      setLocationVerifyError('Your GPS verification token expired. Verify your live location again.');
      setSubmitError('GPS verification expired. Re-verify your live location before submitting.');
      return;
    }

    const validationMessage = validateFuelDetails();
    if (validationMessage) {
      setFormError(validationMessage);
      return;
    }

    if (isSubmitting) return;
    setIsSubmitting(true);

    try {
      // Capture fresh GPS coordinates right before final submission
      const freshCoords = await getCurrentLocation();

      // Upload all three mandatory photos via modular upload adapter
      const uploadedPhotos = await Promise.all([
        uploadFuelPhoto(photos.PLATE.blob, 'PLATE', {
          petrolPumpId: selectedPumpId,
          gpsVerificationToken: locationVerification.gps_verification_token,
        }),
        uploadFuelPhoto(photos.ODOMETER.blob, 'ODOMETER', {
          petrolPumpId: selectedPumpId,
          gpsVerificationToken: locationVerification.gps_verification_token,
        }),
        uploadFuelPhoto(photos.RECEIPT.blob, 'RECEIPT', {
          petrolPumpId: selectedPumpId,
          gpsVerificationToken: locationVerification.gps_verification_token,
        }),
      ]);

      const payload = {
        vehicle_id: selectedVehicleId,
        petrol_pump_id: selectedPumpId,
        gps_verification_token: locationVerification.gps_verification_token,
        current_odometer: Number(currentOdometer),
        fuel_litres: Number(fuelLitres),
        is_full_tank: Boolean(isFullTank),
        latitude: freshCoords.latitude,
        longitude: freshCoords.longitude,
        accuracy_m: freshCoords.accuracy_m,
        photos: uploadedPhotos,
      };

      const created = await createFuelEntry(payload);
      setSubmittedEntry(created);
      loadMasterData();
    } catch (err) {
      const message = extractApiError(err, err.message || 'Failed to submit fuel entry.');
      if (err.response?.status === 403 && /invalid or expired gps verification/i.test(message)) {
        setLocationVerification(null);
        setLocationVerifyError('Your GPS verification token expired. Verify your live location again.');
        setSubmitError(`${message} Verify your live location again before retrying.`);
      } else {
        setSubmitError(message);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResetWorkflow = () => {
    Object.values(photosRef.current).forEach((item) => {
      if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
    });
    setPhotos({ PLATE: null, ODOMETER: null, RECEIPT: null });
    setSelectedVehicleId('');
    setSelectedPumpId('');
    setLocationVerification(null);
    setLocationVerifyError('');
    resetLocation();
    setCurrentOdometer('');
    setFuelLitres('');
    setIsFullTank(true);
    setFormError('');
    setSubmitError('');
    setSubmittedEntry(null);
  };

  if (submittedEntry) {
    return (
      <div className="max-w-2xl mx-auto bg-white rounded-2xl border border-emerald-200 shadow-xs p-6 sm:p-8 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-bold uppercase tracking-wider text-emerald-700">
              Submission Confirmed
            </p>
            <h2 className="text-2xl font-bold text-slate-900 mt-1">
              Fuel Entry Recorded
            </h2>
          </div>
          <StatusBadge status={submittedEntry.status} />
        </div>

        <AlertBanner variant="success">
          Your fueling record has been submitted and is currently <strong>{submittedEntry.status}</strong> owner review.
        </AlertBanner>

        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4 rounded-xl bg-slate-50 border border-slate-200 p-4 text-sm">
          <div>
            <dt className="text-slate-500">Vehicle</dt>
            <dd className="font-bold text-slate-900">{submittedEntry.vehicle_number}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Petrol Pump</dt>
            <dd className="font-bold text-slate-900">{submittedEntry.petrol_pump_name}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Odometer</dt>
            <dd className="font-semibold text-slate-900">
              {formatNumber(submittedEntry.previous_odometer)} &rarr;{' '}
              {formatNumber(submittedEntry.current_odometer)} km
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Fuel Filled</dt>
            <dd className="font-semibold text-slate-900">
              {formatNumber(submittedEntry.fuel_litres)} L ({submittedEntry.is_full_tank ? 'Full Tank' : 'Partial'})
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Distance Travelled</dt>
            <dd className="font-semibold text-slate-900">
              {submittedEntry.distance_km != null ? `${formatNumber(submittedEntry.distance_km)} km` : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-slate-500">Submitted At</dt>
            <dd className="font-semibold text-slate-900">{formatDateTime(submittedEntry.created_at)}</dd>
          </div>
        </dl>

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            type="button"
            onClick={handleResetWorkflow}
            className="flex-1 rounded-xl bg-blue-600 px-5 py-4 text-base font-bold text-white hover:bg-blue-700"
          >
            Submit Another Fuel Entry
          </button>
          <Link
            to="/operator/history"
            className="flex-1 text-center rounded-xl border border-slate-300 bg-white px-5 py-4 text-base font-bold text-slate-700 hover:bg-slate-50"
          >
            View My History
          </Link>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6 pb-12" noValidate>
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Record Fuel Entry</h2>
        <p className="text-sm text-slate-600 mt-1">
          Follow each step in order at the petrol pump. Camera capture unlocks after live GPS verification.
        </p>
      </div>

      {masterError && (
        <AlertBanner variant="error" title="Could not load fleet data">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>{masterError}</span>
            <button
              type="button"
              onClick={loadMasterData}
              className="rounded-lg bg-red-700 px-3 py-1.5 text-xs font-bold text-white hover:bg-red-800"
            >
              Retry
            </button>
          </div>
        </AlertBanner>
      )}

      {/* Step 1: Select Vehicle */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
              Step 1
            </span>
            <h3 className="text-lg font-bold text-slate-900">Select Vehicle</h3>
          </div>
          {selectedVehicle && (
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full">
              Selected: {selectedVehicle.vehicle_number}
            </span>
          )}
        </div>

        {loadingMaster ? (
          <p className="text-sm text-slate-500 py-4">Loading active vehicles...</p>
        ) : vehicles.length === 0 ? (
          <AlertBanner variant="warning">
            No active vehicles are registered yet. Ask the fleet owner to add a vehicle.
          </AlertBanner>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {vehicles.map((vehicle) => {
              const selected = vehicle.id === selectedVehicleId;
              return (
                <button
                  key={vehicle.id}
                  type="button"
                  onClick={() => setSelectedVehicleId(vehicle.id)}
                  className={`text-left rounded-xl border-2 p-4 transition-colors ${
                    selected
                      ? 'border-blue-600 bg-blue-50/70 ring-2 ring-blue-600/20'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <p className="text-base font-bold text-slate-900">{vehicle.vehicle_number}</p>
                  <p className="text-xs text-slate-600 mt-0.5">
                    {vehicle.model || 'Standard Fleet Vehicle'}
                  </p>
                  <p className="text-xs font-semibold text-slate-700 mt-2">
                    Last Odometer: {formatNumber(vehicle.latest_odometer ?? vehicle.initial_odometer)} km
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Step 2: Select Petrol Pump */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
              Step 2
            </span>
            <h3 className="text-lg font-bold text-slate-900">Select Petrol Pump</h3>
          </div>
          {selectedPump && (
            <span className="text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full">
              Selected: {selectedPump.name}
            </span>
          )}
        </div>

        {loadingMaster ? (
          <p className="text-sm text-slate-500 py-4">Loading authorized petrol pumps...</p>
        ) : pumps.length === 0 ? (
          <AlertBanner variant="warning">
            No authorized petrol pumps are registered yet. Ask the fleet owner to add a pump.
          </AlertBanner>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {pumps.map((pump) => {
              const selected = pump.id === selectedPumpId;
              return (
                <button
                  key={pump.id}
                  type="button"
                  onClick={() => handleSelectPump(pump.id)}
                  className={`text-left rounded-xl border-2 p-4 transition-colors ${
                    selected
                      ? 'border-blue-600 bg-blue-50/70 ring-2 ring-blue-600/20'
                      : 'border-slate-200 bg-white hover:border-slate-300'
                  }`}
                >
                  <p className="text-base font-bold text-slate-900">{pump.name}</p>
                  {pump.address && (
                    <p className="text-xs text-slate-600 mt-0.5">{pump.address}</p>
                  )}
                  <p className="text-xs font-semibold text-slate-700 mt-2">
                    Permitted radius: {formatNumber(pump.radius_meters, 0)} m
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Step 3: Verify Live Location */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
              Step 3
            </span>
            <h3 className="text-lg font-bold text-slate-900">Verify Live Location</h3>
            <p className="text-sm text-slate-600 mt-0.5">
              High-accuracy live GPS is required at the petrol pump to unlock camera capture.
            </p>
          </div>
          {isLocationVerified && (
            <span className="text-xs font-bold text-emerald-800 bg-emerald-100 border border-emerald-300 px-3 py-1 rounded-full">
              GPS Verified
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={handleVerifyLocation}
          disabled={!selectedPumpId || isLocating || isVerifyingLocation}
          className="w-full sm:w-auto rounded-xl bg-blue-600 px-6 py-4 text-base font-bold text-white shadow-xs hover:bg-blue-700 disabled:bg-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed"
        >
          {isLocating
            ? 'Acquiring High-Accuracy GPS...'
            : isVerifyingLocation
              ? 'Verifying with Server...'
              : isLocationVerified
                ? 'Re-verify Live Location'
                : 'Verify Live Location'}
        </button>

        {!selectedPumpId && (
          <p className="text-xs text-slate-500">
            Select a petrol pump in Step 2 to enable live location verification.
          </p>
        )}

        {gpsError && (
          <AlertBanner variant="error" title="GPS Error">
            {gpsError}
          </AlertBanner>
        )}

        {locationVerifyError && (
          <AlertBanner variant="error" title="Location Verification Failed">
            {locationVerifyError}
          </AlertBanner>
        )}

        {isLocationVerified && locationVerification && (
          <AlertBanner variant="success" title="Location Verified">
            <p>{locationVerification.message}</p>
            <p className="mt-1 text-xs">
              Pump: <strong>{locationVerification.petrol_pump_name}</strong> | Distance:{' '}
              <strong>{formatNumber(locationVerification.distance_from_pump_m)} m</strong>
              {gpsPosition?.accuracy_m != null && (
                <>
                  {' '}
                  | GPS Accuracy: <strong>±{Math.round(gpsPosition.accuracy_m)} m</strong>
                </>
              )}
              {' '}
              | Token expires in{' '}
              <strong>
                {Math.floor(secondsUntilExpiry / 60)}:
                {String(secondsUntilExpiry % 60).padStart(2, '0')}
              </strong>
            </p>
          </AlertBanner>
        )}
        {locationVerification?.is_location_verified && !isLocationVerified && (
          <AlertBanner variant="warning" title="GPS Verification Expired">
            Verify your live location again to unlock camera capture and submit this entry.
          </AlertBanner>
        )}
      </section>

      {/* Step 4: Capture Mandatory Photos */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
            Step 4
          </span>
          <h3 className="text-lg font-bold text-slate-900">Capture Mandatory Live Photos</h3>
          <p className="text-sm text-slate-600 mt-0.5">
            Capture all three photos directly with your tablet camera. Gallery uploads are disabled.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {PHOTO_SLOTS.map((slot) => (
            <CameraCaptureCard
              key={slot.photoType}
              photoType={slot.photoType}
              label={slot.label}
              instruction={slot.instruction}
              unlocked={isLocationVerified}
              capture={photos[slot.photoType]}
              onCapture={handleCapturePhoto}
              onClear={handleClearPhoto}
            />
          ))}
        </div>
      </section>

      {/* Step 5: Enter Fuel Details */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-5">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
            Step 5
          </span>
          <h3 className="text-lg font-bold text-slate-900">Enter Fuel Details</h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <div>
            <label
              htmlFor="current_odometer"
              className="block text-sm font-semibold text-slate-700 mb-1.5"
            >
              Current Odometer Reading (km)
            </label>
            <input
              id="current_odometer"
              type="number"
              step="any"
              min="0.01"
              required
              value={currentOdometer}
              onChange={(e) => setCurrentOdometer(e.target.value)}
              placeholder="e.g. 45600"
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-lg font-semibold text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            />
            {selectedVehicle && (
              <p className="text-xs text-slate-500 mt-1.5">
                Last recorded odometer for {selectedVehicle.vehicle_number}:{' '}
                <strong>
                  {formatNumber(selectedVehicle.latest_odometer ?? selectedVehicle.initial_odometer)} km
                </strong>
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="fuel_litres"
              className="block text-sm font-semibold text-slate-700 mb-1.5"
            >
              Fuel Quantity (Litres)
            </label>
            <input
              id="fuel_litres"
              type="number"
              step="any"
              min="0.01"
              required
              value={fuelLitres}
              onChange={(e) => setFuelLitres(e.target.value)}
              placeholder="e.g. 42.5"
              className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3.5 text-lg font-semibold text-slate-900 focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-600/20"
            />
          </div>
        </div>

        <div>
          <span className="block text-sm font-semibold text-slate-700 mb-2">
            Refill Type
          </span>
          <div className="grid grid-cols-2 gap-3 max-w-md">
            <button
              type="button"
              onClick={() => setIsFullTank(true)}
              className={`rounded-xl border-2 px-4 py-3.5 text-base font-bold transition-colors ${
                isFullTank
                  ? 'border-blue-600 bg-blue-50 text-blue-800'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
              }`}
            >
              Full Tank
            </button>
            <button
              type="button"
              onClick={() => setIsFullTank(false)}
              className={`rounded-xl border-2 px-4 py-3.5 text-base font-bold transition-colors ${
                !isFullTank
                  ? 'border-blue-600 bg-blue-50 text-blue-800'
                  : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
              }`}
            >
              Partial Refill
            </button>
          </div>
        </div>
      </section>

      {/* Step 6: Submit Fuel Entry */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow-xs space-y-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
            Step 6
          </span>
          <h3 className="text-lg font-bold text-slate-900">Submit Fuel Entry</h3>
          <p className="text-sm text-slate-600 mt-0.5">
            Fresh GPS coordinates are captured automatically at submission time.
          </p>
        </div>

        {formError && (
          <AlertBanner variant="error" title="Incomplete or Invalid Details">
            {formError}
          </AlertBanner>
        )}

        {submitError && (
          <AlertBanner variant="error" title="Submission Error">
            {submitError}
          </AlertBanner>
        )}

        <button
          type="submit"
          disabled={isSubmitting || isLocating}
          className="w-full rounded-xl bg-emerald-600 px-6 py-4 text-lg font-bold text-white shadow-xs hover:bg-emerald-700 disabled:bg-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? 'Capturing Fresh GPS & Submitting...' : 'Submit Fuel Entry'}
        </button>
      </section>
    </form>
  );
}
