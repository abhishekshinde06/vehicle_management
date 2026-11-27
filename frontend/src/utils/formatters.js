export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatNumber(value, decimals = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: decimals,
  });
}

export function extractApiError(error, fallback = 'An unexpected error occurred. Please try again.') {
  if (!error) return fallback;

  if (!error.response) {
    return 'Unable to reach the server. Check your network connection and API server.';
  }

  const { status, data } = error.response;

  if (status === 422 && Array.isArray(data?.detail)) {
    const messages = data.detail.map((item) => {
      const field = Array.isArray(item.loc)
        ? item.loc.filter((part) => part !== 'body').join('.')
        : '';
      return field ? `${field}: ${item.msg}` : item.msg;
    });
    return messages.join(' | ') || 'Validation failed. Please check your inputs.';
  }

  if (typeof data?.detail === 'string' && data.detail.trim()) {
    return data.detail;
  }

  if (status === 401) return 'Your session has expired or credentials are invalid.';
  if (status === 403) return 'You do not have permission to perform this action.';
  if (status === 404) return 'The requested resource was not found.';
  if (status === 409) return 'This record conflicts with its current state (e.g., already reviewed).';
  if (status >= 500) return 'Server error occurred. Please try again shortly.';

  return fallback;
}
