import { useEffect, useState } from 'react'

type Scenario = {
  hypothetical_annual_market_yield: string
  received_through_horizon_rub_per_bond: string
  theoretical_terminal_price_rub_per_bond: string
  terminal_wealth_rub_per_bond: string
  gross_total_return_decimal: string
}

type Pilot = {
  status: 'EXPERIMENTAL'
  instrument_isin: string
  valuation_date: string
  horizon_date: string
  document_observation_date: string
  historical_cashflow_availability: 'NOT_PROVEN'
  historical_backtest_validated: false
  price_basis: string
  dirty_price_rub_per_bond: string
  source_json_sha256: string
  coupon_count: number
  scenarios: Scenario[]
  performance_measure: false
  portfolio_risk_measure: false
}

function isPilot(value: unknown): value is Pilot {
  if (value === null || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  if (
    v.status !== 'EXPERIMENTAL' ||
    v.historical_backtest_validated !== false ||
    v.historical_cashflow_availability !== 'NOT_PROVEN' ||
    v.performance_measure !== false ||
    v.portfolio_risk_measure !== false ||
    typeof v.instrument_isin !== 'string' ||
    typeof v.valuation_date !== 'string' ||
    typeof v.horizon_date !== 'string' ||
    typeof v.document_observation_date !== 'string' ||
    typeof v.dirty_price_rub_per_bond !== 'string' ||
    !Array.isArray(v.scenarios) ||
    v.scenarios.length !== 3
  ) return false

  return v.scenarios.every((item: unknown) => {
    if (item === null || typeof item !== 'object') return false
    const s = item as Record<string, unknown>
    return [
      'hypothetical_annual_market_yield',
      'received_through_horizon_rub_per_bond',
      'theoretical_terminal_price_rub_per_bond',
      'terminal_wealth_rub_per_bond',
      'gross_total_return_decimal',
    ].every((key) =>
      typeof s[key] === 'string' &&
      s[key] !== '' &&
      Number.isFinite(Number(s[key]))
    )
  })
}

const rub = (value: string) =>
  `${Number(value).toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} RUB`

const pct = (value: string) =>
  `${(Number(value) * 100).toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} %`

export default function ExperimentalPilotPanel({
  refreshKey,
}: {
  refreshKey: number
}) {
  const [data, setData] = useState<Pilot | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch('/api/experimental-pilot', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('Pilot unavailable')

        const payload: unknown = await response.json()
        if (!isPilot(payload)) throw new Error('Invalid pilot')

        if (!controller.signal.aborted) {
          setData(payload)
          setError(false)
        }
      } catch {
        if (!controller.signal.aborted) {
          setData(null)
          setError(true)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <div className="panel-kicker">RECHERCHE DOCUMENTAIRE</div>
          <h2>Premier pilote déterministe</h2>
        </div>
        <span className="panel-tag">EXPÉRIMENTAL</span>
      </div>

      {error ? (
        <p className="panel-note">
          Pilote indisponible ou source modifiée. Aucun résultat n’est affiché.
        </p>
      ) : !data ? (
        <p className="panel-note">Chargement du pilote…</p>
      ) : (
        <>
          <p>
            OFZ 26252 · {data.instrument_isin} · photographie du{' '}
            {data.valuation_date} · horizon du {data.horizon_date}.
          </p>
          <p>
            Prix de référence MOEX avec intérêts courus, par obligation :{' '}
            <strong>{rub(data.dirty_price_rub_per_bond)}</strong>.
            Ce n’est pas un prix d’exécution courtier.
          </p>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', textAlign: 'left' }}>
              <thead>
                <tr>
                  <th>Rendement de marché supposé</th>
                  <th>Coupons reçus</th>
                  <th>Prix terminal théorique</th>
                  <th>Rendement total brut</th>
                </tr>
              </thead>
              <tbody>
                {data.scenarios.map((scenario) => (
                  <tr key={scenario.hypothetical_annual_market_yield}>
                    <td>{pct(scenario.hypothetical_annual_market_yield)}</td>
                    <td>{rub(scenario.received_through_horizon_rub_per_bond)}</td>
                    <td>{rub(scenario.theoretical_terminal_price_rub_per_bond)}</td>
                    <td><strong>{pct(scenario.gross_total_return_decimal)}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p className="panel-note">
            Simulation rétrospective expérimentale : les flux ont été vérifiés
            le {data.document_observation_date}, mais leur disponibilité au{' '}
            {data.valuation_date} n’est pas prouvée. Ce n’est pas un backtest
            sans connaissance future. Hypothèses de rendement plat, non
            calibrées au marché ; hors fiscalité, frais, défaut et réinvestissement.
            Résultats par obligation, sans quantités détenues ni recommandation
            d’achat ou de vente.
          </p>
        </>
      )}
    </section>
  )
}
