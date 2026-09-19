export default function MethodologyPanel() {
  return (
    <section className="panel section-panel">
      <div className="panel-kicker">CADRE DE RECHERCHE</div>
      <h2>Méthodologie du prototype</h2>
      <p>
        Portfolio Quant conserve des cycles expérimentaux reproductibles.
        Le moteur actuel sert à vérifier une chaîne de calcul, pas à produire
        une estimation validée de la valeur ou du risque du portefeuille.
      </p>

      <div className="methodology-grid">
        <article className="methodology-item">
          <div className="panel-kicker">01 / PÉRIMÈTRE</div>
          <h3>Coupons connus uniquement</h3>
          <p>
            Le calcul utilise les flux de coupons disponibles dans les données
            lues du CORE. Les échéanciers inconnus ne sont pas assimilés à zéro.
            Il ne s’agit pas d’une valorisation complète du portefeuille.
          </p>
        </article>

        <article className="methodology-item">
          <div className="panel-kicker">02 / SCÉNARIOS</div>
          <h3>Trajectoires fictives</h3>
          <p>
            Le moteur Rust génère des trajectoires de taux à partir de
            paramètres expérimentaux. Ces trajectoires ne sont pas des
            prévisions et le modèle n’est pas calibré au marché.
          </p>
        </article>

        <article className="methodology-item">
          <div className="panel-kicker">03 / DONNÉES OBSERVÉES</div>
          <h3>Taux directeur de la BCR</h3>
          <p>
            L’onglet Données présente des observations historiques, avec
            leurs dates d’effet et de collecte. Leur présence dans la base
            ne signifie pas qu’elles calibrent les trajectoires du moteur,
            ni qu’elles déterminent les coupons variables.
          </p>
        </article>

        <article className="methodology-item">
          <div className="panel-kicker">04 / TRAÇABILITÉ</div>
          <h3>Cycles identifiés et dédupliqués</h3>
          <p>
            Une identité déterministe distingue les entrées et paramètres
            des cycles. Un cycle déjà enregistré n’est pas recalculé ;
            les résultats restent dans la base Quant séparée.
          </p>
        </article>
      </div>

      <div className="notice methodology-warning">
        <span className="notice-icon" aria-hidden="true">i</span>
        <div>
          <strong>Limites actuelles</strong>
          <p>
            Aucune calibration au marché, aucune valorisation complète et
            aucune mesure de risque validée. L’interface est en lecture seule
            et ne permet pas de passer des ordres.
          </p>
        </div>
      </div>
    </section>
  )
}
