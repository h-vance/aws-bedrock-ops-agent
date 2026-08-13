import os

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from triage_core import IncidentBundle, TriageResult, run_triage

BEDROCK_MOCK = os.getenv("BEDROCK_MOCK", "true").lower() == "true"

# The SDK auto-enables Host/Origin allowlisting for DNS-rebinding protection, but
# only when it thinks it's bound to localhost. Since this is mounted behind a real
# public domain on Render, that allowlist must be configured explicitly here —
# otherwise every request in production 421s once the default localhost-only
# allowlist doesn't match the deployed Host header.
_ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv(
        "MCP_ALLOWED_HOSTS",
        "127.0.0.1:*,localhost:*,[::1]:*",
    ).split(",")
    if h.strip()
]
_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "MCP_ALLOWED_ORIGINS",
        "http://127.0.0.1:*,http://localhost:*,http://[::1]:*",
    ).split(",")
    if o.strip()
]

class TriageToolResult(TriageResult):
    incident_id: str
    mode: str


mcp_server = MCPServer(
    name="bedrock-ops-triage",
    title="Bedrock Ops Triage",
    instructions=(
        "Triage an incident evidence bundle and return ranked hypotheses, "
        "recommended checks, and escalation-ready notes for a support engineer."
    ),
)


@mcp_server.tool()
async def triage_incident(bundle: IncidentBundle) -> TriageToolResult:
    """Analyze an incident evidence bundle and return structured triage output."""
    return TriageToolResult.model_validate(run_triage(bundle, mock=BEDROCK_MOCK))


def streamable_http_app():
    return mcp_server.streamable_http_app(
        streamable_http_path="/",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=_ALLOWED_HOSTS,
            allowed_origins=_ALLOWED_ORIGINS,
        ),
    )


if __name__ == "__main__":
    mcp_server.run(transport="stdio")
