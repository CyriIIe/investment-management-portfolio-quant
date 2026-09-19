import { useEffect, useState } from 'react'

type AssetIdentity = {
  isin: string
  security_code: string | null
  market_section: string
  currency: string
}

type AssetPrice = AssetIdentity & {
  clean_price_per_unit: string
  accrued_interest_per_unit: string
  dirty_price_per_unit: string
}

type AssetPriceResponse = {
  as_of_date: string
  assets: AssetPrice[]
  performance_measure: false
  portfolio_risk_measure: false
}

function isDecimal(value: unknown): value is string {
  return typeof value === 'string' &&
    /^-?\d+(?:\.\d+)?$/.test(value)
}

function isAssetPrice(value: unknown): value is AssetPrice {
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
    isDecimal(asset.clean_price_per_unit) &&
    isDecimal(asset.accrued_interest_per_unit) &&
    isDecimal(asset.dirty_price_per_unit)
  )
}

function isResponse(value: unknown): value is AssetPriceResponse {
  if (value === null || typeof value !== 'object') return false
  const data = value as Record<string, unknown>

  return (
    typeof data.as_of_date === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(data.as_of_date) &&
    Array.isArray(data.assets) &&
    data.assets.every(isAssetPrice) &&
    data.performance_measure === false &&
    data.portfolio_risk_measure === false
  )
}

function sameAsset(a: AssetIdentity, b: AssetIdentity): boolean {
  return a.isin === b.isin &&
    a.security_code === b.security_code &&
    a.market_section === b.market_section &&
    a.currency === b.currency
}

export default function AssetPriceDetails({
  asset,
  asOfDate,
}: {
  asset: AssetIdentity
  asOfDate: string
}) {
  const { isin, security_code, market_section, currency } = asset
  const [result, setResult] = useState<AssetPrice | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const controller = new AbortController()

    async function load() {
      setLoading(true)
      setError(false)
      setResult(null)

      try {
        const response = await fetch('/api/asset-prices', {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!response.ok) throw new Error('API unavailable')

        const payload: unknown = await response.json()
        if (!isResponse(payload) || payload.as_of_date !== asOfDate) {
          throw new Error('Invalid or mismatched snapshot')
        }

        const matches = payload.assets.filter((entry) =>
          sameAsset(entry, {
            isin,
            security_code,
            market_section,
            currency,
          })
        )
        if (matches.length !== 1) {
          throw new Error('Missing or ambiguous asset')
        }

        if (!controller.signal.aborted) {
          setResult(matches[0])
          setError(false)
          setLoading(false)
        }
      } catch {
        if (!controller.signal.aborted) {
          setResult(null)
          setError(true)
          setLoading(false)
        }
      }
    }

    void load()
    return () => controller.abort()
  }, [isin, security_code, market_section, currency, asOfDate])

  if (loading) return <p role="status">Chargement de la valorisation…</p>
  if (error || !result) {
    return <p role="alert">Valorisation courtier indisponible.</p>
  }

  return (
    <div className="panel-note">
      <h3>Valorisation courtier par obligation</h3>
      <p>Photographie du {asOfDate} — devise : {result.currency}.</p>
      <p>Prix hors intérêts courus : {result.clean_price_per_unit} {result.currency}</p>
      <p>Intérêts courus : {result.accrued_interest_per_unit} {result.currency}</p>
      <p>Prix intérêts courus inclus : {result.dirty_price_per_unit} {result.currency}</p>
      <p>
        Valeurs unitaires issues du courtier, et non cours MOEX,
        prix d’achat, rendement ou mesure de risque.
      </p>
    </div>
  )
}
