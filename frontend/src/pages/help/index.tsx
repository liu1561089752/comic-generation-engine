import { Card, Tabs, Typography, Timeline, Collapse, Table, Tag, Descriptions } from 'antd'
import {
  BookOutlined,
  QuestionCircleOutlined,
  FileTextOutlined,
  InfoCircleOutlined,
  BarcodeOutlined,
} from '@ant-design/icons'

const { Text, Title } = Typography

// ---------- Changelog Data ----------

const changelogData = [
  { version: '1.0.0', date: '2026-06-15', items: ['正式版发布', '支持完整漫画生成流程', '集成 LLM 与生图模型管理', '新增插件中心'] },
  { version: '0.9.0', date: '2026-05-20', items: ['Beta 版发布', '优化 Prompt 生成逻辑'] },
  { version: '0.8.0', date: '2026-04-10', items: ['Alpha 版发布', '基础功能：项目管理、角色创建、分镜编辑'] },
]

// ---------- Component ----------

export default function HelpCenter() {
  return (
    <div>
      <Title level={4} style={{ marginTop: 0, marginBottom: 24 }}>
        帮助中心
      </Title>

      <Tabs
        defaultActiveKey="tutorial"
        items={[
          {
            key: 'tutorial',
            label: <span><BookOutlined /> 使用教程</span>,
            children: <TutorialTab />,
          },
          {
            key: 'shortcuts',
            label: <span><BarcodeOutlined /> 快捷键</span>,
            children: <ShortcutsTab />,
          },
          {
            key: 'faq',
            label: <span><QuestionCircleOutlined /> 常见问题</span>,
            children: <FAQTab />,
          },
          {
            key: 'changelog',
            label: <span><FileTextOutlined /> 更新日志</span>,
            children: <ChangelogTab />,
          },
          {
            key: 'about',
            label: <span><InfoCircleOutlined /> 关于系统</span>,
            children: <AboutTab />,
          },
        ]}
      />
    </div>
  )
}

// ---------- Tutorial ----------

function TutorialTab() {
  const steps = [
    { title: '1. 创建项目', description: '在项目管理中创建新项目，设置作品名称和基本信息。' },
    { title: '2. 导入或创作小说', description: '导入已有小说文本，或直接在编辑器中进行创作。' },
    { title: '3. 创建角色与世界观', description: '在人物IP和世界观模块中，定义角色形象和世界设定。' },
    { title: '4. 剧情拆解与分镜', description: '将小说拆解为剧情线，生成分镜草稿。' },
    { title: '5. Prompt 生成与优化', description: 'AI 自动生成生图 Prompt，可在 Prompt 中心编辑优化。' },
    { title: '6. 批量生图', description: '在生图中心配置参数，批量生成漫画画面。' },
    { title: '7. 导出成品', description: '在导出中心选择格式，导出完整漫画作品。' },
  ]

  return (
    <Card title="快速上手流程">
      <Timeline
        items={steps.map(s => ({
          children: (
            <div>
              <Text strong>{s.title}</Text>
              <br />
              <Text type="secondary">{s.description}</Text>
            </div>
          ),
        }))}
      />
    </Card>
  )
}

// ---------- Shortcuts ----------

function ShortcutsTab() {
  const shortcutData = [
    { key: 'Ctrl+S', action: '保存当前编辑', scope: '全局' },
    { key: 'Ctrl+Z', action: '撤销', scope: '编辑器' },
    { key: 'Ctrl+Shift+Z', action: '重做', scope: '编辑器' },
    { key: 'Ctrl+C', action: '复制选中元素', scope: '编辑器' },
    { key: 'Ctrl+V', action: '粘贴', scope: '编辑器' },
    { key: 'Delete', action: '删除选中元素', scope: '编辑器' },
    { key: 'Ctrl+A', action: '全选', scope: '编辑器' },
    { key: 'Ctrl++', action: '放大视图', scope: '编辑器' },
    { key: 'Ctrl+-', action: '缩小视图', scope: '编辑器' },
    { key: 'Ctrl+0', action: '重置缩放', scope: '编辑器' },
    { key: 'Space', action: '按住拖拽平移画布', scope: '编辑器' },
    { key: 'Ctrl+P', action: '快速跳转到项目', scope: '全局' },
    { key: 'Ctrl+K', action: '搜索', scope: '全局' },
    { key: 'Ctrl+E', action: '导出当前项目', scope: '全局' },
  ]

  const columns = [
    { title: '快捷键', dataIndex: 'key', key: 'key', render: (k: string) => <Tag color="blue">{k}</Tag> },
    { title: '功能', dataIndex: 'action', key: 'action' },
    { title: '适用范围', dataIndex: 'scope', key: 'scope', render: (s: string) => <Tag>{s}</Tag> },
  ]

  return (
    <Card title="快捷键一览">
      <Table dataSource={shortcutData} columns={columns} rowKey="key" pagination={false} size="small" />
    </Card>
  )
}

