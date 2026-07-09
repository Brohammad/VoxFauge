from dataclasses import dataclass


@dataclass(frozen=True)
class SampleScript:
    script_id: str
    user_transcript: str
    user_metadata: dict


BILLING_CONTACT_CHANGE = SampleScript(
    script_id="billing_contact_change",
    user_transcript="Hi, I need help changing the billing contact on my account.",
    user_metadata={"intent": "billing_contact_change"},
)


def get_default_sample_script() -> SampleScript:
    return BILLING_CONTACT_CHANGE
