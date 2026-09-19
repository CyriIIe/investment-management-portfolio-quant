import { useEffect, useState } from 'react'

type AssetIdentity = {
  isin: string
  security_code: string | null
  market_section: string
  currency: string
}

type AssetCashflow = AssetIdentity & {
  known_event_count: number
  next_known_event_date: string | null
  incomplete_reasons: string[]
}

type AssetCashflowResponse = {
  as_of_date: string
  assets: AssetCashflow[]
  unassigned_event_count: number
  unassigned_schedule_count: number
  complete_cashflows: false
  portfolio_risk_measure: false
  performance_measure: false
}

function isDate(value: unknown): value is string {
  return typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(value)
}

function isNonnegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0
}

function isAsset(value: unknown): value is AssetCashflow {
  if (value === null || typeof value !== 'object') return false
  const asset = value as Record<string, unknown>

  return (
    typeof asset.isin === 'string' &&
    asset.isin.length === 12 &&
    (asset.security_code === null ||
      typeof asset.security_code === 'string') &&
    typeof asset.market_section === 'string' &&
    asset.market_section.length > 0 &&
    typeof asset.currency === 'string' &&
    /^[A-Za-z]{3}$/.test(asset.currency) &&
    isNonnegativeInteger(asset.known_event_count) &&
    (asset.next_known_event_date === null ||
      isDate(asset.next_known_event_date)) &&
    Array.isArray(asset.incomplete_reasons) &&
    asset.incomplete_reasons.every(
      (reason: unknown) => typeof reason === 'string' && reason.length > 0
    )
  )
}

function isResponse(value: unknown): value is AssetCashflowResponse {
  if (value === null || typeof value !== 'object') return false
  const data = value as Record<string, unknown>

  return (
    isDate(data.as_of_date) &&
    Array.isArray(data.assets) &&
    data.assets.every(isAsset) &&
    isNonnegativeInteger(data.unassigned_event_count) &&
    isNonnegativeInteger(data.unassigned_schedule_count) &&
    data.complete_cashflows === false &&
    data.portfolio_risk_measure === false &&
    data.performance_measure === false
  )
}

function sameAsset(a: AssetIdentity, b: AssetIdentity): boolean {
  return a.isin === b.isin &&
    a.security_code === b.security_code &&
    a.market_section === b.market_section &&
    a.currency === b.currency
}

const reasonLabels: Record<string, string> = {
  MISSING_COUPON_SCHEDULE: 'Calendrier des coupons manquant',
  MISSING_MATURITY: 'Échéance non renseignée',
  MISSING_CURRENCY: 'Devise manquante dans la source',
  MISSING_ACTION_AMOUNT: 'Montant d’un événement manquant dans la source',
}

export default function AssetCashflowDetails({
  asset,
  asOfDate,
}: {
  asset: AssetIdentity
  asOfDate: string
}) {
  const { isin, security_code, market_section, currency } = asset
  const [result, setResult] = useState<AssetCashflow | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      try {
        const response = await fetch('/api/asset-cashflows', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API indisponible')

        const payload: unknown = await response.json()
        if (!isResponse(payload)) throw new Error('Réponse API invalide')

        if (payload.as_of_date !== asOfDate) {
          throw new Error('Dates des photographies différentes')
        }

        const matches = payload.assets.filter(
          (entry) => sameAsset(entry, {
            isin,
            security_code,
            market_section,
            currency,
          })
        )
        if (matches.length !== 1) {
          throw new Error('Correspondance individuelle indisponible')
        }

        if (!controller.signal.aborted) {
          setResult(matches[0])
          setError(null)
          setLoading(false)
        }
      } catch (caught) {
        if (!controller.signal.aborted) {
          setResult(null)
          setError(
            caught instanceof Error ? caught.message : 'Données indisponibles'
          )
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [
    isin,
    security_code,
    market_section,
    currency,
    asOfDate,
  ])

  if (loading) return <p role="status">Chargement des événements connus…</p>
  if (error || !result) {
    return (
      <p role="alert">
        Flux individuels indisponibles : {error ?? 'données indisponibles'}.
      </p>
    )
  }

  return (
    <div className="panel-note">
      <h3>Événements connus</h3>
      <p>Nombre d’événements attribués : {result.known_event_count}</p>
      <p>
        Prochain événement connu :{' '}
        {result.next_known_event_date ?? 'Aucune date connue'}
      </p>
      {result.incomplete_reasons.length > 0 ? (
        <>
          <h3>Informations manquantes signalées</h3>
          <div className="cycles-list">
            {result.incomplete_reasons.map((reason) => (
              <div className="cycle-entry" key={reason}>
                {reasonLabels[reason] ?? reason}
              </div>
            ))}
          </div>
        </>
      ) : (
        <p>Aucun motif d’incomplétude signalé pour cet actif.</p>
      )}
      <p>
        Événements connus uniquement : ce calendrier n’est pas garanti
        exhaustif. Aucune mesure de performance ou de risque n’est fournie.
      </p>
    </div>
  )
}
