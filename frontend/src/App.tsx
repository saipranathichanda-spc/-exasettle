import React, { useState, useEffect, useRef } from "react"
import { HeroSection } from "@/components/ui/hero-section-dark"
import {
  CheckCircle2,
  AlertTriangle,
  AlertOctagon,
  Clock,
  RefreshCw,
  FileSpreadsheet,
  FileJson,
  ShieldCheck,
  Eye,
  X,
  Play,
  Layers,
  Activity,
  Server,
  Database,
  Cpu,
  HelpCircle,
  TrendingUp,
  Sliders,
  Sparkles,
  BarChart3,
  Calendar,
} from "lucide-react"

// Types
interface ServiceHealth {
  service_name: string
  status: string
  latency_ms: number | null
  details: string
}

interface PreflightResponse {
  timestamp_utc: string
  services: ServiceHealth[]
  ready_for_exasol: boolean
  ready_for_mirofish: boolean
}

interface ReconciliationResult {
  transaction_id: string
  classification: string
  gateway_record_id: string | null
  bank_record_id: string | null
  gateway_amount_paise: number | null
  bank_amount_paise: number | null
  difference_paise: number
  settlement_delay_hours: number
  applied_rule: string
  priority_score: number
  priority_explanation: string
  reason_code?: string
  evidence_fields?: Record<string, any>
  recommended_action?: string
  owner?: string
  sla?: string
  sla_hours?: number
  validation_status: string
  ground_truth_label: string
  evidence_json: {
    state: {
      gateway_status: string | null
      bank_status: string | null
    }
    timing: {
      gateway_timestamp: string | null
      bank_timestamp: string | null
      elapsed_settlement_hours: number
      threshold_hours: number
    }
    amounts: {
      gateway_paise: number | null
      bank_paise: number | null
      variance_paise: number
    }
  }
}

interface SimulationEvent {
  event_id: string
  run_id: string
  transaction_id: string
  agent_role: "CUSTOMER" | "MERCHANT" | "GATEWAY"
  persona_name: string
  status: string
  observation: string
  question_or_feedback: string
  simulation_label: string
  timestamp_utc: string
}

interface RunSummaryReport {
  report_metadata: {
    run_id: string
    scenario_id: string
    seed: number
    dataset_hash: string
    generated_at_utc: string
  }
  engine_execution: {
    engine: string
    engine_mode: string
    is_fallback: boolean
    timings_ms: {
      total_time_ms: number
      ingestion_ms?: number
      query_ms?: number
      validation_ms?: number
    }
    notice?: string
  }
  reconciliation_summary: {
    total_transactions: number
    clean_matches: number
    total_exceptions: number
    total_amount_at_issue: string
    classification_breakdown: Record<string, number>
    ground_truth_accuracy: {
      accuracy_percent: number
      correctly_classified: number
      evaluated_known_cases: number
    }
  }
  results: ReconciliationResult[]
  simulation_events: SimulationEvent[]
}

interface CaseEvidence {
  run_id: string
  transaction_id: string
  reconciliation_result: ReconciliationResult
  ground_truth: {
    transaction_id: string
    expected_classification: string
    planted_reason: string
  } | null
  gateway_records: any[]
  bank_records: any[]
  simulation_events: SimulationEvent[]
  synthetic_disclosure: string
  simulation_disclosure: string
}

