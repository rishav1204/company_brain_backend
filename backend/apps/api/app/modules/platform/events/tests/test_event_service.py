from __future__ import annotations

# Re-export legacy static smoke tests + wave2 suite is separate.
from app.modules.platform.events.tests.test_wave2_event_platform import (  # noqa: F401
    test_event_service_module_exists,
    test_queue_manager_has_maxlen,
    test_modular_consumers_package,
)
