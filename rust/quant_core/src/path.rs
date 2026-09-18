//! Experimental discounting along a fictional interest-rate path.
//! This is not a complete bond valuation or portfolio risk measure.

const DAYS_PER_YEAR: f64 = 365.0;
const MONTHS: usize = 12;

/// Discount one known coupon along 12 equal intervals over 365 days.
///
/// `rates` contains 13 observations. The first 12 apply to the
/// corresponding intervals; the final observation is an endpoint.
///
/// Rates are annual decimal fractions; 0.10 means 10%.
pub fn discount_coupon_on_path(
    gross_amount: f64,
    days_until_payment: u32,
    rates: &[f64],
) -> Result<f64, &'static str> {
    if !gross_amount.is_finite() || gross_amount < 0.0 {
        return Err("invalid coupon amount");
    }

    if days_until_payment == 0 || days_until_payment > 365 {
        return Err("payment outside supported horizon");
    }

    if rates.len() != MONTHS + 1 {
        return Err("expected 13 rate observations");
    }

    if rates
        .iter()
        .any(|rate| !rate.is_finite() || !(0.0..=1.0).contains(rate))
    {
        return Err("invalid rate observation");
    }

    let payment_day = f64::from(days_until_payment);
    let interval_days = DAYS_PER_YEAR / MONTHS as f64;
    let mut accumulated_rate_days = 0.0_f64;

    for (month, &rate) in rates.iter().take(MONTHS).enumerate() {
        let start = month as f64 * interval_days;
        let end = (month + 1) as f64 * interval_days;
        let duration = payment_day.min(end) - start;

        if duration <= 0.0 {
            break;
        }

        accumulated_rate_days += rate * duration;
    }

    let value =
        gross_amount * (-accumulated_rate_days / DAYS_PER_YEAR).exp();

    if !value.is_finite() {
        return Err("non-finite present value");
    }

    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::discount_coupon_on_path;

    #[test]
    fn constant_path_matches_flat_rate() {
        let rates = [0.10_f64; 13];
        let actual = discount_coupon_on_path(100.0, 365, &rates).unwrap();
        let expected = 100.0 * (-0.10_f64).exp();

        assert!((actual - expected).abs() < 1e-10);
    }

    #[test]
    fn piecewise_path_uses_each_period() {
        let mut rates = [0.0_f64; 13];

        for rate in rates.iter_mut().skip(6) {
            *rate = 0.20;
        }

        let actual = discount_coupon_on_path(100.0, 365, &rates).unwrap();
        let expected = 100.0 * (-0.10_f64).exp();

        assert!((actual - expected).abs() < 1e-10);
    }

    #[test]
    fn final_observation_does_not_change_value() {
        let first = [0.10_f64; 13];
        let mut second = first;
        second[12] = 0.90;

        assert_eq!(
            discount_coupon_on_path(100.0, 365, &first).unwrap(),
            discount_coupon_on_path(100.0, 365, &second).unwrap()
        );
    }

    #[test]
    fn invalid_inputs_are_rejected() {
        let rates = [0.10_f64; 13];

        assert!(discount_coupon_on_path(-100.0, 365, &rates).is_err());
        assert!(discount_coupon_on_path(100.0, 0, &rates).is_err());
        assert!(discount_coupon_on_path(100.0, 366, &rates).is_err());
        assert!(discount_coupon_on_path(100.0, 365, &rates[..12]).is_err());

        let mut invalid_rates = rates;
        invalid_rates[0] = f64::NAN;

        assert!(
            discount_coupon_on_path(100.0, 365, &invalid_rates).is_err()
        );
    }
}
