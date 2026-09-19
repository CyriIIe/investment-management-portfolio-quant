import { useEffect, useState } from 'react'

type Cycle = {
  identity_prefix: string
  created_at_utc: string
  model_name: string
  calibrated_to_market: boolean
  complete_portfolio_valuation: boolean
  portfolio_risk_measure: boolean
}

type CyclesResponse = {
  total: number
  cycles: Cycle[]
}

function formatUtc(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date indisponible'
    : `${date.toLocaleString('fr-FR', {
        timeZone: 'UTC',
        dateStyle: 'medium',
        timeStyle: 'short',
      })} UTC`
}

export default function CyclesPanel({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<CyclesResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadCycles() {
      try {
        const response = await fetch('/api/cycles', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const result: CyclesResponse = await response.json()
        if (
          !Number.isSafeInteger(result.total) ||
          !Array.isArray(result.cycles) ||
          result.cycles.some((cycle) =>
            typeof cycle.identity_prefix !== 'string' ||
            typeof cycle.created_at_utc !== 'string' ||
            typeof cycle.model_name !== 'string' ||
            typeof cycle.calibrated_to_market !== 'boolean' ||
            typeof cycle.complete_portfolio_valuation !== 'boolean' ||
            typeof cycle.portfolio_risk_measure !== 'boolean'
          )
        ) {
          throw new Error('Invalid API response')
        }

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

    void loadCycles()
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section className="panel section-panel">
      <div className="panel-kicker">HISTORIQUE QUANT</div>
      <h2>Cycles expérimentaux</h2>
      <p>
        Métadonnées enregistrées dans Portfolio Quant. Aucun montant,
        résultat détaillé ou indicateur de risque non validé n’est affiché.
      </p>

      {error ? (
        <p role="alert">Impossible de consulter les cycles : API locale indisponible.</p>
      ) : !data ? (
        <p role="status">Chargement des cycles…</p>
      ) : (
        <>
          <p>
            {data.total} cycle{data.total > 1 ? 's' : ''} enregistré
            {data.total > 1 ? 's' : ''} · {data.cycles.length} affiché
            {data.cycles.length > 1 ? 's' : ''}
          </p>

          {data.cycles.length === 0 ? (
            <p>Aucun cycle enregistré.</p>
          ) : (
            <div className="cycles-list">
              {data.cycles.map((cycle) => (
                <article className="cycle-entry" key={cycle.identity_prefix}>
                  <div className="panel-kicker">CYCLE · {cycle.identity_prefix}</div>
                  <h3>{formatUtc(cycle.created_at_utc)}</h3>
                  <p>Modèle : {cycle.model_name}</p>
                  <p>
                    {cycle.calibrated_to_market
                      ? 'Calibration au marché déclarée'
                      : 'Non calibré au marché'}
                    {' · '}
                    {cycle.complete_portfolio_valuation
                      ? 'Valorisation complète déclarée'
                      : 'Valorisation incomplète'}
                    {' · '}
                    {cycle.portfolio_risk_measure
                      ? 'Mesure de risque déclarée'
                      : 'Aucune mesure de risque validée'}
                  </p>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}
