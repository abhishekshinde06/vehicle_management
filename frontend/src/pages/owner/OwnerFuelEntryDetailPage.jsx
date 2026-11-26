import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { getFuelEntryById, verifyFuelEntry } from '../../api/fuelEntries';
import { getPetrolPumps } from '../../api/petrolPumps';
import { resolvePhotoUrl } from '../../api/photoUpload';
import AlertBanner from '../../components/AlertBanner';
import EntryLocationMap from '../../components/EntryLocationMap';
import StatusBadge from '../../components/StatusBadge';
import { extractApiError, formatDateTime, formatNumber } from '../../utils/formatters';

function PhotoCard({ photoType, label, photoUrl }) {
  const [imageError, setImageError] = useState(false);
  const resolved = resolvePhotoUrl(photoUrl);

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 overflow-hidden flex flex-col">
      <div className="px-3.5 py-2.5 bg-white border-b border-slate-200 flex items-center justify-between">
        <span className="text-xs font-bold text-slate-900">{label}</span>
        <span className="text-[11px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50 px-2 py-0.5 rounded">
          {photoType}
        </span>
      </div>

      {resolved && !imageError ? (
        <div className="aspect-video bg-slate-900">
          <img
            src={resolved}
            alt={`${label} (${photoType})`}
            onError={() => setImageError(true)}
            className="w-full h-full object-contain"
          />
        </div>
      ) : (
        <div className="aspect-video flex flex-col items-center justify-center p-4 text-center bg-slate-100 text-xs text-slate-600 space-y-1">
          <p className="font-semibold text-slate-700">Photo Unavailable for Preview</p>
          <p>
            {photoUrl
              ? 'Secure photo retrieval is pending or this asset cannot be loaded.'
              : 'No photo URL recorded.'}
          </p>
          {photoUrl && (
            <p className="text-[11px] font-mono text-slate-500 break-all max-w-full">
              Ref: {photoUrl}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default function OwnerFuelEntryDetailPage() {
  const { id } = useParams();

  const [entry, setEntry] = useState(null);
  const [pumps, setPumps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectBox, setShowRejectBox] = useState(false);
  const [reviewSubmitting, setReviewSubmitting] = useState(false);
  const [reviewError, setReviewError] = useState('');
  const [reviewSuccess, setReviewSuccess] = useState('');

  const loadDetail = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const [entryData, pumpList] = await Promise.all([
        getFuelEntryById(id),
        getPetrolPumps().catch(() => []),
      ]);
      setEntry(entryData);
      setPumps(pumpList);
    } catch (err) {
      setError(extractApiError(err, 'Failed to load fuel entry details.'));
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const matchedPump = useMemo(() => {
    if (!entry) return null;
    return pumps.find((p) => p.id === entry.petrol_pump_id) || null;
  }, [entry, pumps]);

  const photoMap = useMemo(() => {
    if (!entry) return {};
    const map = {
      PLATE: entry.photo_plate_url || null,
      ODOMETER: entry.photo_odometer_url || null,
      RECEIPT: entry.photo_receipt_url || null,
    };
    if (Array.isArray(entry.photos)) {
      entry.photos.forEach((p) => {
        if (p?.photo_type && p?.photo_url && !map[p.photo_type]) {
          map[p.photo_type] = p.photo_url;
        }
      });
    }
    return map;
  }, [entry]);

  const handleApprove = async () => {
    if (!entry || entry.status !== 'PENDING' || reviewSubmitting) return;
    setReviewError('');
    setReviewSuccess('');
    setReviewSubmitting(true);

    try {
      await verifyFuelEntry(entry.id, { status: 'APPROVED' });
      await loadDetail();
      setReviewSuccess('Fuel entry approved successfully.');
    } catch (err) {
      setReviewError(extractApiError(err, 'Failed to approve fuel entry.'));
    } finally {
      setReviewSubmitting(false);
    }
  };

  const handleReject = async (e) => {
    e.preventDefault();
    if (!entry || entry.status !== 'PENDING' || reviewSubmitting) return;

    const trimmedReason = rejectionReason.trim();
    if (!trimmedReason) {
      setReviewError('A rejection reason is required when rejecting an entry.');
      return;
    }

    setReviewError('');
    setReviewSuccess('');
    setReviewSubmitting(true);

    try {
      await verifyFuelEntry(entry.id, {
        status: 'REJECTED',
        rejection_reason: trimmedReason,
      });
      setShowRejectBox(false);
      setRejectionReason('');
      await loadDetail();
      setReviewSuccess('Fuel entry rejected and mileage recalculated.');
    } catch (err) {
      setReviewError(extractApiError(err, 'Failed to reject fuel entry.'));
    } finally {
      setReviewSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        Loading fuel entry details...
      </div>
    );
  }

  if (error || !entry) {
    return (
      <div className="space-y-4">
        <Link to="/owner" className="inline-flex text-sm font-semibold text-blue-600 hover:underline">
          &larr; Back to Fuel Entries
        </Link>
        <AlertBanner variant="error">{error || 'Fuel entry not found.'}</AlertBanner>
      </div>
    );
  }

  const isPending = entry.status === 'PENDING';

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-1">
          <Link to="/owner" className="inline-flex text-sm font-semibold text-blue-600 hover:underline">
            &larr; Back to Fuel Entries
          </Link>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">
              {entry.vehicle_number || 'Fuel Entry'}
            </h1>
            <StatusBadge status={entry.status} />
          </div>
          <p className="text-sm text-slate-600">
            Submitted {formatDateTime(entry.created_at)}
            {entry.operator_name ? ` by ${entry.operator_name}` : ''}
          </p>
        </div>
      </div>

      {reviewSuccess && <AlertBanner variant="success">{reviewSuccess}</AlertBanner>}
      {reviewError && <AlertBanner variant="error">{reviewError}</AlertBanner>}

      {/* Review Actions (Pending only) */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Owner Verification</h2>
            <p className="text-sm text-slate-600">
              {isPending
                ? 'Inspect photos, GPS location, and mileage details before approving or rejecting.'
                : `This entry has already been reviewed (${entry.status})${
                    entry.reviewed_at ? ` on ${formatDateTime(entry.reviewed_at)}` : ''
                  }.`}
            </p>
          </div>

          {isPending && (
            <div className="flex flex-wrap items-center gap-2.5">
              <button
                type="button"
                onClick={handleApprove}
                disabled={reviewSubmitting}
                className="rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-emerald-700 disabled:opacity-60"
              >
                {reviewSubmitting ? 'Processing...' : 'Approve Entry'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowRejectBox((prev) => !prev);
                  setReviewError('');
                }}
                disabled={reviewSubmitting}
                className="rounded-xl bg-red-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-60"
              >
                Reject Entry
              </button>
            </div>
          )}
        </div>

        {!isPending && entry.status === 'REJECTED' && entry.rejection_reason && (
          <AlertBanner variant="error" title="Rejection Reason">
            {entry.rejection_reason}
          </AlertBanner>
        )}

        {isPending && showRejectBox && (
          <form onSubmit={handleReject} className="rounded-xl border border-red-200 bg-red-50/70 p-4 space-y-3">
            <label htmlFor="rejection_reason" className="block text-sm font-semibold text-red-950">
              Rejection Reason (Required)
            </label>
            <textarea
              id="rejection_reason"
              rows={3}
              required
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="Explain why this entry is being rejected (e.g., unclear odometer photo, mismatch on receipt)..."
              className="w-full rounded-lg border border-red-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-red-600 focus:outline-none"
            />
            <div className="flex items-center gap-2.5">
              <button
                type="submit"
                disabled={reviewSubmitting}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-bold text-white hover:bg-red-700 disabled:opacity-60"
              >
                {reviewSubmitting ? 'Submitting...' : 'Confirm Rejection'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowRejectBox(false);
                  setRejectionReason('');
                }}
                disabled={reviewSubmitting}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>

      {/* Mileage & Fuel Details */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-lg font-bold text-slate-900">Mileage &amp; Refill Details</h2>
          <span className="text-xs font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-md">
            Automated OCR verification: Pending backend integration
          </span>
        </div>

        <dl className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 text-sm">
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Previous Odometer</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {formatNumber(entry.previous_odometer)} km
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Current Odometer</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {formatNumber(entry.current_odometer)} km
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Distance Travelled</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {entry.distance_km != null ? `${formatNumber(entry.distance_km)} km` : '—'}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Fuel Quantity</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {formatNumber(entry.fuel_litres)} L
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Refill Type</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {entry.is_full_tank ? 'Full Tank' : 'Partial Refill'}
            </dd>
          </div>
          <div className="rounded-xl bg-blue-50 border border-blue-100 p-3">
            <dt className="text-xs text-blue-700">Calculated Mileage</dt>
            <dd className="font-bold text-blue-950 mt-0.5">
              {entry.mileage_kmpl != null ? `${formatNumber(entry.mileage_kmpl)} km/L` : '—'}
            </dd>
          </div>
        </dl>
      </section>

      {/* Photos */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
        <div>
          <h2 className="text-lg font-bold text-slate-900">Captured Evidence Photos</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Photos are displayed when secure photo retrieval is available for the stored references.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <PhotoCard photoType="PLATE" label="Vehicle Number Plate" photoUrl={photoMap.PLATE} />
          <PhotoCard photoType="ODOMETER" label="Dashboard Odometer" photoUrl={photoMap.ODOMETER} />
          <PhotoCard photoType="RECEIPT" label="Pump / Fuel Receipt" photoUrl={photoMap.RECEIPT} />
        </div>
      </section>

      {/* GPS & Map Visualization */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-slate-900">GPS &amp; Petrol Pump Location</h2>
            <p className="text-sm text-slate-600">
              {entry.petrol_pump_name || 'Authorized Petrol Pump'}
              {matchedPump?.address ? ` — ${matchedPump.address}` : ''}
            </p>
          </div>
          <span
            className={`px-3 py-1 rounded-full text-xs font-bold border ${
              entry.is_location_verified
                ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                : 'bg-red-100 text-red-900 border-red-300'
            }`}
          >
            {entry.is_location_verified ? 'Location Verified' : 'Location Not Verified'}
          </span>
        </div>

        <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-sm">
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Submitted Operator GPS</dt>
            <dd className="font-mono text-xs font-semibold text-slate-900 mt-1">
              {entry.latitude != null && entry.longitude != null
                ? `${entry.latitude.toFixed(6)}, ${entry.longitude.toFixed(6)}`
                : 'Not recorded'}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Registered Pump GPS</dt>
            <dd className="font-mono text-xs font-semibold text-slate-900 mt-1">
              {matchedPump
                ? `${matchedPump.latitude.toFixed(6)}, ${matchedPump.longitude.toFixed(6)}`
                : 'Unavailable'}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">Distance from Pump</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {entry.distance_from_pump_m != null
                ? `${formatNumber(entry.distance_from_pump_m)} m`
                : '—'}
              {matchedPump?.radius_meters != null && (
                <span className="text-xs font-normal text-slate-500">
                  {' '}
                  (allowed {formatNumber(matchedPump.radius_meters, 0)} m)
                </span>
              )}
            </dd>
          </div>
          <div className="rounded-xl bg-slate-50 border border-slate-100 p-3">
            <dt className="text-xs text-slate-500">GPS Accuracy</dt>
            <dd className="font-bold text-slate-900 mt-0.5">
              {entry.accuracy_m != null ? `±${formatNumber(entry.accuracy_m, 1)} m` : '—'}
            </dd>
          </div>
        </dl>

        {(matchedPump || (entry.latitude != null && entry.longitude != null)) && (
          <EntryLocationMap
            pump={matchedPump}
            operatorLat={entry.latitude}
            operatorLon={entry.longitude}
            accuracyM={entry.accuracy_m}
            isLocationVerified={entry.is_location_verified}
          />
        )}
      </section>
    </div>
  );
}
