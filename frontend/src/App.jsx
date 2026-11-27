import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import ProtectedRoute, { getHomePathForRole } from './components/ProtectedRoute';
import OperatorLayout from './layouts/OperatorLayout';
import OwnerLayout from './layouts/OwnerLayout';
import LoginPage from './pages/LoginPage';
import OperatorDashboardPage from './pages/operator/OperatorDashboardPage';
import OperatorHistoryPage from './pages/operator/OperatorHistoryPage';
import OwnerFuelEntriesPage from './pages/owner/OwnerFuelEntriesPage';
import OwnerFuelEntryDetailPage from './pages/owner/OwnerFuelEntryDetailPage';
import OwnerVehiclesPage from './pages/owner/OwnerVehiclesPage';
import OwnerPetrolPumpsPage from './pages/owner/OwnerPetrolPumpsPage';
import OwnerOperatorsPage from './pages/owner/OwnerOperatorsPage';

function RootRedirect() {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return null;
  if (isAuthenticated && user) {
    return <Navigate to={getHomePathForRole(user.role)} replace />;
  }
  return <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<RootRedirect />} />
          <Route path="/login" element={<LoginPage />} />

          <Route
            path="/operator"
            element={
              <ProtectedRoute allowedRoles={['operator']}>
                <OperatorLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<OperatorDashboardPage />} />
            <Route path="history" element={<OperatorHistoryPage />} />
          </Route>

          <Route
            path="/owner"
            element={
              <ProtectedRoute allowedRoles={['owner']}>
                <OwnerLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<OwnerFuelEntriesPage />} />
            <Route path="entries/:id" element={<OwnerFuelEntryDetailPage />} />
            <Route path="vehicles" element={<OwnerVehiclesPage />} />
            <Route path="petrol-pumps" element={<OwnerPetrolPumpsPage />} />
            <Route path="operators" element={<OwnerOperatorsPage />} />
          </Route>

          <Route path="*" element={<RootRedirect />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
