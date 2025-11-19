import { useAuth } from '../contexts/AuthContext'

export default function Header() {
  const { logout } = useAuth()

  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
      <div>
        <h2 className="text-xl font-semibold text-gray-800">Welcome to Plot Palette</h2>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-gray-600">User</span>
        <button
          onClick={logout}
          className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors"
        >
          Logout
        </button>
      </div>
    </header>
  )
}
