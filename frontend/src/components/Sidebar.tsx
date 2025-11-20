import { Link, useLocation } from 'react-router-dom'

export default function Sidebar() {
  const location = useLocation()

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/jobs', label: 'Jobs', icon: '📋' },
    { path: '/templates', label: 'Templates', icon: '📝' },
    { path: '/settings', label: 'Settings', icon: '⚙️' },
  ]

  return (
    <aside className="w-64 bg-gray-900 text-white p-4">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Plot Palette</h1>
        <p className="text-gray-400 text-sm">Synthetic Data Generator</p>
      </div>

      <nav className="space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`block px-4 py-2 rounded-lg transition-colors ${
              location.pathname === item.path
                ? 'bg-blue-600 text-white'
                : 'text-gray-300 hover:bg-gray-800'
            }`}
          >
            <span className="mr-2">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
