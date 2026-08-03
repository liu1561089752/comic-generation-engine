import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Suspense } from 'react'
import { Spin } from 'antd'
import AppLayout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import { useAuthStore } from './stores/authStore'
import {
  Dashboard,
  Login,
  ProjectDetail,
  ProjectList,
  NovelList,
  NovelDetail,
  NovelEditor,
  StoryBreakdownLanding,
  StoryBreakdownDetail,
  ProjectStoryBreakdown,
  ProjectStoryboard,
  ProjectLayoutPage,
  CharacterList,
  CharacterGlobalList,
  CharacterDetail,
  CharacterRelations,
  WorldList,
  WorldDetail,
  StyleTemplateList,
  EditorList,
  ComicEditor,
  ExportCenter,
  TaskCenter,
  ModelCenter,
  GenerationCenter,
  QualityCenter,
  NotificationsPage,
  SystemSettings,
  StoryboardCenter,
  LayoutCenter,
  TextCenter,
  PromptCenter,
  ResourceCenter,
  PluginCenter,
  HelpCenter,
} from './routeComponents'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

/**
 * 轻量级 Suspense fallback
 *
 * 设计要点：
 *  - 不使用全屏白底，避免与目标页面产生明显的背景反差
 *  - 只在内容区显示 Spin，保持左侧导航栏和顶部 Header 不被遮挡
 *  - Spin 颜色随主题色，视觉干扰最小
 */
function RouteFallback() {
  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'calc(100vh - 120px)' }}>
      <Spin size="large" />
    </div>
  )
}

function App() {
  return (
    <BrowserRouter>
      <ErrorBoundary>
      <Routes>
        <Route path="/login" element={<Suspense fallback={null}><Login /></Suspense>} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Suspense fallback={<RouteFallback />}><Dashboard /></Suspense>} />
          <Route path="projects" element={<Suspense fallback={<RouteFallback />}><ProjectList /></Suspense>} />
          <Route path="projects/:id" element={<Suspense fallback={<RouteFallback />}><ProjectDetail /></Suspense>}>
            <Route path="novels" element={<Suspense fallback={<RouteFallback />}><NovelList /></Suspense>} />
            <Route path="novels/:novelId" element={<Suspense fallback={<RouteFallback />}><NovelDetail /></Suspense>} />
            <Route path="novels/:novelId/editor" element={<Suspense fallback={<RouteFallback />}><NovelEditor /></Suspense>} />
            <Route path="novels/:novelId/story-breakdown" element={<Suspense fallback={<RouteFallback />}><StoryBreakdownDetail /></Suspense>} />
            <Route path="characters" element={<Suspense fallback={<RouteFallback />}><CharacterList /></Suspense>} />
            <Route path="characters/:characterId" element={<Suspense fallback={<RouteFallback />}><CharacterDetail /></Suspense>} />
            <Route path="characters/relations" element={<Suspense fallback={<RouteFallback />}><CharacterRelations /></Suspense>} />
            <Route path="worlds" element={<Suspense fallback={<RouteFallback />}><WorldList /></Suspense>} />
            <Route path="worlds/:worldId" element={<Suspense fallback={<RouteFallback />}><WorldDetail /></Suspense>} />
            <Route path="style-templates" element={<Suspense fallback={<RouteFallback />}><StyleTemplateList /></Suspense>} />
            <Route path="story-breakdown" element={<Suspense fallback={<RouteFallback />}><ProjectStoryBreakdown /></Suspense>} />
            <Route path="storyboard" element={<Suspense fallback={<RouteFallback />}><ProjectStoryboard /></Suspense>} />
            <Route path="novels/:novelId/storyboard" element={<Suspense fallback={<RouteFallback />}><ProjectStoryboard /></Suspense>} />
            <Route path="layout" element={<Suspense fallback={<RouteFallback />}><ProjectLayoutPage /></Suspense>} />
            <Route path="novels/:novelId/layout" element={<Suspense fallback={<RouteFallback />}><ProjectLayoutPage /></Suspense>} />
            <Route path="generation" element={<Suspense fallback={<RouteFallback />}><GenerationCenter /></Suspense>} />
            <Route path="quality" element={<Suspense fallback={<RouteFallback />}><QualityCenter /></Suspense>} />
            <Route path="editor" element={<Suspense fallback={<RouteFallback />}><EditorList /></Suspense>} />
            <Route path="editor/:pageId" element={<Suspense fallback={<RouteFallback />}><ComicEditor /></Suspense>} />
            <Route path="export" element={<Suspense fallback={<RouteFallback />}><ExportCenter /></Suspense>} />
        </Route>
          <Route path="characters" element={<Suspense fallback={<RouteFallback />}><CharacterGlobalList /></Suspense>} />
          <Route path="novels" element={<Suspense fallback={<RouteFallback />}><NovelList /></Suspense>} />
          <Route path="editor" element={<Suspense fallback={<RouteFallback />}><EditorList /></Suspense>} />
          <Route path="export" element={<Suspense fallback={<RouteFallback />}><ExportCenter /></Suspense>} />
          <Route path="storyboard" element={<Suspense fallback={<RouteFallback />}><StoryboardCenter /></Suspense>} />
          <Route path="layout" element={<Suspense fallback={<RouteFallback />}><LayoutCenter /></Suspense>} />
          <Route path="story-breakdown" element={<Suspense fallback={<RouteFallback />}><StoryBreakdownLanding /></Suspense>} />
          <Route path="text-center" element={<Suspense fallback={<RouteFallback />}><TextCenter /></Suspense>} />
          <Route path="prompts" element={<Suspense fallback={<RouteFallback />}><PromptCenter /></Suspense>} />
          <Route path="models" element={<Suspense fallback={<RouteFallback />}><ModelCenter /></Suspense>} />
          <Route path="generation" element={<Suspense fallback={<RouteFallback />}><GenerationCenter /></Suspense>} />
          <Route path="quality" element={<Suspense fallback={<RouteFallback />}><QualityCenter /></Suspense>} />
          <Route path="tasks" element={<Suspense fallback={<RouteFallback />}><TaskCenter /></Suspense>} />
          <Route path="notifications" element={<Suspense fallback={<RouteFallback />}><NotificationsPage /></Suspense>} />
          <Route path="system" element={<Suspense fallback={<RouteFallback />}><SystemSettings /></Suspense>} />
          <Route path="resources" element={<Suspense fallback={<RouteFallback />}><ResourceCenter /></Suspense>} />
          <Route path="plugins" element={<Suspense fallback={<RouteFallback />}><PluginCenter /></Suspense>} />
          <Route path="help" element={<Suspense fallback={<RouteFallback />}><HelpCenter /></Suspense>} />
        </Route>
      </Routes>
      </ErrorBoundary>
    </BrowserRouter>
  )
}

export default App
