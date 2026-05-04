const ROLE_LABELS = {
  admin: 'Admin',
  el: 'Einsatzleiter',
  fa: 'Führungsassistent',
  al: 'Abschnittsleiter',
  dokumentation: 'Dokumentation',
};

const ROLE_COLORS = {
  admin: 'bg-red-100 text-red-800 border-red-200',
  el: 'bg-blue-100 text-blue-800 border-blue-200',
  fa: 'bg-green-100 text-green-800 border-green-200',
  al: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  dokumentation: 'bg-gray-100 text-gray-800 border-gray-200',
};

export default function RoleBadge({ role, size = 'sm' }) {
  const label = ROLE_LABELS[role] || role;
  const color = ROLE_COLORS[role] || 'bg-gray-100 text-gray-800 border-gray-200';
  const sizeClass = size === 'sm' ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1';

  return (
    <span
      className={`inline-flex items-center rounded-full border font-medium ${color} ${sizeClass}`}
    >
      {label}
    </span>
  );
}
