"""Site-wide totals over the existing per-user database aggregation."""

from pydantic import BaseModel, Field


class SiteUsage(BaseModel):
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    recorded_messages: int = Field(ge=0)
    recorded_users: int = Field(ge=0)


async def site_usage(reader, db):
    # No time, group or user filter: include every user's retained usage record.
    rows = await reader(db=db)
    inputs = sum(row['input_tokens'] for row in rows.values())
    outputs = sum(row['output_tokens'] for row in rows.values())
    return SiteUsage(
        input_tokens=inputs,
        output_tokens=outputs,
        total_tokens=inputs + outputs,
        recorded_messages=sum(row['message_count'] for row in rows.values()),
        recorded_users=len(rows),
    )
