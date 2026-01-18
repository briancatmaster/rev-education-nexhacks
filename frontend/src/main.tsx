import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './globals.css'

import RootLayout from './layouts/RootLayout'
import SiteLayout from './layouts/SiteLayout'
import LessonsLayout from './layouts/LessonsLayout'

import HomePage from './pages/Home'
import OnboardingPage from './pages/Onboarding'
import LessonsPage from './pages/Lessons'
import LessonDetailPage from './pages/LessonDetail'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<RootLayout />}>
          <Route element={<SiteLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/onboarding" element={<OnboardingPage />} />
            <Route element={<LessonsLayout />}>
              <Route path="/lessons" element={<LessonsPage />} />
              <Route path="/lessons/:lessonId" element={<LessonDetailPage />} />
            </Route>
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
