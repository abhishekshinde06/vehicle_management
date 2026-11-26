import apiClient, { getBackendOrigin } from './client';

/**
 * Modular Photo Upload & Secure Retrieval Adapter
 * ------------------------------------------------
 * Pending backend dependency:
 * The production secure photo upload module (e.g. authenticated S3 presigned
 * uploads and secure photo retrieval URLs) is still under development.
 *
 * By default, `isSecurePhotoUploadAvailable()` returns `false` so that:
 * - No fake photo URLs are ever generated.
 * - Final fuel entry submission is blocked with a clear dependency message.
 *
 * For local development testing against the temporary multipart endpoint
 * `POST /api/fuel-entries/upload-photo`, set `VITE_ENABLE_DEV_PHOTO_UPLOAD=true`.
 */

export const PHOTO_UPLOAD_DEPENDENCY_NOTICE =
  'Secure photo upload module is still under development on the backend. Live camera photos can be captured, previewed, and retaken locally, but final fuel entry submission is disabled until secure photo upload is enabled.';

export function isSecurePhotoUploadAvailable() {
  return import.meta.env.VITE_ENABLE_DEV_PHOTO_UPLOAD === 'true';
}

export async function uploadFuelPhoto(blob, photoType) {
  if (!isSecurePhotoUploadAvailable()) {
    const err = new Error(PHOTO_UPLOAD_DEPENDENCY_NOTICE);
    err.code = 'SECURE_PHOTO_UPLOAD_UNAVAILABLE';
    throw err;
  }

  if (!blob) {
    throw new Error(`Missing captured image for ${photoType}.`);
  }

  const formData = new FormData();
  const filename = `${photoType.toLowerCase()}_${Date.now()}.jpg`;
  formData.append('file', blob, filename);

  const response = await apiClient.post('/fuel-entries/upload-photo', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  const photoUrl = response.data?.photo_url;
  if (!photoUrl || typeof photoUrl !== 'string' || !photoUrl.trim()) {
    throw new Error('Photo upload did not return a valid photo URL.');
  }

  return {
    photo_type: photoType,
    photo_url: photoUrl.trim(),
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
