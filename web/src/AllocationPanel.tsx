import { useEffect, useState } from 'react'
import AssetCashflowDetails from './AssetCashflowDetails'
import AssetPriceDetails from './AssetPriceDetails'

type Asset = {
  isin: string
  security_code: string | null
  market_section: string
  weight_pct: string | null
}

type CurrencyGroup = {
  currency: string
  weights_available: boolean
  assets: Asset[]
}

type Allocation = {
  as_of_date: string
  currencies: CurrencyGroup[]
  includes_cash: false
  includes_accrued_interest: true
  portfolio_risk_measure: false
  performance_measure: false
}

const palette = [
  '#4d9d91', '#75b5a1', '#91a9cf', '#c0a276',
  '#ac89bb', '#769fc2', '#c48882', '#97b26f',
  '#b1a0cd', '#69acae', '#d3b68a', '#8b9ea5',
]

function validWeight(value: unknown): value is string | null {
  if (value === null) return true
  return (
    typeof value === 'string' &&
    value.trim() !== '' &&
    Number.isFinite(Number(value)) &&
    Number(value) >= 0 &&
    Number(value) <= 100
  )
}

function isAllocation(value: unknown): value is Allocation {
  if (value === null || typeof value !== 'object') return false
  const data = value as Record<string, unknown>

  if (
    typeof data.as_of_date !== 'string' ||
    !/^\d{4}-\d{2}-\d{2}$/.test(data.as_of_date) ||
    data.includes_cash !== false ||
    data.includes_accrued_interest !== true ||
    data.portfolio_risk_measure !== false ||
    data.performance_measure !== false ||
    !Array.isArray(data.currencies)
  ) return false

  return data.currencies.every((entry: unknown) => {
    if (entry === null || typeof entry !== 'object') return false
    const group = entry as Record<string, unknown>

    if (
      typeof group.currency !== 'string' ||
      !/^[A-Za-z]{3}$/.test(group.currency) ||
      typeof group.weights_available !== 'boolean' ||
      !Array.isArray(group.assets)
    ) return false

    const assetsValid = group.assets.every((entry: unknown) => {
      if (entry === null || typeof entry !== 'object') return false
      const asset = entry as Record<string, unknown>
      return (
        typeof asset.isin === 'string' &&
        asset.isin.length === 12 &&
        (asset.security_code === null ||
          typeof asset.security_code === 'string') &&
        typeof asset.market_section === 'string' &&
        asset.market_section.length > 0 &&
        validWeight(asset.weight_pct) &&
        (group.weights_available
          ? asset.weight_pct !== null
          : asset.weight_pct === null)
      )
    })

    if (!assetsValid) return false
    if (!group.weights_available) return true

    const sum = (group.assets as Asset[]).reduce(
      (total, asset) => total + Number(asset.weight_pct), 0
    )
    return group.assets.length > 0 && Math.abs(sum - 100) < 0.001
  })
}

function labelFor(asset: Asset): string {
  return asset.security_code || asset.isin
}

