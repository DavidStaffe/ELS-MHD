/**
 * Route guard component.
 *
 * Usage:
 *   <RequireAuth>                     – nur eingeloggt sein erforderlich
 *   <RequireAuth allowedRoles={['admin']}>  – zusätzlich Rollenprüfung
 *
 * Redirect to /login if not authenticated.
 * Redirect to / with a 403 state if role is not allowed.
 */
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../lib/auth';

export default function RequireAuth({ children, allowedRoles }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // User is logged in but lacks the required role
    return <Navigate to="/" state={{ forbidden: true, requiredRoles: allowedRoles }} replace />;
  }

  return children;
}
