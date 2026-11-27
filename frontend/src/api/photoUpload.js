import apiClient, { getBackendOrigin } from './client';

export async function uploadFuelPhoto(
  blob,
  photoType,
  { petrolPumpId, gpsVerificationToken }
) {
  if (!blob) {
    throw new Error(`Missing captured image for ${photoType}.`);
  }
  if (!petrolPumpId || !gpsVerificationToken) {
    throw new Error('Verify your live GPS location before uploading photos.');
  }

  const formData = new FormData();
  const filename = `${photoType.toLowerCase()}_${Date.now()}.jpg`;
  formData.append('file', blob, filename);
  formData.append('photo_type', photoType);
  formData.append('petrol_pump_id', petrolPumpId);
  formData.append('gps_verification_token', gpsVerificationToken);

  const response = await apiClient.post('/fuel-entries/upload-photo', formData);

  const { photo_id: photoId, photo_type: uploadedType } = response.data || {};
  if (!photoId || uploadedType !== photoType) {
    throw new Error(`Photo upload did not return a valid ${photoType} photo reference.`);
  }

  return {
    photo_type: photoType,
    photo_id: photoId,
  };
}

export function resolvePhotoUrl(photoUrl) {
  if (!photoUrl || typeof photoUrl !== 'string' || !photoUrl.trim()) {
    return null;
  }
  const trimmed = photoUrl.trim();
  if (/^https?:\/\//i.test(trimmed)) {
    return trimmed;
  }
  if (trimmed.startsWith('/')) {
    return `${getBackendOrigin()}${trimmed}`;
  }
  return null;
}

export async function loadFuelPhoto(photoUrl) {
  const resolvedUrl = resolvePhotoUrl(photoUrl);
  if (!resolvedUrl) return null;

  const resolved = new URL(resolvedUrl);
  const apiBase = new URL(apiClient.defaults.baseURL);
  const apiPath = apiBase.pathname.replace(/\/+$/, '');
  const photoPathPrefix = `${apiPath}/fuel-entries/photos/`;

  if (
    resolved.origin !== getBackendOrigin() ||
    !resolved.pathname.startsWith(photoPathPrefix)
  ) {
    return resolvedUrl;
  }

  const responsePath = resolved.pathname.slice(apiPath.length) + resolved.search;
  const response = await apiClient.get(responsePath, { responseType: 'blob' });
  return URL.createObjectURL(response.data);
}
