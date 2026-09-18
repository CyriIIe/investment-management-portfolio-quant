//! Experimental Rust calculation kernel.
//! Financial production use requires numerical parity checks with Python.

/// Present value of one known coupon, using continuous compounding.
///
/// `days_until_payment` is measured from the portfolio snapshot date.
/// Rates are decimal fractions: 0.10 means 10% annually.
///
/// This function does not calculate a bond price or a portfolio value.
pub fn discount_coupon(
    gross_amount: f64,
    days_until_payment: u32,
    annual_rate: f64,
) -> Result<f64, &'static str> {
    if !gross_amount.is_finite() || gross_amount < 0.0 {
        return Err("invalid coupon amount");
    }

    if days_until_payment == 0 || days_until_payment > 365 {
        return Err("payment outside the supported horizon");
    }

    if !annual_rate.is_finite() || !(0.0..=1.0).contains(&annual_rate) {
        return Err("invalid annual rate");
    }

    let years = f64::from(days_until_payment) / 365.0;
    let present_value = gross_amount * (-annual_rate * years).exp();

    if !present_value.is_finite() {
        return Err("non-finite present value");
    }

    Ok(present_value)
}

#[cfg(test)]
mod tests {
    use super::discount_coupon;

    #[test]
    fn zero_rate_preserves_amount() {
        assert_eq!(discount_coupon(100.0, 365, 0.0).unwrap(), 100.0);
    }

    #[test]
    fn one_year_coupon_matches_reference_formula() {
        let actual = discount_coupon(100.0, 365, 0.10).unwrap();
        let expected = 100.0 * (-0.10_f64).exp();

        assert!((actual - expected).abs() < 1e-12);
    }

    #[test]
    fn higher_rate_reduces_present_value() {
        let low = discount_coupon(100.0, 365, 0.10).unwrap();
        let high = discount_coupon(100.0, 365, 0.11).unwrap();

        assert!(high < low);
    }

    #[test]
    fn invalid_inputs_are_rejected() {
        assert!(discount_coupon(f64::NAN, 365, 0.10).is_err());
        assert!(discount_coupon(-100.0, 365, 0.10).is_err());
        assert!(discount_coupon(100.0, 0, 0.10).is_err());
        assert!(discount_coupon(100.0, 366, 0.10).is_err());
        assert!(discount_coupon(100.0, 365, -0.01).is_err());
    }
}

/// Discount a batch of known coupons using the same validated formula.
///
/// Each tuple contains (gross amount, days until payment, annual rate).
/// Returns an error if any input is invalid; no partial result is returned.
pub fn discount_coupons(
    coupons: &[(f64, u32, f64)],
) -> Result<Vec<f64>, &'static str> {
    coupons
        .iter()
        .map(|&(amount, days, rate)| discount_coupon(amount, days, rate))
        .collect()
}

pub mod path;
