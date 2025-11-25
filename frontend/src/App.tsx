import './App.css'

import { LoadingOverlay } from './components/LoadingOverlay'
import { useAuth } from './hooks/useAuth'
import ChatPage from './pages/ChatPage'
import LoginPage from './pages/LoginPage'

function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return <LoadingOverlay />
  }

  return user ? <ChatPage /> : <LoginPage />
}

export default App

