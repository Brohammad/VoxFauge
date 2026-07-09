# Prove Value in 1 Day

Checklist for a pilot team to prove VoxForge support-deflection value without engineering hand-holding.

## Prerequisites

- API running locally or in staging
- Org owner JWT from `/api/v1/auth/register` or `/api/v1/auth/login`
- Dashboard available at `/dashboard`

## Step checklist

1. **Create account + org**
   - Register via `/api/v1/auth/register`
   - Copy the access token

2. **Connect dashboard**
   - Open `/dashboard`
   - Paste JWT and click Connect
   - Confirm Overview loads

3. **Start outcome-first onboarding**
   - Open **Onboarding**
   - Click **1. Start**
   - Click **2. Connect Token**
   - Click **3. Run Sample Call**
   - Expected status: `test_call_passed`
   - Sample call runs through the production `VoicePipelineService` (LLM, TTS,
     evaluation, outcomes) with a scripted billing-contact scenario

4. **Verify business KPIs**
   - Return to **Overview**
   - Confirm cards show:
     - Task Success Rate
     - Escalation Rate
     - Avg Resolution Time
   - Confirm **Outcome Trends** panel has at least one point
   - Toggle **7d / 30d** (trend window should update)

5. **Inspect API source of truth**
   - Call `GET /api/v1/dashboard/outcomes?days=7`
   - Expect:
     - `task_success_rate > 0` after sample call
     - `top_intents` includes `billing_contact_change`
     - `trend` is a non-empty list

6. **Optional quality check**
   - Run: `pytest tests/unit/test_outcome_golden_scenarios.py`
   - Target: accuracy gate passes (>= 90%)

## Pass criteria for the day

- Onboarding sample call completes without help
- Outcome KPIs appear in dashboard within minutes
- Team can explain success vs escalation from Overview
- CEO/ops stakeholder can see trend movement over 7d/30d

## If something fails

- 401 on dashboard: refresh JWT and reconnect
- Empty trend: re-run sample call, then refresh Overview
- Onboarding stuck: check `/api/v1/onboarding/status`, then restart flow from Start
