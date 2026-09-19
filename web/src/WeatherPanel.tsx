import { useEffect, useState } from 'react'

type Weather = {
  portfolio_date: string
  cashflow_run_id: number
  position_count: number
  coupon_coverage_pct: string
  unknown_schedule_count: number
  cashflow_horizon_days: number
  event_count: number
  events_by_type: Record<string, number>
  events_by_currency: Record<string, number>
  complete_cashflows: boolean
  portfolio_risk_measure: boolean
}

function isCount(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0
}

function isCounts(value: unknown): value is Record<string, number> {
  return (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    Object.values(value).every(isCount)
  )
}

function isWeather(value: unknown): value is Weather {
  if (value === null || typeof value !== 'object') return false

  const data = value as Record<string, unknown>
  const coverage =
    typeof data.coupon_coverage_pct === 'string'
      ? Number(data.coupon_coverage_pct)
      : NaN

  return (
    typeof data.portfolio_date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(data.portfolio_date) &&
    isCount(data.cashflow_run_id) &&
    data.cashflow_run_id > 0 &&
    isCount(data.position_count) &&
    data.position_count > 0 &&
    Number.isFinite(coverage) &&
    coverage >= 0 &&
    coverage <= 100 &&
    isCount(data.unknown_schedule_count) &&
    isCount(data.cashflow_horizon_days) &&
    data.cashflow_horizon_days > 0 &&
    isCount(data.event_count) &&
    isCounts(data.events_by_type) &&
    isCounts(data.events_by_currency) &&
    data.complete_cashflows === false &&
    data.portfolio_risk_measure === false
  )
}

export default function WeatherPanel({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<Weather | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadWeather() {
      try {
        const response = await fetch('/api/weather', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const result: unknown = await response.json()
        if (!isWeather(result)) throw new Error('Invalid weather response')

        if (!controller.signal.aborted) {
          setData(result)
          setError(false)
        }
      } catch {
        if (!controller.signal.aborted) {
          setData(null)
          setError(true)
        }
      }
    }

    void loadWeather()
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section className="panel section-panel">
      <div className="panel-kicker">MÉTÉO / PHASE 2.1</div>
      <h2>Photographie descriptive du portefeuille</h2>
      <p>
        Données CORE consultées en lecture seule. Ce bulletin décrit la
        couverture disponible ; il ne prédit pas la performance.
      </p>

      {error ? (
        <p role="alert">
          Météo indisponible : aucune donnée de portefeuille n’est affichée.
        </p>
      ) : !data ? (
        <p role="status">Chargement de la météo…</p>
      ) : (
        <>
          <div className="metrics-grid">
            <article className="metric-card">
              <div className="metric-top">POSITIONS <span aria-hidden="true">◫</span></div>
              <div className="metric-value">{data.position_count}</div>
              <div className="metric-detail">
                Photographie du {data.portfolio_date}
              </div>
            </article>

            <article className="metric-card">
              <div className="metric-top">COUVERTURE DES COUPONS <span aria-hidden="true">▤</span></div>
              <div className="metric-value">
                {data.coupon_coverage_pct} %
              </div>
              <div className="metric-detail">
                Couverture du calendrier, pas du risque global
              </div>
            </article>

            <article className="metric-card">
              <div className="metric-top">CALENDRIERS INCONNUS <span aria-hidden="true">◇</span></div>
              <div className="metric-value">
                {data.unknown_schedule_count}
              </div>
              <div className="metric-detail">
                Informations restant à documenter
              </div>
            </article>
          </div>

          <div className="panel-note">
            Calcul de flux CORE n° {data.cashflow_run_id} · Horizon :
            {' '}{data.cashflow_horizon_days} jours ·
            {' '}{data.event_count} événements recensés.
          </div>

          <h3>Événements par type</h3>
          {Object.entries(data.events_by_type).length === 0 ? (
            <p>Aucun événement recensé.</p>
          ) : (
            <div className="cycles-list">
              {Object.entries(data.events_by_type).map(([type, count]) => (
                <div className="cycle-entry" key={type}>
                  <strong>{type}</strong> · {count}
                </div>
              ))}
            </div>
          )}

          <h3>Événements par devise</h3>
          {Object.entries(data.events_by_currency).length === 0 ? (
            <p>Aucun événement recensé.</p>
          ) : (
            <div className="cycles-list">
              {Object.entries(data.events_by_currency).map(([currency, count]) => (
                <div className="cycle-entry" key={currency}>
                  <strong>{currency}</strong> · {count}
                </div>
              ))}
            </div>
          )}

          <div className="panel-note">
            Flux complets : non établis · Mesure du risque global :
            non disponible. Les montants et positions individuelles ne sont
            pas affichés dans ce bulletin.
          </div>
        </>
      )}
    </section>
  )
}
