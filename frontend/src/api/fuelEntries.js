import apiClient from './client';

export async function verifyLocation({ petrol_pump_id, latitude, longitude, accuracy_m }) {
  const response = await apiClient.post('/fuel-entries/verify-location', {
    petrol_pump_id,
    latitude,
    longitude,
    accuracy_m,
  });
  return response.data;
}

export async function createFuelEntry(payload) {
  const response = await apiClient.post('/fuel-entries/', payload);
  return response.data;
}

export async function getFuelEntries(filters = {}) {
  const params = {};
  if (filters.vehicle_id) params.vehicle_id = filters.vehicle_id;
  if (filters.petrol_pump_id) params.petrol_pump_id = filters.petrol_pump_id;
  if (filters.status) params.status = filters.status;
  if (filters.start_date) params.start_date = filters.start_date;
  if (filters.end_date) params.end_date = filters.end_date;

  const response = await apiClient.get('/fuel-entries/', { params });
  return response.data;
}

export async function getFuelEntryById(id) {
  const response = await apiClient.get(`/fuel-entries/${id}`);
  return response.data;
}

export async function verifyFuelEntry(id, { status, rejection_reason }) {
  const payload =
    status === 'REJECTED'
      ? { status: 'REJECTED', rejection_reason: rejection_reason.trim() }
      : { status: 'APPROVED' };

  const response = await apiClient.patch(`/fuel-entries/${id}/verify`, payload);
  return response.data;
}
