use quant_core::{discount_coupon, discount_coupons};

#[test]
fn batch_matches_individual_calculations() {
    let coupons = [
        (100.0, 365, 0.10),
        (125.50, 30, 0.11),
        (1_000_000.0, 200, 0.075),
    ];

    let batch = discount_coupons(&coupons).unwrap();

    assert_eq!(batch.len(), coupons.len());

    for (index, &(amount, days, rate)) in coupons.iter().enumerate() {
        let individual = discount_coupon(amount, days, rate).unwrap();

        assert_eq!(batch[index], individual);
    }
}

#[test]
fn invalid_coupon_rejects_entire_batch() {
    let coupons = [
        (100.0, 365, 0.10),
        (-50.0, 30, 0.10),
        (200.0, 180, 0.10),
    ];

    assert!(discount_coupons(&coupons).is_err());
}

#[test]
fn empty_batch_returns_empty_results() {
    let result = discount_coupons(&[]).unwrap();

    assert!(result.is_empty());
}
