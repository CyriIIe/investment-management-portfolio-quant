use quant_core::path::discount_coupon_on_path;

fn main() {
    let constant = [0.10_f64; 13];

    let mut variable = [0.0_f64; 13];
    for rate in variable.iter_mut().skip(6) {
        *rate = 0.20;
    }

    let mut changed_endpoint = constant;
    changed_endpoint[12] = 0.90;

    let cases = [
        (100.0, 365_u32, constant),
        (100.0, 365_u32, variable),
        (125.50, 30_u32, variable),
        (100.0, 365_u32, changed_endpoint),
    ];

    for (amount, days, rates) in cases {
        let value = discount_coupon_on_path(amount, days, &rates)
            .expect("valid fictional case");

        println!("{value:.17e}");
    }
}
