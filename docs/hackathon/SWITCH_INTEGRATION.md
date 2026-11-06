# Switch is the collaboration layer

SwitchOps AI coordinates business requests in genuine Switch Rooms. The business database owns transactional records; Switch owns room conversation, shared context, participant identity, addressing and human/agent visibility. This project does not implement a replacement Switch service.

## Actual contract used

The adapter implements the currently published [agent protocol](https://docs.switchagents.ai/switch-rooms/internals/agent-protocol), [connection frames](https://docs.switchagents.ai/switch-rooms/internals/agent-connection) and [event payloads](https://docs.switchagents.ai/switch-rooms/internals/agent-events):

- One-time `POST /agents` using a separate registration credential and `always_on` integration profile; no overwrite or accidental rotation.
- Bearer-authenticated WebSocket `/agents/{id}/connection/ws`, stable connection ID, rooms supplied at open, persisted cursor, `expected_generation` and authoritative connection state.
- Pings serviced promptly with cursor-bearing pongs while slow inference runs in a separate durable consumer.
- Discovered HTTP operations catalog; `update_agent_detail` sets peer addressing where supported.
- Genuine `/agents/{id}/message` posts with explicit @specialist mentions and stable workflow/handoff identifiers.
- Received messages require addressed=true, expected room, exact opaque predecessor participant and current workflow expectation.
- Reconnection with backoff; no retry takeover loops, silent gap recovery or simulated fallback.

No latest installed Switch version is claimed: no server was present during the build. The adapter targets published released behavior, and live startup/version compatibility is an explicit verification requirement. The repository snapshot of the template language was used only to inspect version-1 syntax; it does not establish an installed server version.

## Agents and rooms

Six identities: ops-coordinator, customer-intelligence, research-specialist, communications-specialist, quality-reviewer and scheduling-specialist. Each has its own scoped prompt, credential and connection/cursor. Registration is done through the dashboard; imported identities can be mapped without re-registration.

The official-format group template creates operations-hub, customer-requests, research-desk, approvals and scheduling. The flagship workflow includes all six agents in operations-hub so its complete conversation is inspectable in one room. Topical rooms retain narrower membership. Their mappings are navigation/context, not a claim of unsupported membership synchronization.

## Human collaboration and decisions

A human can start work in the dashboard or address the coordinator from genuine Mattermost. A room request requires an exact verified identity mapping to a non-viewer organization member. An unambiguous existing CRM customer match starts work; missing or ambiguous matches visibly need information.

Human approval is authenticated in the dashboard. The exact version, recipient, content hash, expiry, actor and decision reason persist. The room receives the review link. An AI quality review is not human authorization. Chat text saying approved is never accepted as authorization.

## Dependency demonstration

1. Configure the actual Switch server, mapped room/participants and real model.
2. Start the runtime and verify real heartbeats, messages and a multi-agent proposal workflow.
3. Disconnect/stop Switch using its supported administration surface.
4. Create another request. It persists, but no cross-agent work continues through another channel; the workflow becomes BLOCKED with a Switch error and model-call count remains zero for a request that never dispatched.
5. Restore Switch, wait for real heartbeats and explicitly retry. Persistent customer records remained readable throughout.

The automated suite asserts the disconnected behavior and verifies handoff frames with controlled HTTP/network/model fixtures. **Those fixtures are not evidence of a live Switch run.** Follow [the onboarding guide](../../switch/onboarding/README.md) and [demo script](DEMO_SCRIPT.md) for the live acceptance run.
