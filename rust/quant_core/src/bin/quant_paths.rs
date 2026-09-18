//! Experimental batch discounting of known coupons over fictional rate paths.
//! One currency per invocation. No principal, calibration, or portfolio risk.

use quant_core::path::discount_coupon_on_path;
use std::io::{self, Read};

const MAX_COUPONS: usize = 10_000;
const MAX_PATHS: usize = 10_000;
const MAX_CALCULATIONS: usize = 2_000_000;

fn parse_usize(value: &str) -> Result<usize, String> {
    value
        .trim()
        .parse::<usize>()
        .map_err(|_| "invalid count".to_string())
}

fn parse_number(value: &str) -> Result<f64, String> {
    let number = value
        .trim()
        .parse::<f64>()
        .map_err(|_| "invalid decimal number".to_string())?;

    if !number.is_finite() {
        return Err("non-finite number".to_string());
    }

    Ok(number)
}

fn calculate(input: &str) -> Result<String, String> {
    let mut lines = input.lines();

    let header = lines
        .next()
        .ok_or_else(|| "missing header".to_string())?;

    let (coupon_count_text, path_count_text) = header
        .split_once(',')
        .ok_or_else(|| "expected coupon_count,path_count".to_string())?;

    let coupon_count = parse_usize(coupon_count_text)?;
    let path_count = parse_usize(path_count_text)?;

    if coupon_count == 0
        || path_count == 0
        || coupon_count > MAX_COUPONS
        || path_count > MAX_PATHS
        || coupon_count
            .checked_mul(path_count)
            .is_none_or(|count| count > MAX_CALCULATIONS)
    {
        return Err("unsupported batch size".to_string());
    }

    let mut paths = Vec::with_capacity(path_count);

    for _ in 0..path_count {
        let mut rates = [0.0_f64; 13];

        for rate in &mut rates {
            let line = lines
                .next()
                .ok_or_else(|| "missing rate observation".to_string())?;

            *rate = parse_number(line)?;

            if !(0.0..=1.0).contains(rate) {
                return Err("rate outside supported range".to_string());
            }
        }

        paths.push(rates);
    }

    let mut coupons = Vec::with_capacity(coupon_count);

    for _ in 0..coupon_count {
        let line = lines
            .next()
            .ok_or_else(|| "missing coupon".to_string())?;

        let (amount_text, days_text) = line
            .split_once(',')
            .ok_or_else(|| "expected amount,days".to_string())?;

        let amount = parse_number(amount_text)?;
        let days = days_text
            .trim()
            .parse::<u32>()
            .map_err(|_| "invalid payment day".to_string())?;

        if amount < 0.0 || !(1..=365).contains(&days) {
            return Err("invalid coupon".to_string());
        }

        coupons.push((amount, days));
    }

    if lines.next().is_some() {
        return Err("unexpected extra input".to_string());
    }

    // Validate and calculate the complete batch before writing any output.
    let mut output = String::new();

    for rates in &paths {
        let mut total = 0.0_f64;

        for &(amount, days) in &coupons {
            let value = discount_coupon_on_path(amount, days, rates)
                .map_err(str::to_string)?;

            total += value;

            if !total.is_finite() {
                return Err("non-finite aggregate value".to_string());
            }
        }

        output.push_str(&format!("{total:.17e}\n"));
    }

    Ok(output)
}

fn main() {
    let mut input = String::new();

    if let Err(error) = io::stdin().read_to_string(&mut input) {
        eprintln!("input error: {error}");
        std::process::exit(1);
    }

    match calculate(&input) {
        Ok(output) => print!("{output}"),
        Err(error) => {
            eprintln!("batch rejected: {error}");
            std::process::exit(1);
        }
    }
}
