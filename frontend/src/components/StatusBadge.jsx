const STATUS_STYLES = {
  PENDING: 'bg-amber-100 text-amber-900 border-amber-300',
  APPROVED: 'bg-emerald-100 text-emerald-900 border-emerald-300',
  REJECTED: 'bg-red-100 text-red-900 border-red-300',
};

export default function StatusBadge({ status }) {
  const normalized = (status || 'PENDING').toUpperCase();
  const style = STATUS_STYLES[normalized] || 'bg-slate-100 text-slate-800 border-slate-300';

  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold tracking-wide border ${style}`}
    >
      {normalized}
    </span>
  );
}
