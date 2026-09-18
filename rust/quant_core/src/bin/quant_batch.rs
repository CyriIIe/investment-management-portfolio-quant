//! Batch discounting interface for Python.
//! Input: one CSV record per line: amount,days,annual_rate
//! Output: one discounted value per line, in the same order.
//! Experimental calculations only; not a complete bond valuation.

use std::io::{self, BufRead, Write};
use quant_core::discount_coupons;

const MAX_COUPONS: usize = 1_000_000;

fn execute() -> Result<(), String> {
    let stdin = io::stdin();
    let mut coupons = Vec::new();

    for (index, line) in stdin.lock().lines().enumerate() {
        let line = line.map_err(|error| error.to_string())?;

        if line.trim().is_empty() {
            return Err(format!("empty input at line {}", index + 1));
        }

        if coupons.len() >= MAX_COUPONS {
            return Err("batch exceeds maximum size".to_string());
        }

        let fields: Vec<&str> = line.split(',').collect();

        if fields.len() != 3 {
            return Err(format!("invalid input at line {}", index + 1));
        }

        let amount = fields[0]
            .trim()
            .parse::<f64>()
            .map_err(|_| format!("invalid amount at line {}", index + 1))?;

        let days = fields[1]
            .trim()
            .parse::<u32>()
            .map_err(|_| format!("invalid days at line {}", index + 1))?;

        let rate = fields[2]
            .trim()
            .parse::<f64>()
            .map_err(|_| format!("invalid rate at line {}", index + 1))?;

        coupons.push((amount, days, rate));
    }

    // Validate the entire batch before writing any result.
    let values = discount_coupons(&coupons)
        .map_err(str::to_string)?;

    let stdout = io::stdout();
    let mut output = io::BufWriter::new(stdout.lock());

    for value in values {
        writeln!(output, "{value:.17e}")
            .map_err(|error| error.to_string())?;
    }

    output.flush().map_err(|error| error.to_string())
}

fn main() {
    if let Err(error) = execute() {
        eprintln!("quant_batch: {error}");
        std::process::exit(1);
    }
}
