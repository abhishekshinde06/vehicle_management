import apiClient from './client';

export async function getVehicles() {
  const response = await apiClient.get('/vehicles/');
  return response.data;
}

export async function createVehicle({ vehicle_number, model, initial_odometer }) {
  const payload = {
    vehicle_number: vehicle_number.trim(),
    initial_odometer: Number(initial_odometer) || 0,
    ...(model && model.trim() ? { model: model.trim() } : {}),
  };
  const response = await apiClient.post('/vehicles/', payload);
  return response.data;
}
