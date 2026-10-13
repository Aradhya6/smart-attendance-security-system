"""
scripts/check_models.py — Download and verify InsightFace model weights.

Run before starting the application on a new machine:
    python scripts/check_models.py

Downloads the configured model pack into INSIGHTFACE_HOME (default:
%USERPROFILE%/.insightface) if not already present. Never stores weights
inside the repository.
"""
import os
import sys
import time

# Add repo root to path so backend imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    model_name = os.environ.get("INSIGHTFACE_MODEL_NAME", "buffalo_s")
    insightface_home = os.environ.get(
        "INSIGHTFACE_HOME",
        os.path.join(os.path.expanduser("~"), ".insightface"),
    )
    os.environ["INSIGHTFACE_HOME"] = insightface_home

    print(f"[check_models] Model pack : {model_name}")
    print(f"[check_models] Model home : {insightface_home}")
    print()

    # Check if weights already exist
    model_dir = os.path.join(insightface_home, "models", model_name)
    if os.path.isdir(model_dir) and os.listdir(model_dir):
        print(f"[check_models] ✓ Model directory exists: {model_dir}")
        files = os.listdir(model_dir)
        print(f"[check_models]   Files: {files}")
    else:
        print(f"[check_models] Model directory not found or empty: {model_dir}")
        print(f"[check_models] Will attempt download (requires internet, ~280 MB for buffalo_l / ~60 MB for buffalo_s)...")

    try:
        from insightface.app import FaceAnalysis
    except ImportError:
        print("[check_models] ERROR: insightface not installed.")
        print("  Run: pip install insightface")
        sys.exit(1)

    print("[check_models] Loading model (this may download weights on first run)...")
    t0 = time.perf_counter()
    try:
        app = FaceAnalysis(
            name=model_name,
            allowed_modules=["detection", "recognition"],
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=-1, det_size=(640, 640))
        elapsed = time.perf_counter() - t0
        print(f"[check_models] ✓ Model loaded successfully in {elapsed:.2f}s")
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        print(f"[check_models] ERROR loading model after {elapsed:.2f}s: {exc}")
        print()
        print("Manual download instructions:")
        print(f"  1. Create directory: {model_dir}")
        print(f"  2. Download from: https://github.com/deepinsight/insightface/releases")
        print(f"  3. Extract model files to: {model_dir}")
        sys.exit(1)

    # Quick functional test with blank frame
    import numpy as np
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    faces = app.get(blank)
    print(f"[check_models] ✓ Inference test: {len(faces)} faces in blank frame (expected 0)")
    print()
    print("[check_models] Model check PASSED. System ready.")


if __name__ == "__main__":
    main()
