import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProtectedRoute } from './components/ProtectedRoute'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Materials } from './pages/Materials'
import { Dashboard } from './pages/Dashboard'
import { AmmunitionPage } from './pages/Ammunition'
import { TestSessions } from './pages/TestSessions'
import { TestSessionDetail } from './pages/TestSessionDetail'
import { Analytics } from './pages/Analytics'
import { Vests } from './pages/Vests'
import { BallisticTesting } from './pages/BallisticTesting'
import { ModelTraining } from './pages/ModelTraining'
import { OfficialCertifications } from './pages/OfficialCertifications'
import { Protocols } from './pages/Protocols'
import { Comparison } from './pages/Comparison'
import { ViewerModeProvider } from './contexts/ViewerModeContext'

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
      <ViewerModeProvider>
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
                      <Route path="/official-certifications" element={<OfficialCertifications />} />
                      <Route path="/test-sessions/:id" element={<TestSessionDetail />} />
                      <Route path="/vests" element={<Vests />} />
                      <Route path="/protocols" element={<Protocols />} />
                      <Route path="/analytics" element={<Analytics />} />
                      <Route path="/comparison" element={<Comparison />} />
                      <Route path="/predictions" element={<BallisticTesting />} />
                      <Route path="/model-training" element={<ModelTraining />} />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Routes>
                  </Layout>
                </ProtectedRoute>
              }
            />
          </Routes>
        </BrowserRouter>
      </ViewerModeProvider>
    </QueryClientProvider>
  )
}

export default App
