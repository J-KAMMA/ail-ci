use std::env;
use std::path::{Path, PathBuf};
use std::process::Command;

const LIBRARY: &str = "raiser";

fn repo_root(start: &Path) -> PathBuf {
    for dir in start.ancestors() {
        if dir.join("AIL_CURRENT").join("ail_embed.py").is_file() {
            return dir.to_path_buf();
        }
    }
    panic!("cannot find the repository root above {}", start.display());
}

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").expect("CARGO_MANIFEST_DIR"));
    let repo = repo_root(&manifest);
    let module = manifest.parent().expect("the example directory").join("mod.py");
    let tool = repo.join("AIL_CURRENT").join("ail_embed.py");
    let out = PathBuf::from(env::var("OUT_DIR").expect("OUT_DIR"));
    let python = env::var("AIL_PYTHON").unwrap_or_else(|_| String::from("python3"));
    println!("cargo:rerun-if-changed={}", module.display());
    println!("cargo:rerun-if-changed={}", tool.display());
    let status = Command::new(&python)
        .arg("-B")
        .arg(&tool)
        .arg("build")
        .arg(&module)
        .arg("-o")
        .arg(&out)
        .status()
        .unwrap_or_else(|error| panic!("cannot run {}: {}", python, error));
    assert!(status.success(), "ail_embed.py failed for {}", module.display());
    println!("cargo:rustc-link-search=native={}", out.display());
    println!("cargo:rustc-link-lib=static={}", LIBRARY);
    println!("cargo:rustc-link-lib=m");
}
