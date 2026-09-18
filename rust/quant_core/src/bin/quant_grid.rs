//! Experimental compact scenario grid, for one currency only.
//! Input:
//!   number_of_coupons,number_of_rates
//!   one annual rate per line
//!   then one amount,days record per coupon
//! Output: one present-value total per rate.

use quant_core::discount_coupon;
use std::io::{self, BufRead, Write};

fn execute() -> Result<(), String> {
    let stdin = io::stdin();
    let mut lines = stdin.lock().lines();

    let header = lines
        .next()
        .ok_or("missing header")?
        .map_err(|e| e.to_string())?;

    let parts: Vec<&str> = header.split(',').collect();

    if parts.len() != 2 {
        return Err("invalid header".into());
    }

    let coupon_count = parts[0]
        .trim()
        .parse::<usize>()
        .map_err(|_| "invalid coupon count")?;

    let rate_count = parts[1]
        .trim()
        .parse::<usize>()
        .map_err(|_| "invalid rate count")?;

    if coupon_count == 0 || rate_count == 0 {
        return Err("counts must be positive".into());
    }

    if coupon_count
        .checked_mul(rate_count)
        .ok_or("grid size overflow")?
        > 1_000_000
    {
        return Err("grid exceeds maximum size".into());
    }

    let mut rates = Vec::with_capacity(rate_count);

    for _ in 0..rate_count {
        let line = lines
            .next()
            .ok_or("missing rate")?
            .map_err(|e| e.to_string())?;

        let rate = line
            .trim()
            .parse::<f64>()
            .map_err(|_| "invalid rate")?;

        if !rate.is_finite() || !(0.0..=1.0).contains(&rate) {
            return Err("rate outside supported range".into());
        }

        rates.push(rate);
    }

    let mut coupons = Vec::with_capacity(coupon_count);

    for _ in 0..coupon_count {
        let line = lines
            .next()
            .ok_or("missing coupon")?
            .map_err(|e| e.to_string())?;

        let parts: Vec<&str> = line.split(',').collect();

        if parts.len() != 2 {
            return Err("invalid coupon record".into());
        }

        let amount = parts[0]
            .trim()
            .parse::<f64>()
            .map_err(|_| "invalid amount")?;

        let days = parts[1]
            .trim()
            .parse::<u32>()
            .map_err(|_| "invalid payment date")?;

        // Reuse the existing validated calculation.
        discount_coupon(amount, days, 0.0)
            .map_err(str::to_string)?;

        coupons.push((amount, days));
    }

    if lines.next().is_some() {
        return Err("unexpected additional input".into());
    }

    // Calculate one scenario at a time; return only its total.
    let mut totals = Vec::with_capacity(rate_count);

    for rate in rates {
        let mut total = 0.0_f64;

        for &(amount, days) in &coupons {
            total += discount_coupon(amount, days, rate)
                .map_err(str::to_string)?;
        }

        if !total.is_finite() {
            return Err("non-finite scenario total".into());
        }

        totals.push(total);
    }

    let stdout = io::stdout();
    let mut output = io::BufWriter::new(stdout.lock());

    for total in totals {
        writeln!(output, "{total:.17e}")
            .map_err(|e| e.to_string())?;
    }

    output.flush().map_err(|e| e.to_string())
}

fn main() {
    if let Err(error) = execute() {
        eprintln!("quant_grid: {error}");
        std::process::exit(1);
    }
}
