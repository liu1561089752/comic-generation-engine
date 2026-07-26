import type {
  PendingPanel,
  ConsistencyReport,
  QualityReport,
  PanelOption,
} from './types'

export const MOCK_PENDING: PendingPanel[] = Array.from({ length: 8 }, (_, i) => ({
  id: `panel-${i + 1}`,
  panel_number: i + 1,
  thumbnail_url: undefined,
  status: i < 5 ? 'pending' : 'reviewed',
  created_at: '2026-06-28T10:00:00Z',
}))

export const MOCK_CONSISTENCY: ConsistencyReport = {
  panel_id: 'panel-1',
  checks: [
    {
      character_name: 'Alice',
      overall_match: true,
      dimensions: [
        { dimension: 'hair_color', expected: 'blonde', detected: 'blonde', match: true, confidence: 100 },
        { dimension: 'hair_style', expected: 'long straight', detected: 'long straight', match: true, confidence: 100 },
        { dimension: 'eye_color', expected: 'blue', detected: 'blue', match: true, confidence: 100 },
        { dimension: 'skin_tone', expected: 'fair', detected: 'fair', match: true, confidence: 100 },
        { dimension: 'clothing', expected: 'school uniform', detected: 'school uniform', match: true, confidence: 100 },
      ],
    },
    {
      character_name: 'Bob',
      overall_match: false,
      dimensions: [
        { dimension: 'hair_color', expected: 'brown', detected: 'black', match: false, confidence: 85 },
        { dimension: 'hair_style', expected: 'short', detected: 'short', match: true, confidence: 100 },
        { dimension: 'eye_color', expected: 'green', detected: 'green', match: true, confidence: 100 },
        { dimension: 'skin_tone', expected: 'olive', detected: 'olive', match: true, confidence: 100 },
        { dimension: 'clothing', expected: 'casual', detected: 'casual', match: true, confidence: 100 },
      ],
    },
  ],
  passed: false,
  overall_score: 0.9,
}

export const MOCK_QUALITY: QualityReport = {
  panel_id: 'panel-1',
  scores: [
    { dimension: 'composition', score: 82, weight: 0.25, comment: '良好' },
    { dimension: 'character_integrity', score: 75, weight: 0.25, comment: '良好' },
    { dimension: 'lighting', score: 68, weight: 0.15, comment: '一般' },
    { dimension: 'detail', score: 70, weight: 0.15, comment: '良好' },
    { dimension: 'style_consistency', score: 88, weight: 0.20, comment: '优秀' },
  ],
  overall_score: 77.3,
  defects: ['光照偏暗', '细节层次不够丰富'],
  recommendation: 'recommended',
}

export const MOCK_CHECKED_PANELS: PanelOption[] = Array.from({ length: 6 }, (_, i) => ({
  id: `panel-${i + 1}`,
  panel_number: i + 1,
}))

export const MOCK_SCORED_PANELS: PanelOption[] = Array.from({ length: 6 }, (_, i) => ({
  id: `panel-${i + 1}`,
  panel_number: i + 1,
}))
