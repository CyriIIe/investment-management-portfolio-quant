import { useEffect, useState } from 'react'

type Instrument = {
  status: 'AVAILABLE' | 'UNAVAILABLE'
  instrument_isin: string
  instrument_label: string
  valuation_date?: string
  calculated_at_utc?: string
  market_observation_date?: string
  market_collected_at_utc?: string
  board?: string
  reason?: string
}

type Response = {
  status: 'EXPERIMENTAL'
  modeled_instrument_count: 3
  portfolio_representative: false
  instruments: Instrument[]
}

function isResponse(value: unknown): value is Response {
  if (value === null || typeof value !== 'object') return false
  const response = value as Record<string, unknown>
  return response.status === 'EXPERIMENTAL' &&
    response.modeled_instrument_count === 3 &&
    response.portfolio_representative === false &&
    Array.isArray(response.instruments) && response.instruments.length === 3 &&
    response.instruments.every((item) => item !== null && typeof item === 'object' &&
      ['AVAILABLE', 'UNAVAILABLE'].includes((item as Record<string, unknown>).status as string))
}

export default function ExperimentalWeatherPanel({ refreshKey }: { refreshKey: number }) {
  const [data, setData] = useState<Response | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    void fetch('/api/experimental-weather', { signal: controller.signal, cache: 'no-store' })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload: unknown) => { if (!isResponse(payload)) throw new Error(); if (!controller.signal.aborted) setData(payload) })
      .catch(() => { if (!controller.signal.aborted) setData(null) })
    return () => controller.abort()
  }, [refreshKey])

  return <section className="panel">
    <div className="panel-heading"><div><div className="panel-kicker">MÉTÉO DE MARCHÉ</div><h2>3 obligations modélisées</h2></div><span className="panel-tag">EXPÉRIMENTAL</span></div>
    <p className="panel-note">Résultats conditionnels, non calibrés et non prédictifs. Ils ne représentent pas l’ensemble du portefeuille CORE.</p>
    {!data ? <p className="panel-note">Météo non disponible.</p> : data.instruments.map((item) => <div key={item.instrument_isin}>
      <h3>{item.instrument_label}</h3>
      {item.status === 'UNAVAILABLE' ? <p className="panel-note">Non disponible : {item.reason ?? 'entrée absente ou périmée'}.</p> : <p>
        Valorisation : {item.valuation_date} · calcul : {item.calculated_at_utc} · observation : {item.market_observation_date} · collecte : {item.market_collected_at_utc} · board : {item.board}.
      </p>}
    </div>)}
  </section>
}
