import apiClient from './client';

export async function getPetrolPumps() {
  const response = await apiClient.get('/petrol-pumps/');
  return response.data;
}

export async function createPetrolPump({
  name,
  address,
  latitude,
  longitude,
  radius_meters,
}) {
  const payload = {
    name: name.trim(),
    latitude: Number(latitude),
    longitude: Number(longitude),
    radius_meters: Number(radius_meters) || 100,
    ...(address && address.trim() ? { address: address.trim() } : {}),
  };
  const response = await apiClient.post('/petrol-pumps/', payload);
  return response.data;
}
