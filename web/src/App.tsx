import { useEffect, useState } from 'react'
import CyclesPanel from './CyclesPanel'
import './App.css'

type Section = 'Vue d’ensemble' | 'Cycles' | 'Données' | 'Méthodologie'

const sections: Section[] = [
  'Vue d’ensemble',
  'Cycles',
  'Données',
  'Méthodologie',
]

const navigationIcons: Record<Section, string> = {
  'Vue d’ensemble': '◫',
  'Cycles': '◎',
  'Données': '▤',
  'Méthodologie': '◇',
}

type Overview = {
  cycles: {
    count: number
    latest_created_at_utc: string | null
    latest_identity_prefix: string | null
  }
  key_rates: {
    observation_count: number
    latest_effective_date: string | null
    latest_collected_at_utc: string | null
  }
  model: {
    calibrated_to_market: boolean
    complete_portfolio_valuation: boolean
    portfolio_risk_measure: boolean
  }
}

function App() {
  const [section, setSection] = useState<Section>('Vue d’ensemble')
  const [overview, setOverview] = useState<Overview | null>(null)
  const [error, setError] = useState(false)
  const [refresh, setRefresh] = useState(0)
  const [lastChecked, setLastChecked] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()

    async function loadOverview() {
      try {
        const response = await fetch('/api/overview', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const data: Overview = await response.json()
        if (
          typeof data.cycles?.count !== 'number' ||
          typeof data.key_rates?.observation_count !== 'number' ||
          typeof data.model?.calibrated_to_market !== 'boolean'
        ) {
          throw new Error('Invalid API response')
        }

        if (!controller.signal.aborted) {
          setOverview(data)
          setError(false)
          setLastChecked(new Date().toLocaleTimeString('fr-FR'))
        }
      } catch {
        if (!controller.signal.aborted) {
          setOverview(null)
          setError(true)
          setLastChecked(null)
        }
      }
    }

    void loadOverview()
    return () => controller.abort()
  }, [refresh])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">Q<span>.</span></div>
          <div>
            <div className="brand-name">PORTFOLIO QUANT</div>
            <div className="brand-caption">RESEARCH TERMINAL</div>
          </div>
        </div>

        <div className="sidebar-label">ESPACE DE TRAVAIL</div>

        <nav className="navigation" aria-label="Navigation principale">
          {sections.map((item) => (
            <button
              key={item}
              type="button"
              className={`nav-item ${section === item ? 'active' : ''}`}
              onClick={() => setSection(item)}
              aria-current={section === item ? 'page' : undefined}
            >
              <span className="nav-icon" aria-hidden="true">
                {navigationIcons[item]}
              </span>
              {item}
              {section === item && <span className="nav-indicator" />}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-status">
            <span className="status-dot" />
            Interface locale
          </div>
          <div className="sidebar-footnote">
            Consultation uniquement
            <br />
            Aucune opération de trading
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            RESEARCH <span>/</span> {section.toUpperCase()}
          </div>
          <div className="topbar-right">
            <span className="environment-badge">ENVIRONNEMENT LOCAL</span>
            <span className="avatar" aria-label="Portfolio Quant">PQ</span>
          </div>
        </header>

        <div className="page-content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">INVESTMENT MANAGEMENT / QUANT</div>
              <h1>{section}</h1>
              <p className="page-description">
                {section === 'Vue d’ensemble'
                  ? 'Une vue claire de l’infrastructure quantitative et de ses prochaines étapes.'
                  : section === 'Cycles'
                    ? 'Historique et traçabilité des calculs expérimentaux.'
                    : section === 'Données'
                      ? 'Sources, fraîcheur et couverture des données.'
                      : 'Hypothèses, limites et état de validation du modèle.'}
              </p>
            </div>
            <div className="heading-actions">
              <button type="button" className="refresh-button"
                onClick={() => setRefresh((value) => value + 1)}>
                ↻ Actualiser
              </button>
              <span className="read-only-badge">● LECTURE SEULE</span>
            </div>
          </div>

          <div className="notice">
            <span className="notice-icon">i</span>
            <div>
              <strong>État des données Quant</strong>
              <p>
                {error
                  ? 'API locale indisponible. Aucun indicateur n’est affiché.'
                  : overview
                    ? lastChecked
                      ? `Données Quant consultées à ${lastChecked}.`
                      : 'Données Quant chargées.'
                    : 'Chargement des données depuis l’API locale…'}
              </p>
            </div>
          </div>

          {section === 'Vue d’ensemble' ? (
            <>
              <div className="metrics-grid">
                <Metric
                  label="CYCLES ENREGISTRÉS"
                  value={overview ? String(overview.cycles.count) : '—'}
                  detail={overview?.cycles.latest_created_at_utc
                    ? `Dernier cycle : ${overview.cycles.latest_created_at_utc.slice(0, 16)} UTC`
                    : 'Aucune date de cycle disponible'}
                  icon="◎"
                />
                <Metric
                  label="OBSERVATIONS DE TAUX"
                  value={overview ? String(overview.key_rates.observation_count) : '—'}
                  detail={overview?.key_rates.latest_effective_date
                    ? `Dernier taux effectif : ${overview.key_rates.latest_effective_date}`
                    : 'Aucune date de taux disponible'}
                  icon="↗"
                />
                <Metric
                  label="COUVERTURE DU MODÈLE"
                  value="—"
                  detail="Non mesurée · modèle expérimental"
                  icon="▤"
                />
              </div>

              <div className="content-grid">
                <section className="panel featured-panel">
                  <div className="panel-heading">
                    <div>
                      <div className="panel-kicker">RESEARCH ENGINE</div>
                      <h2>Cycle expérimental</h2>
                    </div>
                    <span className="panel-tag">NON CALIBRÉ</span>
                  </div>
                  <div className="empty-visual">
                    <div className="orbit orbit-one" />
                    <div className="orbit orbit-two" />
                    <div className="orbit-center">Q.</div>
                  </div>
                  <div className="panel-footer">
                    <span>Trajectoires fictives · coupons connus uniquement</span>
                    <span>↗</span>
                  </div>
                </section>

                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <div className="panel-kicker">SYSTEM STATUS</div>
                      <h2>Sources et services</h2>
                    </div>
                  </div>
                  <StatusRow
                    name="Collecte BCR"
                    detail={error
                      ? 'API indisponible'
                      : overview?.key_rates.latest_collected_at_utc
                        ? `Dernière collecte : ${overview.key_rates.latest_collected_at_utc.slice(0, 16)} UTC`
                        : 'Date indisponible'}
                  />
                  <StatusRow
                    name="Cycles Quant"
                    detail={error
                      ? 'API indisponible'
                      : overview?.cycles.latest_created_at_utc
                        ? `Dernier cycle : ${overview.cycles.latest_created_at_utc.slice(0, 16)} UTC`
                        : 'Aucun cycle daté'}
                  />
                  <StatusRow
                    name="Lecture CORE"
                    detail="Non vérifiée par cette API"
                  />
                  <div className="panel-note">
                    Ces dates indiquent la dernière activité enregistrée, pas
                    l’état instantané des services. Consultation en lecture seule.
                  </div>
                </section>
              </div>
            </>
          ) : section === 'Cycles' ? (
            <CyclesPanel refreshKey={refresh} />
          ) : (
            <section className="panel section-panel">
              <div className="panel-kicker">MODULE EN PRÉPARATION</div>
              <h2>{section}</h2>
              <p>
                Cette vue sera reliée aux données vérifiées de Portfolio Quant.
                Aucun résultat ou indicateur n’est simulé pour remplir l’interface.
              </p>
            </section>
          )}

          <footer className="page-footer">
            <span>PORTFOLIO QUANT · RESEARCH ENVIRONMENT</span>
            <span>Modèle expérimental — aucune mesure de risque validée</span>
          </footer>
        </div>
      </main>
    </div>
  )
}

function Metric({
  label,
  value,
  detail,
  icon,
}: {
  label: string
  value: string
  detail: string
  icon: string
}) {
  return (
    <section className="metric-card">
      <div className="metric-top">
        <span>{label}</span>
        <span className="metric-icon" aria-hidden="true">{icon}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-detail">{detail}</div>
    </section>
  )
}

function StatusRow({ name, detail }: { name: string; detail: string }) {
  return (
    <div className="status-row">
      <span className="status-placeholder" />
      <span className="status-name">{name}</span>
      <span className="status-detail">{detail}</span>
    </div>
  )
}

export default App
