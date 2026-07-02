import { useState, useEffect } from 'react'
import {
  Card, Table, Button, Modal, Input, Space, Tag, message,
  Typography, Alert, Form,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, EditOutlined, RobotOutlined,
  CodeOutlined, ReloadOutlined,
} from '@ant-design/icons'
import { apiClient, type StrategyInfo } from '../api/client'
import LoadingState from '../components/LoadingState'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'

const { TextArea } = Input
const { Text } = Typography

export default function StrategyPage() {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [aiConfigured, setAiConfigured] = useState(false)
  const [aiModalOpen, setAiModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [aiDescription, setAiDescription] = useState('')
  const [aiFilename, setAiFilename] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [editingCode, setEditingCode] = useState('')
  const [editingFilename, setEditingFilename] = useState('')
  const [viewCode, setViewCode] = useState('')

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [list, ai] = await Promise.all([
        apiClient.getStrategies(),
        apiClient.aiStatus(),
      ])
      setStrategies(list)
      setAiConfigured(ai.configured)
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || '加载策略列表失败'
      setError(msg)
      message.error(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const handleAIGenerate = async () => {
    if (!aiDescription.trim()) {
      message.warning('请描述你的策略')
      return
    }
    setAiLoading(true)
    try {
      const result = await apiClient.aiGenerateStrategy(aiDescription, aiFilename)
      message.success('AI 策略生成成功！')
      setAiModalOpen(false)
      setEditingCode(result.code)
      setEditingFilename(result.filename)
      setEditModalOpen(true)
      setAiDescription('')
      setAiFilename('')
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } }; code?: string; message?: string })
      const msg = detail.response?.data?.detail
        || (detail.code === 'ECONNABORTED' ? '请求超时，AI 仍在生成中，请稍后重试或简化描述' : '')
        || detail.message
        || 'AI 生成失败'
      message.error(msg)
    } finally {
      setAiLoading(false)
    }
  }

  const handleView = async (filename: string) => {
    try {
      const result = await apiClient.getStrategyCode(filename)
      setViewCode(result.code)
    } catch {
      message.error('读取策略失败')
    }
  }

  const handleEdit = async (filename: string) => {
    try {
      const result = await apiClient.getStrategyCode(filename)
      setEditingCode(result.code)
      setEditingFilename(filename)
      setEditModalOpen(true)
    } catch {
      message.error('读取策略失败')
    }
  }

  const handleSave = async () => {
    try {
      await apiClient.saveStrategy(editingFilename, editingCode)
      message.success('策略已保存')
      setEditModalOpen(false)
      load()
    } catch (err: any) {
      message.error(err.response?.data?.detail || '保存失败')
    }
  }

  const handleDelete = (filename: string) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除策略 ${filename} 吗？`,
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await apiClient.deleteStrategy(filename)
          message.success('策略已删除')
          load()
        } catch {
          message.error('删除失败')
        }
      },
    })
  }

  return (
    <div>
      <Card
        title={
          <span>
            <CodeOutlined style={{ marginRight: 8 }} />
            策略管理
            {strategies.length > 0 && (
              <Tag style={{ marginLeft: 8 }} color="blue">{strategies.length} 个</Tag>
            )}
          </span>
        }
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={load}>刷新</Button>
            <Button
              type="primary"
              icon={<RobotOutlined />}
              onClick={async () => {
                try {
                  const ai = await apiClient.aiStatus()
                  setAiConfigured(ai.configured)
                } catch { /* ignore */ }
                setAiModalOpen(true)
              }}
              disabled={!aiConfigured}
            >
              AI 生成策略
            </Button>
            <Button
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingCode('# 新策略\n')
                setEditingFilename('NewStrategy.py')
                setEditModalOpen(true)
              }}
            >
              新建策略
            </Button>
          </Space>
        }
      >
        {!aiConfigured && (
          <Alert
            message="AI 策略生成器未配置"
            description="在 .env 中设置 DEEPSEEK_API_KEY=sk-xxx 即可启用 AI 策略生成功能。获取 Key: https://platform.deepseek.com"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {error && <ErrorState message="加载失败" description={error} onRetry={load} />}

        {loading && !error && <LoadingState />}

        {!loading && !error && strategies.length === 0 && (
          <EmptyState
            description="暂无策略"
            detail='点击「新建策略」手动编写，或配置 AI Key 后使用「AI 生成策略」'
          />
        )}

        {!loading && strategies.length > 0 && (
          <Table
            dataSource={strategies}
            rowKey="filename"
            pagination={false}
            scroll={{ x: 720 }}
            size="middle"
            columns={[
              {
                title: '文件名',
                dataIndex: 'filename',
                key: 'filename',
                width: 200,
                render: (v: string) => <Text code>{v}</Text>,
              },
              { title: '类名', dataIndex: 'name', key: 'name', width: 200 },
              {
                title: '描述',
                dataIndex: 'description',
                key: 'description',
                ellipsis: true,
              },
              {
                title: '状态',
                key: 'status',
                width: 100,
                render: (_: any, r: StrategyInfo) =>
                  r.has_errors ? (
                    <Tag color="error">语法错误</Tag>
                  ) : (
                    <Tag color="success">正常</Tag>
                  ),
              },
              {
                title: '操作',
                key: 'actions',
                width: 220,
                render: (_: any, r: StrategyInfo) => (
                  <Space size="small">
                    <Button size="small" icon={<CodeOutlined />} onClick={() => handleView(r.filename)}>
                      查看
                    </Button>
                    <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(r.filename)}>
                      编辑
                    </Button>
                    <Button
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleDelete(r.filename)}
                    />
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>

      {/* AI 生成弹窗 */}
      <Modal
        title={<span><RobotOutlined /> AI 策略生成器（DeepSeek）</span>}
        open={aiModalOpen}
        onCancel={() => setAiModalOpen(false)}
        onOk={handleAIGenerate}
        okText="生成策略"
        cancelText="取消"
        confirmLoading={aiLoading}
        width={700}
      >
        <Alert
          message="用自然语言描述你的交易策略，AI 会自动生成 Freqtrade 兼容的 Python 代码"
          description="生成通常需要 10–120 秒，请耐心等待，不要关闭窗口。"
          type="info"
          style={{ marginBottom: 16 }}
        />
        <Form layout="vertical">
          <Form.Item label="策略文件名（可选）">
            <Input
              placeholder="如: MacdStrategy.py"
              value={aiFilename}
              onChange={(e) => setAiFilename(e.target.value)}
            />
          </Form.Item>
          <Form.Item label="策略描述">
            <TextArea
              rows={8}
              placeholder={`示例：\n我想要一个基于 MACD 指标的趋势跟踪策略。\n当 MACD 柱状图从负转正时做多，从正转负时做空。\n用 ATR 设置止损，ATR 周期 14。\n同时用 RSI 过滤超买超卖区域，RSI > 70 不做多，RSI < 30 不做空。\n止盈 5%，止损 3%。`}
              value={aiDescription}
              onChange={(e) => setAiDescription(e.target.value)}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑弹窗 */}
      <Modal
        title={`编辑策略: ${editingFilename}`}
        open={editModalOpen}
        onCancel={() => setEditModalOpen(false)}
        onOk={handleSave}
        okText="保存"
        cancelText="取消"
        width={900}
      >
        <Input
          value={editingFilename}
          onChange={(e) => setEditingFilename(e.target.value)}
          style={{ marginBottom: 8 }}
          addonBefore="文件名"
        />
        <TextArea
          rows={22}
          value={editingCode}
          onChange={(e) => setEditingCode(e.target.value)}
          style={{ fontFamily: 'Consolas, Monaco, monospace', fontSize: 13 }}
        />
      </Modal>

      {/* 查看代码弹窗 */}
      <Modal
        title="策略代码"
        open={!!viewCode}
        onCancel={() => setViewCode('')}
        footer={null}
        width={900}
      >
        <pre style={{
          background: '#1a1a2e',
          color: '#e0e0e0',
          padding: 16,
          borderRadius: 8,
          overflow: 'auto',
          maxHeight: 600,
          fontSize: 13,
          fontFamily: 'Consolas, Monaco, monospace',
        }}>
          {viewCode}
        </pre>
      </Modal>
    </div>
  )
}
