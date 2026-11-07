//! Hand-written PyO3 versions of the hottest function of five wedge corpus modules.
//!
//! This is the "rewrite it in Rust" bar the report compares AIL against.  Each function is
//! the one cProfile puts highest in its module, written the way a PyO3 user would write it:
//! scalars and `Vec<i64>`/`Vec<f64>` in, a scalar out, no Python objects in the inner loop.
use pyo3::prelude::*;

/// tokenizer.count_idents: count identifier runs in source text.
#[pyfunction]
fn count_idents(src: &str) -> i64 {
    let bytes = src.as_bytes();
    let mut n: i64 = 0;
    let mut i = 0usize;
    while i < bytes.len() {
        let c = bytes[i];
        if c.is_ascii_alphabetic() || c == b'_' {
            i += 1;
            while i < bytes.len() {
                let d = bytes[i];
                if d.is_ascii_alphanumeric() || d == b'_' {
                    i += 1;
                } else {
                    break;
                }
            }
            n += 1;
        } else {
            i += 1;
        }
    }
    n
}

/// edit_dist.levenshtein: edit distance between two byte strings.
#[pyfunction]
fn levenshtein(a: &str, b: &str) -> i64 {
    let a = a.as_bytes();
    let b = b.as_bytes();
    let (n, m) = (a.len(), b.len());
    if n == 0 {
        return m as i64;
    }
    if m == 0 {
        return n as i64;
    }
    let mut prev: Vec<i64> = (0..=m as i64).collect();
    let mut cur: Vec<i64> = vec![0; m + 1];
    for j in 1..=n {
        cur[0] = j as i64;
        for k in 1..=m {
            cur[k] = if a[j - 1] == b[k - 1] {
                prev[k - 1]
            } else {
                let mut best = prev[k];
                if prev[k - 1] < best {
                    best = prev[k - 1];
                }
                if cur[k - 1] < best {
                    best = cur[k - 1];
                }
                best + 1
            };
        }
        std::mem::swap(&mut prev, &mut cur);
    }
    prev[m]
}

/// float_loops.dot: dot product of two f64 lists.
#[pyfunction]
fn dot(a: Vec<f64>, b: Vec<f64>) -> f64 {
    let mut acc = 0.0f64;
    let n = a.len().min(b.len());
    for i in 0..n {
        acc += a[i] * b[i];
    }
    acc
}

/// matrix.mat_mul: dense n x n integer matrix product over flat lists.
#[pyfunction]
fn mat_mul(a: Vec<i64>, b: Vec<i64>, n: usize) -> Vec<i64> {
    let mut out = vec![0i64; n * n];
    for i in 0..n {
        for k in 0..n {
            let av = a[i * n + k];
            if av == 0 {
                continue;
            }
            for j in 0..n {
                out[i * n + j] += av * b[k * n + j];
            }
        }
    }
    out
}

/// rolling_stats.window_sums: rolling window sums over a list of ints.
#[pyfunction]
fn window_sums(xs: Vec<i64>, w: usize) -> Vec<i64> {
    let mut out: Vec<i64> = Vec::with_capacity(xs.len());
    let mut acc: i64 = 0;
    for (i, &x) in xs.iter().enumerate() {
        acc += x;
        if i >= w {
            acc -= xs[i - w];
        }
        if i + 1 >= w {
            out.push(acc);
        }
    }
    out
}

#[pymodule]
fn hotrust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(count_idents, m)?)?;
    m.add_function(wrap_pyfunction!(levenshtein, m)?)?;
    m.add_function(wrap_pyfunction!(dot, m)?)?;
    m.add_function(wrap_pyfunction!(mat_mul, m)?)?;
    m.add_function(wrap_pyfunction!(window_sums, m)?)?;
    Ok(())
}