// ---------- FAQ ----------

function FAQTab() {
  const faqItems = [
    {
      key: '1',
      label: '如何配置 AI 模型？',
      children: (
        <Text>进入「模型配置中心」，分别配置 LLM 模型和生图模型的 API Base URL、API Key 和模型名称，然后点击"测试连接"验证配置是否正确。</Text>
      ),
    },
    {
      key: '2',
      label: '生图速度太慢怎么办？',
      children: (
        <Text>可以在系统设置中调整「最大并发数」来提高生图速度。同时注意检查网络状况和 API 服务的响应速度。</Text>
      ),
    },
    {
      key: '3',
      label: '如何恢复误删的项目？',
      children: (
        <Text>目前系统会定期自动备份数据。您可以前往「系统管理 → 数据备份」页面，查找最近的备份进行恢复。</Text>
      ),
    },
    {
      key: '4',
      label: '支持哪些图片格式导出？',
      children: (
        <Text>支持导出为 PNG、JPG、PDF、CBZ 等格式。可在导出中心选择需要的格式。</Text>
      ),
    },
    {
      key: '5',
      label: 'Prompt 生成效果不理想如何优化？',
      children: (
        <Text>可以在 Prompt 中心手动编辑和优化生成的 Prompt。也建议在模型配置中心调整 LLM 模型参数，如温度和最大 Token 数。</Text>
      ),
    },
    {
      key: '6',
      label: '如何共享团队项目？',
      children: (
        <Text>目前系统支持单用户模式。多用户协作功能将在后续版本中推出。</Text>
      ),
    },
  ]

  return (
    <Card title="常见问题">
      <Collapse items={faqItems} />
    </Card>
  )
}

// ---------- Changelog ----------

function ChangelogTab() {
  return (
    <Card title="版本更新记录">
      <Timeline
        items={changelogData.map(v => ({
          color: v.version === '1.0.0' ? 'green' : 'blue',
          children: (
            <div>
              <Text strong>v{v.version}</Text>
              <Text type="secondary" style={{ marginLeft: 12 }}>{v.date}</Text>
              <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                {v.items.map((item, i) => (
                  <li key={i}><Text>{item}</Text></li>
                ))}
              </ul>
            </div>
          ),
        }))}
      />
    </Card>
  )
}

// ---------- About ----------

function AboutTab() {
  return (
    <Card title="关于 AI Webtoon Factory">
      <Descriptions bordered size="small" column={1} style={{ maxWidth: 600 }}>
        <Descriptions.Item label="系统名称">AI Webtoon Factory</Descriptions.Item>
        <Descriptions.Item label="版本">1.0.0</Descriptions.Item>
        <Descriptions.Item label="技术栈">React + FastAPI + SQLAlchemy</Descriptions.Item>
        <Descriptions.Item label="描述">
          基于 AI 的漫画/条漫自动生成引擎，集成 LLM 文本生成与 Stable Diffusion 生图能力，
          支持从小说到成品的全流程自动化创作。
        </Descriptions.Item>
        <Descriptions.Item label="LLM 支持">OpenAI / Claude / DeepSeek / GLM / Qwen</Descriptions.Item>
        <Descriptions.Item label="生图引擎">SDXL / SD3.5 / FLUX / DALL-E 3 / Midjourney / CogView</Descriptions.Item>
        <Descriptions.Item label="开源协议">MIT License</Descriptions.Item>
      </Descriptions>
    </Card>
  )
}
