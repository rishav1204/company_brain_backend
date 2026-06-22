"""Domain policy seed definitions for M34 bootstrap."""

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
