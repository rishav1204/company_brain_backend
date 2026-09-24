"""Bootstrap-only policy templates (not runtime authority).

Runtime evaluation reads rows from governance.policies / approval_matrix only.
Amount thresholds in these Python files are defaults; prefer platform.regulatory_param
keys governance.* when present (see bootstrap_governance_policies).
"""

from app.modules.platform.governance.policies.agent_policies import AGENT_POLICIES
from app.modules.platform.governance.policies.ap_policies import AP_POLICIES
from app.modules.platform.governance.policies.banking_policies import BANKING_POLICIES
from app.modules.platform.governance.policies.close_policies import CLOSE_POLICIES
from app.modules.platform.governance.policies.gst_policies import GST_POLICIES
from app.modules.platform.governance.policies.journal_policies import JOURNAL_POLICIES
from app.modules.platform.governance.policies.treasury_policies import TREASURY_POLICIES

ALL_SEED_POLICIES = (
    BANKING_POLICIES
    + TREASURY_POLICIES
    + JOURNAL_POLICIES
    + AP_POLICIES
    + GST_POLICIES
    + CLOSE_POLICIES
    + AGENT_POLICIES
)

__all__ = ["ALL_SEED_POLICIES"]
