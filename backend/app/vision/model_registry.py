"""
ModelRegistry — thread-safe singleton for InsightFace FaceAnalysis.

The model is loaded ONCE per process. Subsequent calls to get() return the
same object without reloading. This is mandatory: loading per-frame would
cause unacceptable latency and GPU/CPU resource leaks.

Usage:
    registry = ModelRegistry.instance()
    app = registry.get()          # FaceAnalysis object ready for inference
    faces = app.get(frame)        # list of insightface Face objects
"""
import logging
import os
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy import to allow the module to load even when insightface is not
# installed (test environments with mocked models).
try:
    import insightface
    from insightface.app import FaceAnalysis

    _INSIGHTFACE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _INSIGHTFACE_AVAILABLE = False
    FaceAnalysis = None  # type: ignore[assignment,misc]


class ModelRegistry:
    """
    Thread-safe singleton wrapper around InsightFace FaceAnalysis.

    The singleton is stored on the class so it survives import caching.
    Calling ModelRegistry.instance() always returns the same registry.
    The underlying FaceAnalysis object is initialised on the first call
    to get(); subsequent calls are O(1) dictionary lookups.
    """

    _instance: Optional["ModelRegistry"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "ModelRegistry":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._app: Optional[object] = None  # type: ignore[assignment]
                obj._load_count: int = 0
                obj._init_lock: threading.Lock = threading.Lock()
                cls._instance = obj
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def instance(cls) -> "ModelRegistry":
        """Return the singleton ModelRegistry."""
        return cls()

    def get(
        self,
        model_name: Optional[str] = None,
        det_size: Optional[tuple] = None,
        allowed_modules: Optional[list] = None,
        providers: Optional[list] = None,
    ) -> object:
        """
        Return the FaceAnalysis application object, loading it if necessary.

        Parameters
        ----------
        model_name : str, optional
            InsightFace model pack name. Defaults to env INSIGHTFACE_MODEL_NAME
            (then 'buffalo_s').
        det_size : tuple, optional
            Detector input size (H, W). Defaults to env DET_SIZE (then 640).
        allowed_modules : list, optional
            Modules to load. Defaults to ['detection', 'recognition'].
        providers : list, optional
            ONNX execution providers. Defaults to ['CPUExecutionProvider'].

        Returns
        -------
        FaceAnalysis
            Prepared InsightFace application object.

        Raises
        ------
        RuntimeError
            If InsightFace is not installed.
        """
        if self._app is not None:
            return self._app

        with self._init_lock:
            # Double-checked locking
            if self._app is not None:
                return self._app

            if not _INSIGHTFACE_AVAILABLE:
                raise RuntimeError(
                    "insightface is not installed. "
                    "Run: pip install insightface"
                )

            # Resolve config from environment if not provided
            if model_name is None:
                model_name = os.environ.get("INSIGHTFACE_MODEL_NAME", "buffalo_s")
            if det_size is None:
                size_val = int(os.environ.get("DET_SIZE", "640"))
                det_size = (size_val, size_val)
            if allowed_modules is None:
                allowed_modules = ["detection", "recognition"]
            if providers is None:
                provider = os.environ.get("ONNX_PROVIDER", "CPUExecutionProvider")
                providers = [provider]

            # Allow custom INSIGHTFACE_HOME
            insightface_home = os.environ.get("INSIGHTFACE_HOME")
            if insightface_home:
                os.environ["INSIGHTFACE_HOME"] = insightface_home

            logger.info(
                "Loading InsightFace model '%s' (modules=%s, providers=%s, det_size=%s)",
                model_name,
                allowed_modules,
                providers,
                det_size,
            )
            t0 = time.perf_counter()
            app = FaceAnalysis(
                name=model_name,
                allowed_modules=allowed_modules,
                providers=providers,
            )
            # ctx_id=-1 forces CPU; det_size controls detector input resolution
            app.prepare(ctx_id=-1, det_size=det_size)
            elapsed = time.perf_counter() - t0
            self._load_count += 1
            logger.info(
                "InsightFace model loaded in %.2f s (load_count=%d)",
                elapsed,
                self._load_count,
            )
            self._app = app
        return self._app  # type: ignore[return-value]

    @property
    def load_count(self) -> int:
        """Number of times the model has been (re)loaded (should be 1)."""
        return self._load_count

    def reset(self) -> None:
        """
        Release the loaded model and reset the singleton state.

        **Only for testing.** Never call in production — it defeats the
        singleton guarantee and causes races in concurrent code.
        """
        with self._init_lock:
            self._app = None
            self._load_count = 0
