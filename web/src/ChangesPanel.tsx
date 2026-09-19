import { useEffect, useState } from 'react'

type Changes = {
  previous_date: string
  current_date: string
  previous_position_count: number
  current_position_count: number
  added_count: number
  removed_count: number
  quantity_changed_count: number
  value_changed_at_constant_quantity_count: number
  accrued_changed_at_constant_quantity_count: number
  source_only_changed_count: number
  unchanged_count: number
  portfolio_risk_measure: boolean
  performance_measure: boolean
  explanations: {
    observations: string[]
    limitations: string[]
  }
}

const countFields = [
  'previous_position_count',
  'current_position_count',
  'added_count',
  'removed_count',
  'quantity_changed_count',
  'value_changed_at_constant_quantity_count',
  'accrued_changed_at_constant_quantity_count',
  'source_only_changed_count',
  'unchanged_count',
] as const

function isTextList(value: unknown): value is string[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((item) => typeof item === 'string')
  )
}

function isChanges(value: unknown): value is Changes {
  if (value === null || typeof value !== 'object') return false
  const data = value as Record<string, unknown>

  return (
    typeof data.previous_date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(data.previous_date) &&
    typeof data.current_date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(data.current_date) &&
    data.previous_date < data.current_date &&
    countFields.every((field) =>
      Number.isSafeInteger(data[field]) && (data[field] as number) >= 0
    ) &&
    data.performance_measure === false &&
    data.portfolio_risk_measure === false &&
    data.explanations !== null &&
    typeof data.explanations === 'object' &&
    isTextList(
      (data.explanations as Record<string, unknown>).observations
    ) &&
    isTextList(
      (data.explanations as Record<string, unknown>).limitations
    )
  )
}

export default function ChangesPanel({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<Changes | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadChanges() {
      try {
        const response = await fetch('/api/changes', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const result: unknown = await response.json()
        if (!isChanges(result)) throw new Error('Invalid changes response')

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

    void loadChanges()
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section className="panel section-panel">
      <div className="panel-kicker">MÉTÉO / PHASE 2.2</div>
      <h2>Depuis la photographie précédente</h2>
      <p>
        Comparaison des positions actives à deux dates. Un ajout ne prouve
        pas un achat ; une variation de valeur n’est pas une performance.
      </p>

      {error ? (
        <p role="alert">
          Comparaison indisponible : aucun changement n’est affiché.
        </p>
      ) : !data ? (
        <p role="status">Chargement des changements…</p>
      ) : (
        <>
          <div className="panel-note">
            Période : {data.previous_date} → {data.current_date} ·
            {' '}{data.previous_position_count} → {data.current_position_count}
            {' '}positions actives.
          </div>

          <div className="metrics-grid">
            <article className="metric-card">
              <div className="metric-top">POSITIONS APPARUES</div>
              <div className="metric-value">{data.added_count}</div>
              <div className="metric-detail">
                Apparition constatée, cause non établie
              </div>
            </article>
            <article className="metric-card">
              <div className="metric-top">POSITIONS DISPARUES</div>
              <div className="metric-value">{data.removed_count}</div>
              <div className="metric-detail">
                Disparition constatée, cause non établie
              </div>
            </article>
            <article className="metric-card">
              <div className="metric-top">QUANTITÉS MODIFIÉES</div>
              <div className="metric-value">
                {data.quantity_changed_count}
              </div>
              <div className="metric-detail">
                Parmi les positions présentes aux deux dates
              </div>
            </article>
          </div>

          <div className="cycles-list">
            <div className="cycle-entry">
              Valeur modifiée à quantité constante :
              {' '}{data.value_changed_at_constant_quantity_count}
            </div>
            <div className="cycle-entry">
              Intérêts courus modifiés à quantité constante :
              {' '}{data.accrued_changed_at_constant_quantity_count}
            </div>
            <div className="cycle-entry">
              Source seule modifiée : {data.source_only_changed_count}
            </div>
            <div className="cycle-entry">
              Positions inchangées : {data.unchanged_count}
            </div>
          </div>

          <div className="panel-note">
            Les variations de valeur et d’intérêts courus peuvent concerner
            les mêmes positions : ces décomptes ne s’additionnent pas.
            Aucune mesure de performance ou de risque global n’est disponible.
          </div>
          <h3>Ce que nous observons</h3>
          <div className="cycles-list">
            {data.explanations.observations.map((observation, index) => (
              <div className="cycle-entry" key={index}>
                {observation}
              </div>
            ))}
          </div>

          <h3>Ce que cette comparaison ne permet pas de conclure</h3>
          <div className="cycles-list">
            {data.explanations.limitations.map((limitation, index) => (
              <div className="cycle-entry" key={index}>
                {limitation}
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  )
}
