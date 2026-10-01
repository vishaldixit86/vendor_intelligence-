import { useEffect, useRef, useState } from 'react'
import './App.css'

const API_BASE_URL = 'http://127.0.0.1:8001'

type HealthResponse = { service: string; status: string }
type ContractSummary = {
  annual_base_fee: string
  business_area: string
  contract_id: string
  renewal_decision_date: string
  risk_tier: string
  sla_actual_percent: string
  sla_status: string
  sla_target_percent: string
  vendor_name: string
}
type FinancialScenarioTotal = { currency: string; record_count: number; scenario: string; total_amount: string }
type DataQualityReport = { warnings: string[] }
type AgentAnswer = { answer: string; evidence: string[]; limitations: string[]; route: string; source_files: string[] }
type QuestionContext = { contextVendorName?: string; contextVendorNames?: string[]; previousRoute?: string }
type ReviewField = { label: string; source_file: string; value: string }
type DecisionCandidate = { contract_id: string; evidence: string[]; priority: string; recommendation: string; review_fields?: ReviewField[]; source_files: string[]; status: string; vendor_name: string }
type DashboardData = {
  contracts: ContractSummary[]
  decisions: DecisionCandidate[]
  financials: FinancialScenarioTotal[]
  health: HealthResponse
  quality: DataQualityReport
}

async function getApiData<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) throw new Error(`${path} returned ${response.status}`)
  return response.json() as Promise<T>
}

async function askVendorQuestion(question: string, context: QuestionContext): Promise<AgentAnswer> {
  const response = await fetch(`${API_BASE_URL}/api/ask`, {
    body: JSON.stringify({
      context_vendor_name: context.contextVendorName,
      context_vendor_names: context.contextVendorNames,
      previous_route: context.previousRoute,
      question,
    }),
    headers: { 'Content-Type': 'application/json' },
    method: 'POST',
  })
  if (!response.ok) throw new Error(`/api/ask returned ${response.status}`)
  return response.json() as Promise<AgentAnswer>
}

function formatCurrency(amount: string, currency: string): string {
  return new Intl.NumberFormat('en-US', { currency, maximumFractionDigits: 0, style: 'currency' }).format(Number(amount))
}

