import { useCallback, useState } from 'react';

function mapGeolocationError(error) {
  if (!error) {
    return 'Unable to retrieve your current location.';
  }
  switch (error.code) {
    case 1:
      return 'Location permission denied. Please enable location permissions in your browser settings and try again.';
    case 2:
      return 'Location unavailable. Ensure device GPS / Location Services are enabled and try again.';
    case 3:
      return 'Location request timed out. Move to an open area away from metal roofs and try again.';
    default:
      return error.message || 'Failed to capture GPS coordinates.';
  }
}

export function useGeolocation() {
  const [position, setPosition] = useState(null);
  const [error, setError] = useState('');
  const [isLocating, setIsLocating] = useState(false);

  const resetLocation = useCallback(() => {
    setPosition(null);
    setError('');
  }, []);

  const getCurrentLocation = useCallback(() => {
    return new Promise((resolve, reject) => {
      if (typeof navigator === 'undefined' || !navigator.geolocation) {
        const msg = 'Browser Geolocation API is not supported on this device/browser.';
        setError(msg);
        reject(new Error(msg));
        return;
      }

      if (typeof window !== 'undefined' && !window.isSecureContext) {
        const msg =
          'GPS access requires a secure browser context (HTTPS or localhost). Current origin is insecure.';
        setError(msg);
        reject(new Error(msg));
        return;
      }

      setIsLocating(true);
      setError('');

      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords = {
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude,
            accuracy_m: pos.coords.accuracy,
            timestamp: pos.timestamp,
          };
          setPosition(coords);
          setIsLocating(false);
          resolve(coords);
        },
        (geoError) => {
          const message = mapGeolocationError(geoError);
          setError(message);
          setIsLocating(false);
          reject(new Error(message));
        },
        {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: 15000,
        }
      );
    });
  }, []);

  return {
    position,
    error,
    isLocating,
    getCurrentLocation,
    resetLocation,
  };
}
