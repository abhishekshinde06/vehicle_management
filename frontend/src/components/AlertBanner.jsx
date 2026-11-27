const VARIANT_CLASSES = {
  info: 'bg-blue-50 border-blue-200 text-blue-900',
  success: 'bg-emerald-50 border-emerald-200 text-emerald-900',
  warning: 'bg-amber-50 border-amber-300 text-amber-950',
  error: 'bg-red-50 border-red-300 text-red-900',
};

export default function AlertBanner({ variant = 'info', title, children, className = '' }) {
  const styles = VARIANT_CLASSES[variant] || VARIANT_CLASSES.info;

  return (
    <div
      role={variant === 'error' || variant === 'warning' ? 'alert' : 'status'}
      className={`rounded-xl border px-4 py-3 text-sm ${styles} ${className}`}
    >
      {title && <p className="font-semibold mb-0.5">{title}</p>}
      <div>{children}</div>
    </div>
  );
}
