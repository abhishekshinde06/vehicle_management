import { useEffect, useRef } from 'react';
import L from 'leaflet';
import { ensureLeafletIcons } from '../utils/leafletSetup';

const DEFAULT_CENTER = [20.5937, 78.9629];

export default function PumpCoordinatePickerMap({
  latitude,
  longitude,
  radiusMeters,
  onSelectCoordinates,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerRef = useRef(null);
  const circleRef = useRef(null);
  const onSelectRef = useRef(onSelectCoordinates);

  onSelectRef.current = onSelectCoordinates;

  useEffect(() => {
    if (!containerRef.current) return undefined;
    ensureLeafletIcons();

    const parsedLat = Number(latitude);
    const parsedLon = Number(longitude);
    const hasCoords =
      Number.isFinite(parsedLat) &&
      Number.isFinite(parsedLon) &&
      latitude !== '' &&
      longitude !== '';

    const map = L.map(containerRef.current, {
      center: hasCoords ? [parsedLat, parsedLon] : DEFAULT_CENTER,
      zoom: hasCoords ? 16 : 5,
    });
    mapRef.current = map;

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);

    map.on('click', (event) => {
      const { lat, lng } = event.latlng;
      onSelectRef.current(Number(lat.toFixed(6)), Number(lng.toFixed(6)));
    });

    return () => {
      map.remove();
      mapRef.current = null;
      markerRef.current = null;
      circleRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const parsedLat = Number(latitude);
    const parsedLon = Number(longitude);
    const parsedRadius = Number(radiusMeters) || 100;

    const hasValidCoords =
      latitude !== '' &&
      longitude !== '' &&
      Number.isFinite(parsedLat) &&
      Number.isFinite(parsedLon) &&
      parsedLat >= -90 &&
      parsedLat <= 90 &&
      parsedLon >= -180 &&
      parsedLon <= 180;

    if (!hasValidCoords) {
      if (markerRef.current) {
        markerRef.current.remove();
        markerRef.current = null;
      }
      if (circleRef.current) {
        circleRef.current.remove();
        circleRef.current = null;
      }
      return;
    }

    const latLng = [parsedLat, parsedLon];

    if (!markerRef.current) {
      markerRef.current = L.marker(latLng).addTo(map);
    } else {
      markerRef.current.setLatLng(latLng);
    }

    if (!circleRef.current) {
      circleRef.current = L.circle(latLng, {
        radius: parsedRadius,
        color: '#2563eb',
        fillColor: '#3b82f6',
        fillOpacity: 0.15,
        weight: 2,
      }).addTo(map);
    } else {
      circleRef.current.setLatLng(latLng);
      circleRef.current.setRadius(parsedRadius);
    }

    map.setView(latLng, Math.max(map.getZoom(), 15));
  }, [latitude, longitude, radiusMeters]);

  return (
    <div className="space-y-1.5">
      <div
        ref={containerRef}
        className="w-full h-64 rounded-xl border border-slate-200 z-0"
      />
      <p className="text-xs text-slate-500">
        Click anywhere on the map to set the petrol pump latitude and longitude.
      </p>
    </div>
  );
}
