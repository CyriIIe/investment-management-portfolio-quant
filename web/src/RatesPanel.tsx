import { useEffect, useState } from 'react'

type RateObservation = {
  effective_date: string
  rate_percent: string
  collected_at_utc: string
}

type RatesResponse = {
  total: number
  observations: RateObservation[]
}

function formatDate(value: string): string {
  const date = new Date(`${value}T00:00:00Z`)
  return Number.isNaN(date.getTime())
    ? 'Date indisponible'
    : date.toLocaleDateString('fr-FR', {
        timeZone: 'UTC',
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      })
}

function formatCollection(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date indisponible'
    : `${date.toLocaleString('fr-FR', {
        timeZone: 'UTC',
        dateStyle: 'medium',
        timeStyle: 'short',
      })} UTC`
}

export default function RatesPanel({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<RatesResponse | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadRates() {
      setData(null)
      setError(false)

      try {
        const response = await fetch('/api/rates', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const result: RatesResponse = await response.json()
        if (
          !Number.isSafeInteger(result.total) ||
          result.total < 0 ||
          !Array.isArray(result.observations) ||
          result.observations.some((item) =>
            typeof item.effective_date !== 'string' ||
            typeof item.rate_percent !== 'string' ||
            typeof item.collected_at_utc !== 'string'
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

    void loadRates()
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section className="panel section-panel">
      <div className="panel-kicker">DONNÉES MACROÉCONOMIQUES</div>
      <h2>Taux directeur de la BCR</h2>
      <p>
        Historique des observations collectées. La date d’effet du taux
        est distincte de la date à laquelle Portfolio Quant l’a enregistré.
        Ces observations ne constituent pas des prévisions.
      </p>

      {error ? (
        <p role="alert">
          Impossible de consulter les taux : API locale indisponible.
        </p>
      ) : !data ? (
        <p role="status">Chargement des observations…</p>
      ) : (
        <>
          <p>
            {data.total} observation{data.total > 1 ? 's' : ''} enregistrée
            {data.total > 1 ? 's' : ''} · {data.observations.length} affichée
            {data.observations.length > 1 ? 's' : ''}
          </p>

          {data.observations.length === 0 ? (
            <p>Aucune observation enregistrée.</p>
          ) : (
            <div className="rates-table-wrap">
              <table className="rates-table">
                <thead>
                  <tr>
                    <th scope="col">Date d’effet</th>
                    <th scope="col">Taux observé</th>
                    <th scope="col">Collecté le</th>
                  </tr>
                </thead>
                <tbody>
                  {data.observations.map((item, index) => (
                    <tr key={`${item.effective_date}-${index}`}>
                      <td>{formatDate(item.effective_date)}</td>
                      <td className="rate-value">
                        {item.rate_percent.replace('.', ',')} %
                      </td>
                      <td>{formatCollection(item.collected_at_utc)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
      <div className="panel-note">
        Taux directeur observé ≠ taux futur ≠ formule contractuelle
        des coupons variables.
      </div>
    </section>
  )
}
