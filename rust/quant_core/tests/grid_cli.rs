use std::io::Write;
use std::process::{Command, Stdio};

fn run_grid(input: &str) -> std::process::Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_quant_grid"))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("quant_grid executable");

    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(input.as_bytes())
        .expect("write input");

    child.wait_with_output().expect("wait for quant_grid")
}

#[test]
fn compact_grid_matches_reference_formula() {
    let output = run_grid("2,2\n0.10\n0.11\n100,365\n125.50,30\n");

    assert!(output.status.success());

    let text = String::from_utf8(output.stdout).unwrap();
    let values: Vec<f64> = text
        .lines()
        .map(|line| line.parse::<f64>().unwrap())
        .collect();

    assert_eq!(values.len(), 2);

    for (&actual, rate) in values.iter().zip([0.10_f64, 0.11_f64]) {
        let expected =
            100.0 * (-rate).exp()
            + 125.50 * (-rate * 30.0 / 365.0).exp();

        assert!((actual - expected).abs() < 1e-10);
    }
}

#[test]
fn higher_rate_reduces_coupon_total() {
    let output = run_grid("1,2\n0.10\n0.11\n100,365\n");

    assert!(output.status.success());

    let text = String::from_utf8(output.stdout).unwrap();
    let values: Vec<f64> = text
        .lines()
        .map(|line| line.parse::<f64>().unwrap())
        .collect();

    assert_eq!(values.len(), 2);
    assert!(values[1] < values[0]);
}

#[test]
fn invalid_input_is_rejected_without_results() {
    let output = run_grid("1,1\n0.10\n-100,365\n");

    assert!(!output.status.success());
    assert!(output.stdout.is_empty());
}
