import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Materials } from './pages/Materials'
import { Dashboard } from './pages/Dashboard'
import { AmmunitionPage } from './pages/Ammunition'
import { TestSessions } from './pages/TestSessions'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <Layout>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/materials" element={<Materials />} />
                    <Route path="/ammunition" element={<AmmunitionPage />} />
                    <Route path="/test-sessions" element={<TestSessions />} />
                    <Route path="/panels" element={<div className="p-8">Panels - Coming Soon</div>} />
                    <Route path="/shots" element={<div className="p-8">Shots - Coming Soon</div>} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Layout>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
