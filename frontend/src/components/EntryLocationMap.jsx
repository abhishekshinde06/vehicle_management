import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { ensureLeafletIcons } from '../utils/leafletSetup';

export default function EntryLocationMap({
  pump,
  operatorLat,
  operatorLon,
  accuracyM,
  isLocationVerified,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return undefined;

    ensureLeafletIcons();

    const hasPump =
      pump && typeof pump.latitude === 'number' && typeof pump.longitude === 'number';
    const hasOperator =
      typeof operatorLat === 'number' && typeof operatorLon === 'number';

    if (!hasPump && !hasOperator) return undefined;

    const initialCenter = hasOperator
      ? [operatorLat, operatorLon]
      : [pump.latitude, pump.longitude];

    const map = L.map(containerRef.current, {
      center: initialCenter,
      zoom: 16,
      scrollWheelZoom: false,
    });
    mapRef.current = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    const bounds = [];

    if (hasPump) {
      const pumpLatLng = [pump.latitude, pump.longitude];
      bounds.push(pumpLatLng);

      L.marker(pumpLatLng)
        .addTo(map)
        .bindPopup(
          `<strong>Petrol Pump:</strong> ${pump.name}<br/>Allowed radius: ${pump.radius_meters} m`
        );

      L.circle(pumpLatLng, {
        radius: pump.radius_meters || 100,
        color: '#2563eb',
        fillColor: '#3b82f6',
        fillOpacity: 0.14,
        weight: 2,
      }).addTo(map);
    }

    if (hasOperator) {
      const opLatLng = [operatorLat, operatorLon];
      bounds.push(opLatLng);

      const opColor = isLocationVerified ? '#059669' : '#dc2626';

      L.circleMarker(opLatLng, {
        radius: 8,
        color: '#ffffff',
        weight: 2,
        fillColor: opColor,
        fillOpacity: 1,
      })
        .addTo(map)
        .bindPopup(
          `<strong>Operator GPS</strong><br/>${operatorLat.toFixed(6)}, ${operatorLon.toFixed(6)}${
            accuracyM != null ? `<br/>Accuracy: ±${Math.round(accuracyM)} m` : ''
          }`
        );

      if (typeof accuracyM === 'number' && accuracyM > 0) {
        L.circle(opLatLng, {
          radius: accuracyM,
          color: opColor,
          fillColor: opColor,
          fillOpacity: 0.1,
          dashArray: '4 4',
          weight: 1.5,
        }).addTo(map);
      }
    }

    if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [45, 45], maxZoom: 17 });
    } else if (bounds.length === 1) {
      map.setView(bounds[0], 16);
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [pump, operatorLat, operatorLon, accuracyM, isLocationVerified]);

  return (
    <div className="space-y-2">
      <div
        ref={containerRef}
        className="w-full h-72 sm:h-80 rounded-xl border border-slate-200 z-0"
      />
      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-full bg-blue-600/30 border border-blue-600 inline-block" />
          Petrol pump &amp; allowed geofence radius
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className={`w-3 h-3 rounded-full inline-block ${
              isLocationVerified ? 'bg-emerald-600' : 'bg-red-600'
            }`}
          />
          Submitted operator location &amp; GPS accuracy
        </span>
      </div>
    </div>
  );
}
