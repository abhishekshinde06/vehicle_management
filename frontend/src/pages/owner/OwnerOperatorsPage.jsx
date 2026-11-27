import { useCallback, useEffect, useState } from 'react';
import { createOperator, getOperators } from '../../api/auth';
import AlertBanner from '../../components/AlertBanner';
import { extractApiError } from '../../utils/formatters';

export default function OwnerOperatorsPage() {
  const [operators, setOperators] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');

  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');

  const loadOperators = useCallback(async () => {
    setLoading(true);
    setListError('');
    try {
      const data = await getOperators();
      setOperators(data);
    } catch (err) {
      setListError(extractApiError(err, 'Failed to load operators.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOperators();
  }, [loadOperators]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError('');
    setFormSuccess('');

    const trimmedUsername = username.trim();
    const trimmedFullName = fullName.trim();
    if (!trimmedUsername || trimmedUsername.length < 3 || trimmedUsername.length > 50 || /\s/.test(trimmedUsername)) {
      setFormError('Username must be 3-50 characters and cannot contain spaces.');
      return;
    }
    if (!trimmedFullName) {
      setFormError('Full name is required.');
      return;
    }
    if (!password.trim() || /\s/.test(password) || password.length < 8) {
      setFormError('Password must be at least 8 characters and cannot contain spaces.');
      return;
    }

    setSubmitting(true);
    try {
      const created = await createOperator({
        username: trimmedUsername,
        password,
        full_name: trimmedFullName,
      });
      setFormSuccess(`Operator account "${created.username}" created successfully.`);
      setUsername('');
      setFullName('');
      setPassword('');
      loadOperators();
    } catch (err) {
      setFormError(extractApiError(err, 'Failed to create operator account.'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Fleet Operators</h1>
        <p className="text-sm text-slate-600 mt-0.5">
          Provision and view active driver / operator accounts for the tablet portal.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <form
          onSubmit={handleSubmit}
          className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4"
        >
          <h2 className="text-lg font-bold text-slate-900">Create Operator Account</h2>

          {formError && <AlertBanner variant="error">{formError}</AlertBanner>}
          {formSuccess && <AlertBanner variant="success">{formSuccess}</AlertBanner>}

          <div>
            <label htmlFor="op_username" className="block text-sm font-semibold text-slate-700 mb-1">
              Username *
            </label>
            <input
              id="op_username"
              type="text"
              required
              minLength={3}
              maxLength={50}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. ramesh_driver"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="op_full_name" className="block text-sm font-semibold text-slate-700 mb-1">
              Full Name *
            </label>
            <input
              id="op_full_name"
              type="text"
              required
              minLength={1}
              maxLength={100}
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Ramesh Kumar"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="op_password" className="block text-sm font-semibold text-slate-700 mb-1">
              Password * (min 8 characters)
            </label>
            <input
              id="op_password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 characters"
              className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 focus:border-blue-600 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white hover:bg-blue-700 disabled:opacity-60"
          >
            {submitting ? 'Creating...' : 'Create Operator'}
          </button>
        </form>

        <div className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900">
              Active Operators ({operators.length})
            </h2>
            <button
              type="button"
              onClick={loadOperators}
              disabled={loading}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>

          {listError && <AlertBanner variant="error">{listError}</AlertBanner>}

          {loading ? (
            <p className="text-sm text-slate-500 py-6 text-center">Loading operators...</p>
          ) : operators.length === 0 ? (
            <p className="text-sm text-slate-500 py-6 text-center">No active operators found.</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {operators.map((op) => (
                <div
                  key={op.id}
                  className="py-3.5 flex items-center justify-between gap-3"
                >
                  <div>
                    <p className="font-bold text-slate-900">
                      {op.full_name || op.username}
                    </p>
                    <p className="text-xs text-slate-500">Username: {op.username}</p>
                  </div>
                  <span className="text-xs font-semibold text-emerald-800 bg-emerald-50 border border-emerald-200 px-2.5 py-1 rounded-full">
                    {op.is_active ? 'Active Operator' : 'Inactive'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
