"""Canonical agent run entry — delegates to orchestration pipeline."""

from app.modules.finance_os.agents.pipelines.agent_orchestration_pipeline import agent_orchestration_pipeline

run = agent_orchestration_pipeline.run