function App() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [activeVendorName, setActiveVendorName] = useState('')
  const [conversationVendorNames, setConversationVendorNames] = useState<string[]>([])
  const [question, setQuestion] = useState('')
  const [agentAnswer, setAgentAnswer] = useState<AgentAnswer | null>(null)
  const [askError, setAskError] = useState<string | null>(null)
  const [dashboardDate] = useState(() => {
    const currentDate = new Date()
    currentDate.setHours(0, 0, 0, 0)
    return currentDate
  })
  const lastRouteRef = useRef<string | undefined>(undefined)

  useEffect(() => {
    async function loadDashboard(): Promise<void> {
      try {
        const [health, contracts, decisions, financials, quality] = await Promise.all([
          getApiData<HealthResponse>('/api/health'),
          getApiData<ContractSummary[]>('/api/semantic/contracts'),
          getApiData<DecisionCandidate[]>('/api/decisions/renewal-reviews'),
          getApiData<FinancialScenarioTotal[]>('/api/semantic/financials/summary'),
          getApiData<DataQualityReport>('/api/data/quality'),
        ])
        setData({ contracts, decisions, financials, health, quality })
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'The dashboard could not load its API data.')
      }
    }
    void loadDashboard()
  }, [])

  if (error) return <main className="app-shell"><section className="connection-state" aria-live="polite"><p className="eyebrow">API connection required</p><h1>Decision intelligence is waiting for the backend.</h1><p>{error}</p><code>cd citi-demo; .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload</code></section></main>
  if (!data) return <main className="app-shell"><section className="connection-state" aria-live="polite"><p className="eyebrow">Connecting to semantic layer</p><h1>Loading vendor decision intelligence...</h1></section></main>

  const draftDecisions = data.decisions.filter((decision) => decision.status === 'Draft')
  const questionVendorName = agentAnswer ? activeVendorName || undefined : undefined
  const reviewDecisions = questionVendorName
    ? draftDecisions.filter((decision) => decision.vendor_name === questionVendorName)
    : []
  const dueSoonDate = new Date(dashboardDate)
  dueSoonDate.setDate(dashboardDate.getDate() + 90)
  const renewalDate = (contract: ContractSummary) => new Date(`${contract.renewal_decision_date}T00:00:00`)
  const renewalWatchlist = [...data.contracts]
    .sort((left, right) => renewalDate(left).getTime() - renewalDate(right).getTime())
    .slice(0, 6)
  const overdueRenewals = data.contracts.filter((contract) => renewalDate(contract) < dashboardDate).length
  const dueSoonRenewals = data.contracts.filter((contract) => {
    const date = renewalDate(contract)
    return date >= dashboardDate && date <= dueSoonDate
  }).length

  async function submitQuestion(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault()
    const cleanedQuestion = question.trim()
    if (!cleanedQuestion) return
    const mentionedVendors = data?.contracts.filter(
      (contract) => cleanedQuestion.toLowerCase().includes(contract.vendor_name.toLowerCase()),
    ) ?? []
    if (mentionedVendors.length > 0) {
      setActiveVendorName(mentionedVendors[0].vendor_name)
    }
    const requestVendorNames = mentionedVendors.length > 0
      ? mentionedVendors.map((contract) => contract.vendor_name)
      : conversationVendorNames.length > 0
        ? conversationVendorNames
        : activeVendorName ? [activeVendorName] : []
    setAskError(null)
    try {
      const answer = await askVendorQuestion(cleanedQuestion, {
        contextVendorName: requestVendorNames[0],
        contextVendorNames: requestVendorNames,
        previousRoute: agentAnswer?.route ?? lastRouteRef.current,
      })
      lastRouteRef.current = answer.route
      setConversationVendorNames(requestVendorNames)
      setAgentAnswer(answer)
      setQuestion('')
    } catch (questionError) {
      setAskError(questionError instanceof Error ? questionError.message : 'The question could not be answered.')
    }
  }

  return <main className="vendor-workspace">
    <aside className="workspace-navigation" aria-label="Workspace navigation"><p className="navigation-title">Vendor Decision Intelligence</p><nav><a href="#portfolio">Portfolio</a><a className="active" href="#vendor-review">Vendor 360</a><a href="#human-review">Human review</a><a href="#financial-scenarios">Scenarios</a></nav></aside>
    <div className="app-shell">
    <section className="vendor-heading" id="vendor-review"><div><p className="eyebrow">Procurement intelligence workbench</p><h1>{activeVendorName || 'Portfolio command center'}</h1><p className="heading-summary">Review contract exposure, financial position, vendor evidence, and approval-ready decisions in one place.</p></div></section>
    <form className="question-bar" onSubmit={submitQuestion}><label htmlFor="vendor-question">Ask a vendor question</label><input id="vendor-question" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Should we renew, renegotiate, consolidate, or reduce dependency?" /><button type="submit">Ask</button></form>
    {askError && <p className="question-error" role="alert">{askError}</p>}
    {agentAnswer && <section className="agent-answer" aria-live="polite"><div className="answer-heading"><div><p className="eyebrow">{agentAnswer.route.replace('_', ' ')} specialist</p><h2>Evidence-backed response</h2></div><span className="panel-tag">Not approved</span></div><p className="answer-text">{agentAnswer.answer}</p><div className="answer-grid"><div><h3>Evidence</h3><ul>{agentAnswer.evidence.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div><div><h3>Sources</h3><ul>{agentAnswer.source_files.map((source) => <li key={source}>{source}</li>)}</ul><h3>Limitation</h3><ul>{agentAnswer.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}</ul></div></div></section>}
    <section className="renewal-dashboard" id="portfolio" aria-labelledby="renewal-dashboard-title">
      <div className="renewal-dashboard-heading"><div><p className="eyebrow">Contract dashboard</p><h2 id="renewal-dashboard-title">Renewal decisions that need attention.</h2></div><div className="renewal-counts"><span><strong>{overdueRenewals}</strong> past due</span><span><strong>{dueSoonRenewals}</strong> due in 90 days</span><span><strong>{draftDecisions.length}</strong> in human review</span></div></div>
      <div className="renewal-watchlist"><div className="watchlist-heading"><span>Vendor and business area</span><span>Renewal</span><span>SLA</span><span>Risk</span><span>Annual fee</span><span>Attention</span></div>{renewalWatchlist.map((contract) => { const date = renewalDate(contract); const isOverdue = date < dashboardDate; const isDueSoon = date <= dueSoonDate; return <article className="watchlist-row" key={contract.contract_id}><div><strong>{contract.vendor_name}</strong><span>{contract.contract_id} · {contract.business_area}</span></div><time dateTime={contract.renewal_decision_date}>{date.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' })}</time><div className="sla-summary"><strong>{contract.sla_status}</strong><span>{Number(contract.sla_actual_percent).toFixed(2)}% actual / {Number(contract.sla_target_percent).toFixed(2)}% target</span></div><span className={`risk-${contract.risk_tier.toLowerCase().replaceAll(' ', '-')}`}>{contract.risk_tier}</span><strong className="annual-fee">{formatCurrency(contract.annual_base_fee, 'USD')}</strong><span className={isOverdue ? 'status-overdue' : isDueSoon ? 'status-soon' : 'status-planned'}>{isOverdue ? 'Past due' : isDueSoon ? 'Due soon' : 'Planned'}</span></article>})}</div>
      <div className="finance-strip" id="financial-scenarios"><div><p className="eyebrow">Financial context</p><h3>Actual, budget, and forecast.</h3></div><div>{data.financials.map((scenario) => <article key={scenario.scenario}><span>{scenario.scenario}</span><strong>{formatCurrency(scenario.total_amount, scenario.currency)}</strong><small>{scenario.record_count} CSV records</small></article>)}</div></div>
    </section>
    <section className="decision-queue" id="human-review" aria-labelledby="decision-queue-title">
      <div className="queue-heading"><div><p className="eyebrow">Human review</p><h2 id="decision-queue-title">{questionVendorName ? `${reviewDecisions.length} review item${reviewDecisions.length === 1 ? '' : 's'} for ${questionVendorName}.` : 'No review item selected.'}</h2></div><p>{questionVendorName ? 'This section refreshes only for the vendor in the latest question.' : 'Ask a vendor question to load a relevant review item.'}</p></div>
      {reviewDecisions.length > 0 ? <div className="review-list">{reviewDecisions.map((decision) => <article className="review-card" key={decision.contract_id}><div className="review-card-heading"><div><p className="eyebrow">{decision.priority} priority / Requires review</p><h3>{decision.vendor_name}</h3><span>{decision.contract_id}</span></div><p>{decision.recommendation}</p></div><div className="review-signals" aria-label={`${decision.vendor_name} review signals`}>{decision.evidence.map((reason, index) => <span key={`${reason}-${index}`}>{reason}</span>)}</div><div className="review-reasons"><div><h4>CSV review snapshot</h4><dl className="review-fields">{(decision.review_fields ?? []).map((field) => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}</dl></div><div><h4>Open source data</h4><div className="source-links">{decision.source_files.map((source) => <a href={`${API_BASE_URL}/api/data/sources/${encodeURIComponent(source)}`} key={source} rel="noreferrer" target="_blank">{source}<span>Open CSV</span></a>)}</div></div></div></article>)}</div> : questionVendorName && agentAnswer ? <article className="review-assessment"><div><p className="eyebrow">Review assessment</p><h3>No human review required</h3><p>{agentAnswer.answer}</p></div><div><h4>Evidence checked</h4><ul>{agentAnswer.evidence.map((item, index) => <li key={`${item}-${index}`}>{item}</li>)}</ul></div></article> : <p className="review-empty">No review item is shown until a vendor question is submitted.</p>}
    </section>
    </div>
  </main>
}

export default App