function AllocationGroup({
  group,
  asOfDate,
}: {
  group: CurrencyGroup
  asOfDate: string
}) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null)
  const assets = group.assets
  const selected = selectedIndex === null ? null : assets[selectedIndex]
  const segments = assets.map((asset, index) => {
    const start = assets.slice(0, index).reduce(
      (total, previous) => total + Number(previous.weight_pct ?? '0'),
      0
    )
    const end = start + Number(asset.weight_pct ?? '0')
    return `${palette[index % palette.length]} ${start}% ${end}%`
  })

  function selectFromChart(event: React.MouseEvent<HTMLButtonElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const x = event.clientX - bounds.left - bounds.width / 2
    const y = event.clientY - bounds.top - bounds.height / 2
    const angle = (Math.atan2(x, -y) * 180 / Math.PI + 360) % 360
    const percentage = angle / 3.6

    let cumulative = 0
    for (let index = 0; index < assets.length; index += 1) {
      cumulative += Number(assets[index].weight_pct ?? '0')
      if (percentage < cumulative || index === assets.length - 1) {
        setSelectedIndex(index)
        return
      }
    }
  }

  return (
    <div className="panel-note">
      <h3>Répartition en {group.currency}</h3>
      {!group.weights_available ? (
        <p>Poids indisponibles : valeur totale nulle pour cette devise.</p>
      ) : (
        <>
          <button
            type="button"
            onClick={selectFromChart}
            aria-label={`Camembert en ${group.currency} : cliquer pour sélectionner un actif`}
            style={{
              display: 'block',
              width: 'min(260px, 100%)',
              aspectRatio: '1',
              borderRadius: '50%',
              border: '2px solid #526574',
              cursor: 'pointer',
              background: `conic-gradient(${segments.join(', ')})`,
              margin: '18px auto',
            }}
          />
          <div className="cycles-list">
            {assets.map((asset, index) => (
              <button
                key={`${asset.isin}:${asset.security_code ?? ''}:${asset.market_section}`}
                type="button"
                onClick={() => setSelectedIndex(index)}
                aria-pressed={selectedIndex === index}
                className="cycle-entry"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  width: '100%',
                  cursor: 'pointer',
                  textAlign: 'left',
                  color: 'inherit',
                  border: selectedIndex === index
                    ? '1px solid #91bdb5'
                    : '1px solid transparent',
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    flexShrink: 0,
                    width: '12px',
                    height: '12px',
                    borderRadius: '3px',
                    background: palette[index % palette.length],
                  }}
                />
                <span style={{ flex: 1 }}>{labelFor(asset)}</span>
                <strong>{Number(asset.weight_pct).toFixed(2)} %</strong>
              </button>
            ))}
          </div>
        </>
      )}

      {selected && (
        <div className="panel-note" aria-live="polite">
          <h3>Fiche descriptive — {labelFor(selected)}</h3>
          <p>ISIN : {selected.isin}</p>
          <p>Marché : {selected.market_section}</p>
          <p>Devise : {group.currency}</p>
          <p>Poids dans cette devise : {Number(selected.weight_pct).toFixed(2)} %</p>
          <p>Photographie du {asOfDate}.</p>
          <AssetPriceDetails
          key={`price:${asOfDate}:${selected.isin}:${selected.security_code ?? ''}:${selected.market_section}:${group.currency}`}
          asset={{
            isin: selected.isin,
            security_code: selected.security_code,
            market_section: selected.market_section,
            currency: group.currency,
          }}
          asOfDate={asOfDate}
        />
        <AssetCashflowDetails
            key={`${asOfDate}:${selected.isin}:${selected.security_code ?? ''}:${selected.market_section}:${group.currency}`}
            asset={{
              isin: selected.isin,
              security_code: selected.security_code,
              market_section: selected.market_section,
              currency: group.currency,
            }}
            asOfDate={asOfDate}
          />
          <p>
            Fiche descriptive uniquement : aucune analyse individuelle de
            rendement, de crédit, de risque ou de performance n’est encore disponible.
          </p>
        </div>
      )}
    </div>
  )
}

export default function AllocationPanel({
  refreshKey,
}: {
  refreshKey: number
}) {
  const [data, setData] = useState<Allocation | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadAllocation() {
      try {
        const response = await fetch('/api/allocation', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const result: unknown = await response.json()
        if (!isAllocation(result)) throw new Error('Invalid allocation response')

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

    void loadAllocation()
    return () => controller.abort()
  }, [refreshKey])

  return (
    <section className="panel section-panel">
      <div className="panel-kicker">MÉTÉO / CARTOGRAPHIE</div>
      <h2>Répartition par actif</h2>
      <p>
        Poids calculés avec la valeur de marché et les intérêts courus,
        séparément par devise. Trésorerie exclue.
      </p>

      {error ? (
        <p role="alert">Répartition indisponible.</p>
      ) : !data ? (
        <p role="status">Chargement de la répartition…</p>
      ) : data.currencies.length === 0 ? (
        <p>Aucune répartition disponible.</p>
      ) : (
        <>
          <div className="panel-note">
            Photographie du {data.as_of_date}. Sélectionne un segment ou
            une ligne de la légende pour ouvrir sa fiche descriptive.
          </div>
          {data.currencies.map((group) => (
            <AllocationGroup
              key={`${data.as_of_date}:${group.currency}:${refreshKey}`}
              group={group}
              asOfDate={data.as_of_date}
            />
          ))}
          <div className="panel-note">
            Chaque camembert représente uniquement les actifs de sa devise.
            Les poids ne mesurent ni la performance ni le risque du portefeuille.
          </div>
        </>
      )}
    </section>
  )
}
