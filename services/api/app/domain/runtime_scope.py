import os

from app.domain.gates import SYNTHETIC_DEMO_RUNTIME_SCOPE

# No configured value grants the synthetic-demo policy authority over a production pointer.
_ENV_NAME = "EXECUTION_OPTIMIZER_RUNTIME_SCOPE"


def server_runtime_scope() -> str:
    """Read deployment configuration. The default is the synthetic demo, not production."""
    return os.environ.get(_ENV_NAME, SYNTHETIC_DEMO_RUNTIME_SCOPE)
