use quant_core::discount_coupon;

fn main() {
    // Données entièrement fictives.
    let cases = [
        (100.0, 365_u32, 0.10),
        (125.50, 30_u32, 0.11),
        (1_000_000.0, 200_u32, 0.075),
    ];

    for (amount, days, rate) in cases {
        let pv = discount_coupon(amount, days, rate)
            .expect("valid fictional test case");

        println!("{amount},{days},{rate},{pv:.12}");
    }
}
