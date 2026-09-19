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
  instrument_label: string
  coupon_type: string
  valuation_date: string
  horizon_date: string
  document_observation_date: string
  historical_cashflow_availability: 'NOT_PROVEN'
  historical_backtest_validated: false
  dirty_price_rub_per_bond: string
  coupon_count: number
  principal_event_count: number
  received_coupon_rub_per_bond: string
  received_principal_rub_per_bond: string
  scenarios: Scenario[]
  performance_measure: false
  portfolio_risk_measure: false
}

type Response = {
  status: 'EXPERIMENTAL'
  instruments: Pilot[]
  historical_backtest_validated: false
  portfolio_risk_measure: false
}

function isNumeric(value: unknown): value is string {
  return (
    typeof value === 'string' &&
    value.trim() !== '' &&
    Number.isFinite(Number(value))
  )
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
    typeof v.instrument_label !== 'string' ||
    typeof v.valuation_date !== 'string' ||
    typeof v.horizon_date !== 'string' ||
    typeof v.document_observation_date !== 'string' ||
    !isNumeric(v.dirty_price_rub_per_bond) ||
    !isNumeric(v.received_coupon_rub_per_bond) ||
    !isNumeric(v.received_principal_rub_per_bond) ||
    !Array.isArray(v.scenarios) ||
    v.scenarios.length !== 3
  ) return false

  return v.scenarios.every((item: unknown, index: number) => {
    if (item === null || typeof item !== 'object') return false
    const s = item as Record<string, unknown>
    const expected = ['0.10', '0.125', '0.15'][index]

    return (
      s.hypothetical_annual_market_yield === expected &&
      [
        'received_through_horizon_rub_per_bond',
        'theoretical_terminal_price_rub_per_bond',
        'terminal_wealth_rub_per_bond',
        'gross_total_return_decimal',
      ].every((key) => isNumeric(s[key]))
    )
  })
}

function isResponse(value: unknown): value is Response {
  if (value === null || typeof value !== 'object') return false
  const v = value as Record<string, unknown>
  return (
    v.status === 'EXPERIMENTAL' &&
    v.historical_backtest_validated === false &&
    v.portfolio_risk_measure === false &&
    Array.isArray(v.instruments) &&
    v.instruments.length > 0 &&
    v.instruments.every(isPilot) &&
    new Set(
      v.instruments.map((item: Pilot) => item.instrument_isin)
    ).size === v.instruments.length
  )
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
  const [data, setData] = useState<Response | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch('/api/experimental-pilots', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('Experimental pilots unavailable')

        const payload: unknown = await response.json()
        if (!isResponse(payload)) throw new Error('Invalid experimental pilots')

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
          <h2>Pilotes déterministes</h2>
        </div>
        <span className="panel-tag">EXPÉRIMENTAL</span>
      </div>

      {error ? (
        <p className="panel-note">
          Pilotes indisponibles ou sources modifiées. Aucun résultat affiché.
        </p>
      ) : !data ? (
        <p className="panel-note">Chargement des pilotes…</p>
      ) : (
        data.instruments.map((pilot) => (
          <div key={pilot.instrument_isin}>
            <h3>{pilot.instrument_label}</h3>
            <p>
              {pilot.instrument_isin} · photographie du {pilot.valuation_date}
              {' '}· horizon du {pilot.horizon_date}.
            </p>
            <p>
              Prix de référence MOEX avec intérêts courus, par obligation :{' '}
              <strong>{rub(pilot.dirty_price_rub_per_bond)}</strong>.
              Ce n’est pas un prix d’exécution courtier.
            </p>
            <p>
              Flux reçus à l’horizon, par obligation : coupons{' '}
              <strong>{rub(pilot.received_coupon_rub_per_bond)}</strong>
              {' '}et principal remboursé{' '}
              <strong>{rub(pilot.received_principal_rub_per_bond)}</strong>.
              {' '}Le principal remboursé n’est pas un revenu supplémentaire.
            </p>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', textAlign: 'left' }}>
                <thead>
                  <tr>
                    <th>Rendement de marché supposé</th>
                    <th>Flux totaux reçus</th>
                    <th>Prix terminal théorique</th>
                    <th>Rendement total brut</th>
                  </tr>
                </thead>
                <tbody>
                  {pilot.scenarios.map((scenario) => (
                    <tr key={scenario.hypothetical_annual_market_yield}>
                      <td>{pct(scenario.hypothetical_annual_market_yield)}</td>
                      <td>
                        {rub(scenario.received_through_horizon_rub_per_bond)}
                      </td>
                      <td>
                        {rub(scenario.theoretical_terminal_price_rub_per_bond)}
                      </td>
                      <td>
                        <strong>
                          {pct(scenario.gross_total_return_decimal)}
                        </strong>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <p className="panel-note">
              Simulation rétrospective expérimentale : calendrier vérifié le{' '}
              {pilot.document_observation_date}, mais disponibilité au{' '}
              {pilot.valuation_date} non prouvée. Ce n’est pas un backtest
              sans connaissance future. Rendements plats hypothétiques, non
              calibrés ; hors fiscalité, frais, défaut et réinvestissement.
              Résultats par obligation, sans quantités détenues ni
              recommandation de transaction.
            </p>
          </div>
        ))
      )}
    </section>
  )
}