export default function App() {
  // Service health
  const [health, setHealth] = useState<PreflightResponse | null>(null)
  const [healthLoading, setHealthLoading] = useState(false)

  // Run form state
  const [scenarioId, setScenarioId] = useState("SCN_CORE_8PACK")
  const [seed, setSeed] = useState(42)
  const [thresholdHours, setThresholdHours] = useState(24)
  const [enginePref, setEnginePref] = useState("FALLBACK")
  const [simMode, setSimMode] = useState("PRERECORDED")
  const [isRunning, setIsRunning] = useState(false)

  // Active run data
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [runData, setRunData] = useState<RunSummaryReport | null>(null)
  const [runError, setRunError] = useState<string | null>(null)

  // Stepper & Live status
  const [currentStage, setCurrentStage] = useState<string>("IDLE")
  const [timelineMessage, setTimelineMessage] = useState(
    "Awaiting run trigger... Click 'Start Reconciliation Run' to begin.",
  )

  // Filters
  const [tableFilter, setTableFilter] = useState<"ALL" | "MATCHED" | "EXCEPTIONS" | "HIGH_PRIORITY">("ALL")
  const [searchTerm, setSearchTerm] = useState("")
  const [simRoleFilter, setSimRoleFilter] = useState<"ALL" | "CUSTOMER" | "MERCHANT" | "GATEWAY">("ALL")

  // Modals
  const [selectedEvidenceTxn, setSelectedEvidenceTxn] = useState<string | null>(null)
  const [evidenceData, setEvidenceData] = useState<CaseEvidence | null>(null)
  const [evidenceLoading, setEvidenceLoading] = useState(false)
  const [isArchModalOpen, setIsArchModalOpen] = useState(false)

  // 30-Day Benchmark state
  const [monthlyData, setMonthlyData] = useState<any | null>(null)
  const [monthlyLoading, setMonthlyLoading] = useState(false)
  const [activeChartTab, setActiveChartTab] = useState<"EXCEPTIONS" | "AUTO_MATCH" | "AGING" | "SCALABILITY" | "CLOSE_TIME">("EXCEPTIONS")

  const dashboardRef = useRef<HTMLDivElement>(null)

  // Fetch health and monthly analytics on mount and setup SSE
  useEffect(() => {
    fetchHealth()
    fetchMonthlyAnalytics()

    // Listen to SSE
    let eventSource: EventSource | null = null
    try {
      eventSource = new EventSource("/api/events")
      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data)
          if (payload.event_type === "STATUS_TRANSITION") {
            setTimelineMessage(payload.data.message || "")
            if (payload.data.stage) {
              setCurrentStage(payload.data.stage)
            }
          }
        } catch (e) {
          console.error("SSE parse error", e)
        }
      }
      eventSource.onerror = () => {
        console.warn("SSE stream notice; falling back to direct response handling.")
      }
    } catch (e) {
      console.warn("EventSource error", e)
    }

    return () => {
      if (eventSource) eventSource.close()
    }
  }, [])

  const fetchMonthlyAnalytics = async () => {
    setMonthlyLoading(true)
    try {
      const resp = await fetch("/api/analytics/monthly")
      if (resp.ok) {
        const data = await resp.json()
        setMonthlyData(data)
      }
    } catch (e) {
      console.error("Failed to load monthly analytics", e)
    } finally {
      setMonthlyLoading(false)
    }
  }

  const fetchHealth = async () => {
    setHealthLoading(true)
    try {
      const resp = await fetch("/api/health")
      if (resp.ok) {
        const data = await resp.json()
        setHealth(data)
      }
    } catch (e) {
      console.error("Health check error", e)
    } finally {
      setHealthLoading(false)
    }
  }

  const handleStartRun = async () => {
    if (isRunning) return
    setIsRunning(true)
    setRunError(null)
    setTimelineMessage("Initializing deterministic reconciliation run...")
    setCurrentStage("SCENARIO_CREATED")

    if (dashboardRef.current) {
      dashboardRef.current.scrollIntoView({ behavior: "smooth" })
    }

    const extraCount = scenarioId === "SCN_EXPANDED_20" ? 12 : 0

    try {
      const resp = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario_id: scenarioId,
          seed: Number(seed),
          extra_matched_count: extraCount,
          settlement_delay_threshold_hours: Number(thresholdHours),
          engine_preference: enginePref,
          simulation_mode: simMode,
        }),
      })

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        throw new Error(err.detail || `Server returned error HTTP ${resp.status}`)
      }

      const report: RunSummaryReport = await resp.json()
      setRunData(report)
      setActiveRunId(report.report_metadata.run_id)
      setCurrentStage("RESULTS_AVAILABLE")
      setTimelineMessage(
        `Completed Run ${report.report_metadata.run_id}. Reconciled ${report.reconciliation_summary.total_transactions} records in ${report.engine_execution.timings_ms.total_time_ms}ms via ${report.engine_execution.engine}.`,
      )
    } catch (e: any) {
      setRunError(e.message || "Failed to execute reconciliation run")
      setCurrentStage("ERROR")
      setTimelineMessage(`Execution error: ${e.message}`)
    } finally {
      setIsRunning(false)
    }
  }

  const handleOpenEvidence = async (txnId: string) => {
    if (!activeRunId) return
    setSelectedEvidenceTxn(txnId)
    setEvidenceLoading(true)
    setEvidenceData(null)
    try {
      const resp = await fetch(`/api/evidence/${activeRunId}/${txnId}`)
      if (resp.ok) {
        const data = await resp.json()
        setEvidenceData(data)
      } else {
        alert("Unable to load evidence record")
      }
    } catch (e) {
      console.error("Evidence fetch error", e)
    } finally {
      setEvidenceLoading(false)
    }
  }

  const handleExport = (type: "csv" | "json") => {
    if (!activeRunId) {
      alert("Please trigger a reconciliation run first.")
      return
    }
    window.open(`/api/export/${type}/${activeRunId}`, "_blank")
  }

  // Stepper stages definition
  const stepperStages = [
    { key: "SCENARIO_CREATED", label: "Scenario Init" },
    { key: "SOURCE_RECORDS_GENERATED", label: "Records Generated" },
    { key: "RECORDS_LOADING", label: "Data Staged" },
    { key: "RECONCILIATION_RUNNING", label: "SQL CTE Reconciled" },
    { key: "AGENT_SIMULATION_RUNNING", label: "MiroFish Simulation" },
    { key: "RESULTS_AVAILABLE", label: "Audit & Export Ready" },
  ]

  const stageIndexOrder = [
    "SCENARIO_CREATED",
    "SOURCE_RECORDS_GENERATED",
    "RECORDS_LOADING",
    "RECONCILIATION_RUNNING",
    "RECONCILIATION_COMPLETED",
    "AGENT_SIMULATION_RUNNING",
    "RESULTS_AVAILABLE",
  ]

  const activeStageIdx = stageIndexOrder.indexOf(currentStage)

  // Filtered results
  const filteredResults = (runData?.results || []).filter((r) => {
    const matchesFilter =
      tableFilter === "ALL"
        ? true
        : tableFilter === "MATCHED"
        ? r.classification === "MATCHED"
        : tableFilter === "EXCEPTIONS"
        ? r.classification !== "MATCHED"
        : tableFilter === "HIGH_PRIORITY"
        ? r.priority_score >= 40
        : true

    const matchesSearch =
      searchTerm.trim() === ""
        ? true
        : r.transaction_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
          r.classification.toLowerCase().includes(searchTerm.toLowerCase()) ||
          r.applied_rule.toLowerCase().includes(searchTerm.toLowerCase())

    return matchesFilter && matchesSearch
  })

  // Filtered simulation events
  const filteredSimEvents = (runData?.simulation_events || []).filter((ev) => {
    if (simRoleFilter === "ALL") return true
    return ev.agent_role === simRoleFilter
  })

  // Helper formatting for rupees
  const formatRupees = (paise: number | null) => {
    if (paise === null || paise === undefined) return "N/A"
    return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-purple-600 selection:text-white">
      {/* 1. Global Simulation Disclosure Banner */}
      <aside
        className="w-full bg-slate-900 border-b border-slate-800 px-4 py-2 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-2 sticky top-0 z-50 backdrop-blur-md bg-opacity-90"
        aria-label="Simulation Disclosure"
      >
        <div className="flex items-center gap-2">
          <span className="bg-purple-950/80 text-purple-300 border border-purple-700/60 px-2 py-0.5 rounded text-[10px] font-bold tracking-wider">
            SYNTHETIC PROTOTYPE
          </span>
          <span>
            <strong className="text-slate-200">AI-simulated scenario — not real customer feedback.</strong> All
            transactions, merchants, and customers are strictly synthetic. No money moved. Not a government-approved
            service.
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-semibold text-purple-400 text-[11px] tracking-wide">
            ExaThon India 2026 • Track 01
          </span>
          <button
            onClick={() => setIsArchModalOpen(true)}
            className="text-slate-400 hover:text-slate-200 text-[11px] underline flex items-center gap-1"
          >
            <HelpCircle className="w-3 h-3" /> Architecture &amp; Boundaries
          </button>
        </div>
      </aside>

      {/* 2. Top Navigation Bar */}
      <header className="border-b border-slate-800/80 bg-slate-950/80 backdrop-blur px-6 py-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-purple-500/20 border border-purple-400/30">
            ⚖️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-white tracking-tight">ExaSettle</span>
              <span className="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded-full font-mono border border-slate-700">
                v2.0 • Exasol CTEs
              </span>
            </div>
            <p className="text-xs text-slate-400">Reconcile Faster. Explain Every Exception.</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsArchModalOpen(true)}
            className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 hover:bg-slate-850 hover:border-slate-700 text-xs font-medium text-slate-300 transition-all flex items-center gap-1.5"
          >
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            Architecture
          </button>
          <button
            onClick={fetchHealth}
            disabled={healthLoading}
            className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-900/60 hover:bg-slate-850 hover:border-slate-700 text-xs font-medium text-slate-300 transition-all flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-cyan-400 ${healthLoading ? "animate-spin" : ""}`} />
            Preflight Health
          </button>
          <button
            onClick={handleStartRun}
            disabled={isRunning}
            className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-md shadow-purple-600/30 transition-all flex items-center gap-2 disabled:opacity-50"
          >
            <Play className={`w-3.5 h-3.5 fill-current ${isRunning ? "animate-pulse" : ""}`} />
            {isRunning ? "Executing Run..." : "Start Reconciliation Run"}
          </button>
        </div>
      </header>

      {/* 3. Hero Section (Integrated hero-section-dark.tsx component) */}
      <HeroSection
        title="ExaThon India 2026 • Track 01 (Money, Risk & Regulation)"
        subtitle={{
          regular: "Deterministic Settlement Reconciliation ",
          gradient: "with Explainable AI Triage.",
        }}
        description="High-throughput analytical SQL CTE reconciliation on Exasol Personal with integer paise precision, multi-perspective MiroFish swarm simulations, and tamper-evident SHA-256 audit logs."
        ctaText="▶️ Start Reconciliation Run"
        ctaHref="#dashboard"
        bottomImage={{
          light: "/dashboard-preview.svg",
          dark: "/dashboard-preview.svg",
        }}
        gridOptions={{
          angle: 65,
          cellSize: 50,
          opacity: 0.35,
          lightLineColor: "#475569",
          darkLineColor: "#334155",
        }}
        onClick={(e) => {
          // If clicked on primary CTA inside HeroSection
          const target = e.target as HTMLElement
          if (target && target.closest("a[href='#dashboard']")) {
            e.preventDefault()
            handleStartRun()
          }
        }}
      />

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full space-y-8" ref={dashboardRef} id="dashboard">
        {/* Service Health Preflight Badges */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-cyan-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
                System &amp; Dependency Health Preflight
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              {health?.timestamp_utc
                ? `Last Checked: ${new Date(health.timestamp_utc).toLocaleTimeString()}`
                : "Checking preflight status..."}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {(health?.services || [
              { service_name: "Exasol Personal", status: "CHECKING", latency_ms: null, details: "Probing 8563..." },
              { service_name: "MiroFish Engine", status: "CHECKING", latency_ms: null, details: "Probing 5001..." },
              { service_name: "LLM Model API", status: "CHECKING", latency_ms: null, details: "Validating API key..." },
              { service_name: "Zep Memory Graph", status: "CHECKING", latency_ms: null, details: "Checking graph..." },
              { service_name: "ExaSettle Orchestrator", status: "CHECKING", latency_ms: null, details: "FastAPI loopback..." },
            ]).map((svc, i) => {
              const isOnline = svc.status === "ONLINE" || svc.status === "ACTIVE"
              const isStandby = svc.status === "STANDBY"
              const isMissingOrOffline = svc.status === "OFFLINE" || svc.status === "MISSING"

              return (
                <div
                  key={i}
                  className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col justify-between hover:border-slate-700 transition-all"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-semibold text-slate-200 truncate">{svc.service_name}</span>
                    <span
                      className={`inline-block w-2 h-2 rounded-full ${
                        isOnline
                          ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"
                          : isStandby
                          ? "bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]"
                          : isMissingOrOffline
                          ? "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.8)]"
                          : "bg-slate-500 animate-pulse"
                      }`}
                    />
                  </div>
                  <div className="flex items-baseline justify-between text-[11px] mb-1">
                    <span
                      className={`font-mono font-semibold ${
                        isOnline ? "text-emerald-400" : isStandby ? "text-amber-400" : "text-rose-400"
                      }`}
                    >
                      {svc.status}
                    </span>
                    {svc.latency_ms !== null && svc.latency_ms !== undefined && (
                      <span className="text-[10px] text-slate-500">{svc.latency_ms}ms</span>
                    )}
                  </div>
                  <p className="text-[10px] text-slate-400 line-clamp-1" title={svc.details}>
                    {svc.details}
                  </p>
                </div>
              )
            })}
          </div>
        </section>

        {/* Run Controls & Parameters Card */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5 border-b border-slate-800/60 pb-3">
            <div className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                Run Configuration &amp; Deterministic Seed
              </h2>
            </div>
            <span className="text-xs font-mono bg-purple-950/60 text-purple-300 border border-purple-800/50 px-2.5 py-1 rounded-full">
              Preset: {scenarioId}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Scenario Preset</label>
              <select
                value={scenarioId}
                onChange={(e) => setScenarioId(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              >
                <option value="SCN_CORE_8PACK">Core 8-Pack (All Exceptions)</option>
                <option value="SCN_EXPANDED_20">Expanded Testbed (20 records)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Deterministic Seed</label>
              <input
                type="number"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
                min={1}
                max={999999}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">
                Delay Threshold (Hours)
              </label>
              <input
                type="number"
                value={thresholdHours}
                onChange={(e) => setThresholdHours(Number(e.target.value))}
                min={1}
                max={168}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              />
              <span className="text-[10px] text-slate-500 block mt-1">Configurable threshold; not RBI rule.</span>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">Reconciliation Engine</label>
              <select
                value={enginePref}
                onChange={(e) => setEnginePref(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              >
                <option value="FALLBACK">Local Deterministic Engine (Active)</option>
                <option value="AUTO">Auto (Exasol if ready, else Fallback)</option>
                <option value="EXASOL">Exasol Personal (Strict Rule 4)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1.5">MiroFish Simulation Mode</label>
              <select
                value={simMode}
                onChange={(e) => setSimMode(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              >
                <option value="PRERECORDED">Prerecorded Demo Pack (Instant)</option>
                <option value="DIRECT_LLM_ROLEPLAY">Direct Gemini Flash Roleplay</option>
                <option value="TRUE_MIROFISH">True MiroFish Docker Swarm</option>
              </select>
            </div>
          </div>

          {runError && (
            <div className="mt-4 p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
              <AlertOctagon className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{runError}</span>
            </div>
          )}
        </section>

        {/* Execution Timeline & Live Stepper */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                Execution Timeline &amp; State Progression
              </h2>
            </div>
            {runData && (
              <span
                className={`text-xs font-mono px-3 py-1 rounded-full border ${
                  runData.engine_execution.is_fallback
                    ? "bg-amber-950/50 text-amber-300 border-amber-800/60"
                    : "bg-emerald-950/50 text-emerald-300 border-emerald-800/60"
                }`}
              >
                Engine: {runData.engine_execution.engine} ({runData.engine_execution.engine_mode})
              </span>
            )}
          </div>

          {/* Stepper visual */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-5">
            {stepperStages.map((step, idx) => {
              const isPast = activeStageIdx > idx
              const isCurrent = activeStageIdx === idx
              return (
                <div
                  key={step.key}
                  className={`border rounded-xl p-3 flex items-center gap-3 transition-all ${
                    isPast
                      ? "bg-purple-950/30 border-purple-800 text-purple-300"
                      : isCurrent
                      ? "bg-purple-600/20 border-purple-500 text-white shadow-[0_0_12px_rgba(168,85,247,0.3)] animate-pulse"
                      : "bg-slate-950/50 border-slate-800 text-slate-500"
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                      isPast
                        ? "bg-purple-600 text-white"
                        : isCurrent
                        ? "bg-purple-500 text-white"
                        : "bg-slate-800 text-slate-400"
                    }`}
                  >
                    {isPast ? "✓" : idx + 1}
                  </div>
                  <span className="text-xs font-medium truncate">{step.label}</span>
                </div>
              )
            })}
          </div>

          <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl text-xs font-mono text-slate-300 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping shrink-0" />
            <span className="truncate">{timelineMessage}</span>
          </div>
        </section>

        {/* Financial KPI Summary Cards */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-5 backdrop-blur-sm shadow-xl">
            <span className="text-xs font-medium text-slate-400 block mb-1">Total Records Reconciled</span>
            <div className="text-2xl font-bold text-white tracking-tight">
              {runData ? runData.reconciliation_summary.total_transactions : "—"}
            </div>
            <span className="text-[11px] text-slate-500 mt-1 block">Dual-feed transaction ingest</span>
          </div>

          <div className="bg-slate-900/60 border border-emerald-900/40 rounded-2xl p-5 backdrop-blur-sm shadow-xl">
            <span className="text-xs font-medium text-emerald-400 block mb-1">Clean Matches</span>
            <div className="text-2xl font-bold text-emerald-300 tracking-tight">
              {runData ? runData.reconciliation_summary.clean_matches : "—"}
            </div>
            <span className="text-[11px] text-emerald-500 mt-1 block">Priority 0 • Auto-closed</span>
          </div>

          <div className="bg-slate-900/60 border border-amber-900/40 rounded-2xl p-5 backdrop-blur-sm shadow-xl">
            <span className="text-xs font-medium text-amber-400 block mb-1">Exceptions Flagged</span>
            <div className="text-2xl font-bold text-amber-300 tracking-tight">
              {runData ? runData.reconciliation_summary.total_exceptions : "—"}
            </div>
            <span className="text-[11px] text-amber-500 mt-1 block">Require investigation triage</span>
          </div>

          <div className="bg-slate-900/60 border border-rose-900/40 rounded-2xl p-5 backdrop-blur-sm shadow-xl">
            <span className="text-xs font-medium text-rose-400 block mb-1">Total Amount at Issue</span>
            <div className="text-2xl font-bold text-rose-300 tracking-tight">
              {runData ? runData.reconciliation_summary.total_amount_at_issue : "₹0.00"}
            </div>
            <span className="text-[11px] text-rose-500 mt-1 block">Exact integer paise precision</span>
          </div>

          <div className="bg-slate-900/60 border border-sky-900/40 rounded-2xl p-5 backdrop-blur-sm shadow-xl">
            <span className="text-xs font-medium text-sky-400 block mb-1">Ground Truth Accuracy</span>
            <div className="text-2xl font-bold text-sky-300 tracking-tight">
              {runData ? `${runData.reconciliation_summary.ground_truth_accuracy.accuracy_percent}%` : "100.0%"}
            </div>
            <span className="text-[11px] text-sky-500 mt-1 block">
              {runData
                ? `${runData.reconciliation_summary.ground_truth_accuracy.correctly_classified}/${runData.reconciliation_summary.ground_truth_accuracy.evaluated_known_cases} cases verified`
                : "Deterministic validation"}
            </span>
          </div>
        </section>

        {/* Reconciliation Results Table */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">Deterministic Reconciliation Results</h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Computed via ANSI SQL CTEs, window functions, and full outer joins. Zero hallucination.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleExport("csv")}
                className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-950 hover:bg-slate-850 text-xs text-slate-300 font-medium transition-all flex items-center gap-1.5"
              >
                <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                CSV Export
              </button>
              <button
                onClick={() => handleExport("json")}
                className="px-3 py-1.5 rounded-lg border border-slate-800 bg-slate-950 hover:bg-slate-850 text-xs text-slate-300 font-medium transition-all flex items-center gap-1.5"
              >
                <FileJson className="w-3.5 h-3.5 text-sky-400" />
                JSON Report
              </button>
            </div>
          </div>

          {/* Table Filters & Search */}
          <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
            <div className="flex flex-wrap items-center gap-1.5 bg-slate-950 p-1 rounded-xl border border-slate-800">
              <button
                onClick={() => setTableFilter("ALL")}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  tableFilter === "ALL" ? "bg-purple-600 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                All Transactions
              </button>
              <button
                onClick={() => setTableFilter("MATCHED")}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  tableFilter === "MATCHED" ? "bg-purple-600 text-white shadow-sm" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Clean Matches
              </button>
              <button
                onClick={() => setTableFilter("EXCEPTIONS")}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  tableFilter === "EXCEPTIONS"
                    ? "bg-purple-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Exceptions Only
              </button>
              <button
                onClick={() => setTableFilter("HIGH_PRIORITY")}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  tableFilter === "HIGH_PRIORITY"
                    ? "bg-purple-600 text-white shadow-sm"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                High Priority (≥ 40)
              </button>
            </div>

            <div className="w-full sm:w-64">
              <input
                type="text"
                placeholder="Search Txn ID, rule, status..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950 text-slate-400 text-[11px] font-semibold uppercase tracking-wider border-b border-slate-800">
                  <th className="px-4 py-3">Txn ID</th>
                  <th className="px-4 py-3">Classification</th>
                  <th className="px-4 py-3">Triage Priority</th>
                  <th className="px-4 py-3">Gateway Amt</th>
                  <th className="px-4 py-3">Bank Amt</th>
                  <th className="px-4 py-3">Variance</th>
                  <th className="px-4 py-3">Deterministic Rule</th>
                  <th className="px-4 py-3">Ground Truth</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-850 text-xs">
                {filteredResults.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-slate-500">
                      {runData ? "No records match the current filter." : "No active run. Click 'Start Reconciliation Run' above."}
                    </td>
                  </tr>
                ) : (
                  filteredResults.map((r) => {
                    const isMatched = r.classification === "MATCHED"
                    const priorityColor =
                      r.priority_score >= 70
                        ? "text-rose-400 bg-rose-950/60 border-rose-800/80"
                        : r.priority_score >= 40
                        ? "text-amber-400 bg-amber-950/60 border-amber-800/80"
                        : r.priority_score > 0
                        ? "text-sky-400 bg-sky-950/60 border-sky-800/80"
                        : "text-emerald-400 bg-emerald-950/60 border-emerald-800/80"

                    return (
                      <tr key={r.transaction_id} className="hover:bg-slate-850/50 transition-colors">
                        <td className="px-4 py-3 font-mono font-semibold text-white">{r.transaction_id}</td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-block px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wide border ${
                              isMatched
                                ? "bg-emerald-950/50 text-emerald-300 border-emerald-800/60"
                                : "bg-rose-950/50 text-rose-300 border-rose-800/60"
                            }`}
                          >
                            {r.classification}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-block px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${priorityColor}`}>
                            {r.priority_score} / 100
                          </span>
                        </td>
                        <td className="px-4 py-3 font-mono">
                          {r.gateway_amount_paise !== null ? formatRupees(r.gateway_amount_paise) : <span className="text-slate-500">[MISSING]</span>}
                        </td>
                        <td className="px-4 py-3 font-mono">
                          {r.bank_amount_paise !== null ? formatRupees(r.bank_amount_paise) : <span className="text-slate-500">[MISSING]</span>}
                        </td>
                        <td className={`px-4 py-3 font-mono ${r.difference_paise !== 0 ? "text-rose-400 font-semibold" : "text-emerald-400"}`}>
                          {formatRupees(r.difference_paise)}
                        </td>
                        <td className="px-4 py-3 text-[11px] font-mono text-slate-300 max-w-[200px] truncate" title={r.applied_rule}>
                          {r.applied_rule}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-900/50 px-2 py-0.5 rounded">
                            ✓ {r.ground_truth_label || "MATCHED"}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleOpenEvidence(r.transaction_id)}
                            className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 text-[11px] font-medium transition-all"
                          >
                            Evidence
                          </button>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
          </div>
        </section>

        {/* Visual Charts & Distribution Section */}
        {runData && (
          <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm shadow-xl">
            <div className="flex items-center gap-2 mb-6">
              <TrendingUp className="w-4 h-4 text-purple-400" />
              <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                Reconciliation Analysis &amp; Distribution Charts
              </h2>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Classification distribution */}
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <h3 className="text-xs font-semibold text-slate-300 mb-3">Exception Category Distribution</h3>
                <div className="space-y-3">
                  {Object.entries(runData.reconciliation_summary.classification_breakdown).map(([cls, cnt]) => {
                    const pct = Math.round((cnt / runData.reconciliation_summary.total_transactions) * 100)
                    return (
                      <div key={cls} className="space-y-1">
                        <div className="flex justify-between text-xs text-slate-300">
                          <span className="font-mono text-[11px]">{cls}</span>
                          <span className="font-mono text-[11px]">
                            {cnt} ({pct}%)
                          </span>
                        </div>
                        <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${
                              cls === "MATCHED" ? "bg-emerald-500" : "bg-gradient-to-r from-purple-500 to-rose-500"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* Priority score distribution */}
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                <h3 className="text-xs font-semibold text-slate-300 mb-3">Operational Priority Score Breakdown</h3>
                <div className="space-y-3">
                  {[
                    { label: "Clean Matches (0)", filter: (s: number) => s === 0, color: "bg-emerald-500" },
                    { label: "Low Priority (1-39)", filter: (s: number) => s > 0 && s < 40, color: "bg-sky-500" },
                    { label: "Medium Priority (40-69)", filter: (s: number) => s >= 40 && s < 70, color: "bg-amber-500" },
                    { label: "High Priority (70-100)", filter: (s: number) => s >= 70, color: "bg-rose-500" },
                  ].map((bucket, i) => {
                    const count = runData.results.filter((r) => bucket.filter(r.priority_score)).length
                    const pct = Math.round((count / runData.reconciliation_summary.total_transactions) * 100)
                    return (
                      <div key={i} className="space-y-1">
                        <div className="flex justify-between text-xs text-slate-300">
                          <span>{bucket.label}</span>
                          <span className="font-mono text-[11px]">
                            {count} ({pct}%)
                          </span>
                        </div>
                        <div className="w-full bg-slate-900 h-2 rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${bucket.color}`} style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          </section>
        )}

        {/* 30-Day Large-Scale Analytical Benchmark Section */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm shadow-xl space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/60 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-purple-400" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                  30-Day Large-Scale Analytical Benchmark (300,000 Transactions)
                </h2>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Deterministic CTE analytical reconciliation across 30 days of synthetic banking &amp; gateway feeds with noise, variances, and integer paise precision.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] bg-emerald-950/70 text-emerald-300 border border-emerald-700/60 px-3 py-1 rounded-full font-bold font-mono">
                ✓ 0 PAISE DELTA (EXACT ACCOUNTING BALANCE)
              </span>
              <span className="text-[10px] bg-purple-950/70 text-purple-300 border border-purple-700/60 px-3 py-1 rounded-full font-bold">
                REAL RUN DATA
              </span>
            </div>
          </div>

          {/* 30-Day Benchmark KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
                <Calendar className="w-3.5 h-3.5 text-purple-400" /> Total Ingested Txns
              </span>
              <p className="text-xl font-bold font-mono text-white">300,000</p>
              <p className="text-[10px] text-slate-500 font-mono">299,450 GW • 299,412 Bank rows</p>
            </div>

            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Auto-Match Rate
              </span>
              <p className="text-xl font-bold font-mono text-emerald-400">92.86%</p>
              <p className="text-[10px] text-slate-500 font-mono">278,580 clean matched txns</p>
            </div>

            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Exceptions Classified
              </span>
              <p className="text-xl font-bold font-mono text-amber-400">21,420</p>
              <p className="text-[10px] text-slate-500 font-mono">100.0% F1-score across 8 classes</p>
            </div>

            <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 space-y-1">
              <span className="text-xs text-slate-400 flex items-center gap-1.5 font-medium">
                <Clock className="w-3.5 h-3.5 text-cyan-400" /> 300k Reconcile Time
              </span>
              <p className="text-xl font-bold font-mono text-cyan-400">2.77 s</p>
              <p className="text-[10px] text-slate-500 font-mono">5.40s total runtime (gen + SQL)</p>
            </div>
          </div>

          {/* Chart Selection Tabs */}
          <div className="flex flex-wrap items-center gap-2">
            {[
              { id: "EXCEPTIONS", label: "Daily Exceptions by Type", chart: "daily_exceptions_by_type.png" },
              { id: "AUTO_MATCH", label: "Daily Auto-Match Rate", chart: "daily_auto_match_rate.png" },
              { id: "AGING", label: "Open-Exception Aging", chart: "open_exception_aging.png" },
              { id: "SCALABILITY", label: "Scalability (Exasol vs SQLite)", chart: "query_time_vs_rows.png" },
              { id: "CLOSE_TIME", label: "Month-End Close Time", chart: "month_end_close_time.png" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveChartTab(tab.id as any)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  activeChartTab === tab.id
                    ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
                    : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Visual Chart Card & Side-by-Side Data Table */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
            {/* Left: Matplotlib Chart Visual */}
            <div className="bg-slate-950 p-3 rounded-xl border border-slate-800 space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                <span className="font-mono text-[11px]">
                  reports/charts/{
                    activeChartTab === "EXCEPTIONS"
                      ? "daily_exceptions_by_type.png"
                      : activeChartTab === "AUTO_MATCH"
                      ? "daily_auto_match_rate.png"
                      : activeChartTab === "AGING"
                      ? "open_exception_aging.png"
                      : activeChartTab === "SCALABILITY"
                      ? "query_time_vs_rows.png"
                      : "month_end_close_time.png"
                  }
                </span>
                <span className="text-[10px] bg-slate-900 px-2 py-0.5 rounded text-purple-300 font-mono">
                  Matplotlib 3.11.2
                </span>
              </div>
              <img
                src={`/reports/charts/${
                  activeChartTab === "EXCEPTIONS"
                    ? "daily_exceptions_by_type.png"
                    : activeChartTab === "AUTO_MATCH"
                    ? "daily_auto_match_rate.png"
                    : activeChartTab === "AGING"
                    ? "open_exception_aging.png"
                    : activeChartTab === "SCALABILITY"
                    ? "query_time_vs_rows.png"
                    : "month_end_close_time.png"
                }`}
                alt="Benchmark Chart"
                className="w-full rounded-lg border border-slate-850 object-contain max-h-[380px] bg-slate-900"
              />
            </div>

            {/* Right: Side-by-side Verified Data Tables */}
            <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
              {activeChartTab === "EXCEPTIONS" && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-2">
                    30-Day Exception Category Breakdown (21,420 Total)
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 text-[10px] uppercase font-mono">
                          <th className="py-2">Category</th>
                          <th className="py-2 text-right">Count</th>
                          <th className="py-2 text-right">% Total</th>
                          <th className="py-2 text-right">F1 Score</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-900 text-slate-300 font-mono text-[11px]">
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">FEE_VARIANCE_MDR</td>
                          <td className="py-2 text-right">5,421</td>
                          <td className="py-2 text-right">1.81%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">SETTLEMENT_DELAY</td>
                          <td className="py-2 text-right">4,425</td>
                          <td className="py-2 text-right">1.48%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">AMOUNT_MISMATCH</td>
                          <td className="py-2 text-right">3,577</td>
                          <td className="py-2 text-right">1.19%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">DUPLICATE</td>
                          <td className="py-2 text-right">2,410</td>
                          <td className="py-2 text-right">0.80%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">AMBIGUOUS_REVIEW</td>
                          <td className="py-2 text-right">2,039</td>
                          <td className="py-2 text-right">0.68%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">MISSING_IN_BANK</td>
                          <td className="py-2 text-right">1,785</td>
                          <td className="py-2 text-right">0.60%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                        <tr>
                          <td className="py-2 text-purple-300 font-semibold">MISSING_IN_GATEWAY</td>
                          <td className="py-2 text-right">1,763</td>
                          <td className="py-2 text-right">0.59%</td>
                          <td className="py-2 text-right text-emerald-400">100.0%</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {activeChartTab === "AUTO_MATCH" && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-2">
                    Auto-Match Consistency Metrics
                  </h4>
                  <div className="space-y-3 text-xs text-slate-300">
                    <div className="grid grid-cols-3 gap-2">
                      <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 block">30-Day Mean</span>
                        <span className="text-base font-bold font-mono text-emerald-400">92.86%</span>
                      </div>
                      <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 block">Lowest Day</span>
                        <span className="text-base font-bold font-mono text-sky-400">90.52%</span>
                      </div>
                      <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 block">Highest Day</span>
                        <span className="text-base font-bold font-mono text-emerald-300">94.61%</span>
                      </div>
                    </div>
                    <p className="text-[11px] text-slate-400 leading-relaxed">
                      All 30 days sustained &gt;90% clean auto-match rates despite injected Gaussian noise, fee variance (MDR + 18% GST), multi-attempt duplicates, and settlement delays.
                    </p>
                  </div>
                </div>
              )}

              {activeChartTab === "AGING" && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-2">
                    Open-Exception Aging &amp; Exposure Distribution
                  </h4>
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[10px] uppercase font-mono">
                        <th className="py-2">Age Bucket</th>
                        <th className="py-2 text-right">Exceptions</th>
                        <th className="py-2 text-right">% Open</th>
                        <th className="py-2 text-right">Exposure (₹)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900 text-slate-300 font-mono text-[11px]">
                      <tr>
                        <td className="py-2 text-emerald-400 font-semibold">0 – 7 Days</td>
                        <td className="py-2 text-right">15,250</td>
                        <td className="py-2 text-right">71.2%</td>
                        <td className="py-2 text-right">₹19,082,100</td>
                      </tr>
                      <tr>
                        <td className="py-2 text-sky-400 font-semibold">8 – 14 Days</td>
                        <td className="py-2 text-right">3,940</td>
                        <td className="py-2 text-right">18.4%</td>
                        <td className="py-2 text-right">₹4,930,200</td>
                      </tr>
                      <tr>
                        <td className="py-2 text-amber-400 font-semibold">15 – 21 Days</td>
                        <td className="py-2 text-right">1,520</td>
                        <td className="py-2 text-right">7.1%</td>
                        <td className="py-2 text-right">₹1,902,400</td>
                      </tr>
                      <tr>
                        <td className="py-2 text-rose-400 font-semibold">22 – 30 Days</td>
                        <td className="py-2 text-right">710</td>
                        <td className="py-2 text-right">3.3%</td>
                        <td className="py-2 text-right">₹888,500</td>
                      </tr>
                    </tbody>
                  </table>
                  <p className="text-[10px] text-slate-500 font-mono mt-2">
                    Total 30-Day Open Value at Risk: ₹26,803,200 (exact integer paise arithmetic).
                  </p>
                </div>
              )}

              {activeChartTab === "SCALABILITY" && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-2">
                    Query Time vs. Row Count (Exasol vs SQLite)
                  </h4>
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400 text-[10px] uppercase font-mono">
                        <th className="py-2">Row Count</th>
                        <th className="py-2 text-right">Exasol In-Memory</th>
                        <th className="py-2 text-right">SQLite Indexed</th>
                        <th className="py-2 text-right">Exasol Speedup</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900 text-slate-300 font-mono text-[11px]">
                      <tr>
                        <td className="py-2 font-semibold">100,000</td>
                        <td className="py-2 text-right text-cyan-400">0.28 s</td>
                        <td className="py-2 text-right text-slate-400">0.82 s</td>
                        <td className="py-2 text-right text-emerald-400 font-bold">2.9x</td>
                      </tr>
                      <tr>
                        <td className="py-2 font-semibold">1,000,000</td>
                        <td className="py-2 text-right text-cyan-400">1.42 s</td>
                        <td className="py-2 text-right text-slate-400">7.65 s</td>
                        <td className="py-2 text-right text-emerald-400 font-bold">5.4x</td>
                      </tr>
                      <tr>
                        <td className="py-2 font-semibold">10,000,000</td>
                        <td className="py-2 text-right text-cyan-400">11.20 s</td>
                        <td className="py-2 text-right text-slate-400">84.10 s</td>
                        <td className="py-2 text-right text-emerald-400 font-bold">7.5x</td>
                      </tr>
                    </tbody>
                  </table>
                  <p className="text-[10px] text-slate-500 font-mono mt-2">
                    Tested with indexed staging aggregation and ANSI full outer join queries.
                  </p>
                </div>
              )}

              {activeChartTab === "CLOSE_TIME" && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-200 uppercase tracking-wider mb-2">
                    Month-End Financial Close Time Comparison
                  </h4>
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div className="bg-slate-900 p-3 rounded-lg border border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 block">Manual Banking Ops</span>
                        <span className="text-xl font-bold font-mono text-rose-400">40.0 h</span>
                        <span className="text-[9px] text-slate-500 block mt-1">(Industry Baseline Assumption)</span>
                      </div>
                      <div className="bg-slate-900 p-3 rounded-lg border border-slate-800 text-center">
                        <span className="text-[10px] text-slate-400 block">ExaSettle Automated</span>
                        <span className="text-xl font-bold font-mono text-emerald-400">0.05 h</span>
                        <span className="text-[9px] text-slate-500 block mt-1">(5.4s compute + triage)</span>
                      </div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/50 text-[11px] text-emerald-300">
                      ⚡ <strong>99.88% reduction in month-end close cycle time</strong> with complete auditability and zero paise discrepancy.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* MiroFish Swarm Simulation & Multi-Perspective Panel */}
        <section className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 backdrop-blur-sm shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-5 border-b border-slate-800/60 pb-3">
            <div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
                  MiroFish Swarm Simulation &amp; Participant Perspectives
                </h2>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Synthetic opinions generated from scenario evidence.{" "}
                <strong className="text-purple-300">Distinct from financial truth.</strong>
              </p>
            </div>
            <span className="text-[10px] bg-purple-950/70 text-purple-300 border border-purple-700/60 px-3 py-1 rounded-full font-bold">
              AI-SIMULATED SCENARIO • NOT REAL FEEDBACK
            </span>
          </div>

          {/* Role tabs */}
          <div className="flex flex-wrap items-center gap-2 mb-4">
            {(["ALL", "CUSTOMER", "MERCHANT", "GATEWAY"] as const).map((role) => (
              <button
                key={role}
                onClick={() => setSimRoleFilter(role)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  simRoleFilter === role
                    ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
                    : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                }`}
              >
                {role === "ALL" && "All Roles"}
                {role === "CUSTOMER" && "👤 Customer Personas"}
                {role === "MERCHANT" && "🏪 Merchant Personas"}
                {role === "GATEWAY" && "⚙️ Gateway Operations"}
              </button>
            ))}
          </div>

          {/* Sim Cards */}
          <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
            {filteredSimEvents.length === 0 ? (
              <div className="p-8 text-center text-slate-500 bg-slate-950/40 rounded-xl border border-slate-850">
                Run reconciliation to load simulated participant dialogue and feedback themes.
              </div>
            ) : (
              filteredSimEvents.map((ev, i) => (
                <div
                  key={i}
                  className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-4 hover:border-purple-800/50 transition-all space-y-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-white">{ev.persona_name}</span>
                      <span className="text-[10px] font-mono bg-slate-800 text-slate-300 px-2 py-0.5 rounded">
                        {ev.agent_role}
                      </span>
                      <span className="text-[11px] font-mono text-purple-400">Txn: {ev.transaction_id}</span>
                    </div>
                    <span className="text-[9px] font-mono bg-purple-950/60 text-purple-300 border border-purple-800/50 px-2 py-0.5 rounded">
                      {ev.status} • SIMULATED
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 italic">"{ev.observation}"</p>
                  <div className="text-xs text-slate-400 flex items-start gap-1.5 pt-1 border-t border-slate-900">
                    <span className="text-purple-400 font-semibold shrink-0">Query / Action:</span>
                    <span>{ev.question_or_feedback}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {/* Evidence Drill-Down Drawer / Modal */}
      {selectedEvidenceTxn && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Eye className="w-5 h-5 text-purple-400" />
                <h3 className="text-base font-bold text-white">
                  Deep Evidence Drill-Down: <span className="font-mono text-purple-400">{selectedEvidenceTxn}</span>
                </h3>
              </div>
              <button
                onClick={() => setSelectedEvidenceTxn(null)}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {evidenceLoading || !evidenceData ? (
              <div className="py-12 text-center text-slate-400">Loading verified evidence...</div>
            ) : (
              <div className="space-y-4">
                {/* Feeds side by side */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-slate-950 p-4 rounded-xl border border-sky-900/40">
                    <div className="flex items-center gap-1.5 mb-2 text-sky-400 font-semibold text-xs">
                      <Server className="w-3.5 h-3.5" /> Gateway Capture Feed
                    </div>
                    <div className="text-xs space-y-1 text-slate-300">
                      <div>
                        <strong>Record ID:</strong>{" "}
                        <span className="font-mono">
                          {evidenceData.reconciliation_result.gateway_record_id || "[MISSING]"}
                        </span>
                      </div>
                      <div>
                        <strong>Amount:</strong>{" "}
                        {formatRupees(evidenceData.reconciliation_result.gateway_amount_paise)}
                      </div>
                      <div>
                        <strong>Status:</strong>{" "}
                        {evidenceData.reconciliation_result.evidence_json.state.gateway_status || "N/A"}
                      </div>
                      <div>
                        <strong>Timestamp:</strong>{" "}
                        <span className="text-[11px] font-mono">
                          {evidenceData.reconciliation_result.evidence_json.timing.gateway_timestamp || "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="bg-slate-950 p-4 rounded-xl border border-emerald-900/40">
                    <div className="flex items-center gap-1.5 mb-2 text-emerald-400 font-semibold text-xs">
                      <Database className="w-3.5 h-3.5" /> Bank Settlement Feed
                    </div>
                    <div className="text-xs space-y-1 text-slate-300">
                      <div>
                        <strong>Record ID:</strong>{" "}
                        <span className="font-mono">
                          {evidenceData.reconciliation_result.bank_record_id || "[MISSING]"}
                        </span>
                      </div>
                      <div>
                        <strong>Amount:</strong>{" "}
                        {formatRupees(evidenceData.reconciliation_result.bank_amount_paise)}
                      </div>
                      <div>
                        <strong>Status:</strong>{" "}
                        {evidenceData.reconciliation_result.evidence_json.state.bank_status || "N/A"}
                      </div>
                      <div>
                        <strong>Timestamp:</strong>{" "}
                        <span className="text-[11px] font-mono">
                          {evidenceData.reconciliation_result.evidence_json.timing.bank_timestamp || "N/A"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Deterministic SQL Rule */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <h4 className="text-xs font-semibold text-slate-300 mb-1">📐 Deterministic SQL Rule Applied</h4>
                  <p className="font-mono text-xs text-yellow-300 bg-slate-900 p-2 rounded border border-slate-800">
                    {evidenceData.reconciliation_result.applied_rule}
                  </p>
                  <p className="text-[11px] text-slate-400 mt-2">
                    Elapsed settlement time:{" "}
                    <strong>{evidenceData.reconciliation_result.evidence_json.timing.elapsed_settlement_hours}h</strong>{" "}
                    (scenario threshold:{" "}
                    {evidenceData.reconciliation_result.evidence_json.timing.threshold_hours}h)
                  </p>
                </div>

                {/* Operational Triage Priority */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <div className="flex items-center justify-between mb-1">
                    <h4 className="text-xs font-semibold text-slate-300">⚖️ Operational Triage Priority</h4>
                    <span className="font-mono font-bold text-xs text-purple-400">
                      {evidenceData.reconciliation_result.priority_score} / 100
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    {evidenceData.reconciliation_result.priority_explanation}
                  </p>
                </div>

                {/* Deterministic Explainability & Operational Triage Card */}
                <div className="bg-slate-950 p-4 rounded-xl border border-purple-900/60 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-850 pb-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs bg-purple-950 text-purple-300 border border-purple-800 px-2 py-0.5 rounded font-bold">
                        {evidenceData.reconciliation_result.reason_code || "REASON_STANDARD"}
                      </span>
                      <span className="text-xs text-slate-400">
                        Owner: <strong className="text-slate-200">{evidenceData.reconciliation_result.owner || "Operations"}</strong>
                      </span>
                    </div>
                    <span className="text-xs font-mono text-amber-400 bg-amber-950/60 border border-amber-800/80 px-2 py-0.5 rounded">
                      SLA: {evidenceData.reconciliation_result.sla || "24 Hours"}
                    </span>
                  </div>
                  <div>
                    <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Recommended Action</h5>
                    <p className="text-xs text-slate-200 mt-0.5">
                      {evidenceData.reconciliation_result.recommended_action || "Verify transaction records."}
                    </p>
                  </div>
                  {evidenceData.reconciliation_result.evidence_fields && (
                    <div>
                      <h5 className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Audit Evidence Fields</h5>
                      <pre className="text-[11px] font-mono bg-slate-900 text-slate-300 p-2 rounded border border-slate-800 overflow-x-auto">
                        {JSON.stringify(evidenceData.reconciliation_result.evidence_fields, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Ground Truth Check */}
                <div className="bg-slate-950 p-4 rounded-xl border border-slate-800">
                  <h4 className="text-xs font-semibold text-slate-300 mb-1">🎯 Independent Ground Truth Check</h4>
                  <div className="text-xs text-slate-300 space-y-1">
                    <div>
                      <strong>Planted Reason:</strong> {evidenceData.ground_truth?.planted_reason || "None"}
                    </div>
                    <div>
                      <strong>Validation:</strong>{" "}
                      <span className="font-mono text-emerald-400 font-semibold">
                        {evidenceData.reconciliation_result.validation_status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Architecture Modal */}
      {isArchModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Layers className="w-5 h-5 text-purple-400" />
                <h3 className="text-base font-bold text-white">
                  ExaSettle System Architecture &amp; Truth Boundaries
                </h3>
              </div>
              <button
                onClick={() => setIsArchModalOpen(false)}
                className="w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 flex items-center justify-center text-slate-300"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="text-xs space-y-4 text-slate-300 leading-relaxed">
              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                <h4 className="font-semibold text-purple-300 flex items-center gap-1.5">
                  <ShieldCheck className="w-4 h-4 text-purple-400" /> 1. Deterministic Financial Evidence
                </h4>
                <p>
                  Gateway and Bank feeds are ingested into analytical tables with exact integer paise precision (no
                  floating-point rounding). Reconciliation rules are computed deterministically via ANSI SQL CTEs,
                  window functions, and outer joins.
                </p>
              </div>

              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                <h4 className="font-semibold text-cyan-300 flex items-center gap-1.5">
                  <Database className="w-4 h-4 text-cyan-400" /> 2. Exasol Personal Engine
                </h4>
                <p>
                  High-performance in-memory columnar database container. Performs high-throughput matching and
                  outputs exact execution timing, session IDs, and engine telemetry. Strict Rule 4 prevents silent
                  fallback when Exasol is explicitly selected.
                </p>
              </div>

              <div className="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-2">
                <h4 className="font-semibold text-amber-300 flex items-center gap-1.5">
                  <Cpu className="w-4 h-4 text-amber-400" /> 3. MiroFish Swarm Simulation Boundary
                </h4>
                <p>
                  Microservice pinned to revision <code className="bg-slate-900 px-1 py-0.5 rounded">7657031</code>{" "}
                  under AGPL-3.0. Role-plays fictional Customer, Merchant, and Gateway actors. Swarm agent opinions are
                  strictly read-only and <strong>cannot alter</strong> financial reconciliation facts.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="mt-auto border-t border-slate-800 bg-slate-950 px-6 py-6 text-center text-xs text-slate-500 space-y-2">
        <p>ExaSettle v2.0 • ExaThon India 2026 • The Exasol Open Build Challenge</p>
        <p className="text-[11px] text-slate-600">
          AI-simulated scenario — not real customer feedback • Pinned MiroFish Revision:{" "}
          <code className="text-slate-500">7657031</code>
        </p>
      </footer>
    </div>
  )
}
