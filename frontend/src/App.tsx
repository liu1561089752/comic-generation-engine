import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import AppLayout from './components/Layout'
import { useAuthStore } from './stores/authStore'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Login = lazy(() => import('./pages/Login'))
const ProjectDetail = lazy(() => import('./pages/projects/[id]'))
const ProjectList = lazy(() => import('./pages/projects'))
const NovelList = lazy(() => import('./pages/novels'))
const NovelDetail = lazy(() => import('./pages/novels/[id]'))
const NovelEditor = lazy(() => import('./pages/novels/editor'))
const StoryBreakdownLanding = lazy(() => import('./pages/story-breakdown'))
const StoryBreakdownDetail = lazy(() => import('./pages/story-breakdown/detail'))
const ProjectStoryBreakdown = lazy(() => import('./pages/story-breakdown/project-entry'))
const ProjectStoryboard = lazy(() => import('./pages/storyboard/project-storyboard'))
const ProjectLayoutPage = lazy(() => import('./pages/layout/project-layout'))
const CharacterList = lazy(() => import('./pages/characters'))
const CharacterGlobalList = lazy(() => import('./pages/characters/global'))
const CharacterDetail = lazy(() => import('./pages/characters/[id]'))
const CharacterRelations = lazy(() => import('./pages/characters/relations'))
const WorldList = lazy(() => import('./pages/worlds'))
const WorldDetail = lazy(() => import('./pages/worlds/[id]'))
const StyleTemplateList = lazy(() => import('./pages/style-templates'))
const EditorList = lazy(() => import('./pages/editor'))
const ComicEditor = lazy(() => import('./pages/editor/[pageId]'))
const ExportCenter = lazy(() => import('./pages/export'))
const TaskCenter = lazy(() => import('./pages/tasks'))
const ModelCenter = lazy(() => import('./pages/models'))
const GenerationCenter = lazy(() => import('./pages/generation'))
const QualityCenter = lazy(() => import('./pages/quality'))
const NotificationsPage = lazy(() => import('./pages/notifications'))
const SystemSettings = lazy(() => import('./pages/system'))
const StoryboardCenter = lazy(() => import('./pages/storyboard'))
const LayoutCenter = lazy(() => import('./pages/layout'))
const TextCenter = lazy(() => import('./pages/text-center'))
const PromptCenter = lazy(() => import('./pages/prompt-center'))
const ResourceCenter = lazy(() => import('./pages/resources'))
const PluginCenter = lazy(() => import('./pages/plugins'))
const HelpCenter = lazy(() => import('./pages/help'))

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh', color: '#888', fontSize: '14px' }}>
          加载中...
        </div>
      }>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<ProjectList />} />
          <Route path="projects/:id" element={<ProjectDetail />}>
            <Route path="novels" element={<NovelList />} />
            <Route path="novels/:novelId" element={<NovelDetail />} />
            <Route path="novels/:novelId/editor" element={<NovelEditor />} />
            <Route path="novels/:novelId/story-breakdown" element={<StoryBreakdownDetail />} />
            <Route path="characters" element={<CharacterList />} />
            <Route path="characters/:characterId" element={<CharacterDetail />} />
            <Route path="characters/relations" element={<CharacterRelations />} />
            <Route path="worlds" element={<WorldList />} />
            <Route path="worlds/:worldId" element={<WorldDetail />} />
            <Route path="style-templates" element={<StyleTemplateList />} />
            <Route path="story-breakdown" element={<ProjectStoryBreakdown />} />
            <Route path="storyboard" element={<ProjectStoryboard />} />
            <Route path="novels/:novelId/storyboard" element={<ProjectStoryboard />} />
            <Route path="layout" element={<ProjectLayoutPage />} />
            <Route path="novels/:novelId/layout" element={<ProjectLayoutPage />} />            
            <Route path="generation" element={<GenerationCenter />} />
            <Route path="quality" element={<QualityCenter />} />
            <Route path="editor" element={<EditorList />} />
            <Route path="editor/:pageId" element={<ComicEditor />} />
            <Route path="export" element={<ExportCenter />} />
          </Route>
          <Route path="characters" element={<CharacterGlobalList />} />
          <Route path="novels" element={<NovelList />} />
          <Route path="editor" element={<EditorList />} />
          <Route path="export" element={<ExportCenter />} />
          <Route path="storyboard" element={<StoryboardCenter />} />
          <Route path="layout" element={<LayoutCenter />} />
          <Route path="story-breakdown" element={<StoryBreakdownLanding />} />
          <Route path="text-center" element={<TextCenter />} />
          <Route path="prompts" element={<PromptCenter />} />
          <Route path="models" element={<ModelCenter />} />
          <Route path="generation" element={<GenerationCenter />} />
          <Route path="quality" element={<QualityCenter />} />
          <Route path="tasks" element={<TaskCenter />} />
          <Route path="notifications" element={<NotificationsPage />} />
          <Route path="system" element={<SystemSettings />} />
          <Route path="resources" element={<ResourceCenter />} />
          <Route path="plugins" element={<PluginCenter />} />
          <Route path="help" element={<HelpCenter />} />
        </Route>
      </Routes>
      </Suspense>
    </BrowserRouter>
  )
}

export default App
