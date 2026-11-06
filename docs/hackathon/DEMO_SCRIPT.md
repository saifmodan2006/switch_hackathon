# Live demonstration: request to approved proposal

Target length: 3–5 minutes. Rehearse with an actual configured Switch/Mattermost deployment, real model and Mailpit. Do not present the deterministic CI fixtures as live inference.

## Before recording

- Finish `switch/onboarding/README.md`; all six agents have real identities, verified participant mappings and operations-hub membership.
- Use a labeled synthetic customer and approved internal service capability document. Configure a sandbox recipient captured only in Mailpit.
- Confirm Switch and model connection tests; verify actual runtime heartbeats. Open the real Mattermost operations-hub, SwitchOps, and actual Mailpit inbox in tabs.
- Start fresh so measured metrics correspond to this run. Never reset real customer data for a demo.

## 0:00–0:40 — the problem and the room

Speaking: “A customer request often gets lost between CRM, research, a draft and someone’s approval. SwitchOps keeps the business record durable while Switch keeps the team’s collaboration visible.”

Show the actual Mattermost room and all six distinct identities. Send as the mapped human:

`@ops-coordinator Acme Solutions needs a workflow automation proposal. Research the approved records and service document, prepare a grounded proposal, and ask me before sending anything.`

Use the exact seeded customer name so the match is unambiguous. Alternatively create the request in Command Center, select that customer and show its actual room post.

## 0:40–1:50 — actual handoffs

Show coordinator triage → customer intelligence → research → communications → quality. Point to real addressed messages, cited record IDs and persisted workflow events, not screenshots of a prior test. If the model needs information or quality finds unsupported claims, show the real error/revision path; do not skip it or fabricate success.

Speaking: “Each specialist has a separate Switch identity. The next agent starts from the genuine addressed room event. There’s no hidden private agent pipeline.”

## 1:50–2:40 — the human decision

Open the generated proposal in the workflow detail, download its Markdown/PDF and show the version. Open Approvals and inspect the exact recipient and content. Demonstrate that no outbound email exists yet. Approve as an authorized human, or request changes first if time allows. Show the persisted actor/reason/hash and new approval requirement after edits.

Speaking: “The reviewer checks quality. I authorize the actual action. A chat message or an agent cannot approve a send.”

## 2:40–3:30 — authorized result

Show the exact approved message captured in the actual Mailpit inbox. Say “captured by the development email sink,” never “delivered to the customer.” Show communications → scheduling → coordinator room handoffs, saved internal follow-up task/event and final workflow outcome. External availability is explicitly unknown unless a live calendar was queried.

Show updated persisted analytics and reopen the workflow timeline. Switch retains the genuine conversation; SQL retains the business decision history.

## 3:30–4:30 — dependency demonstration

Stop/disconnect the actual Switch server using its supported management UI. Create a new request. Show that the request persists, then visibly blocks, and no new specialist handoff/model execution happens through a substitute route. Existing CRM stays readable. Restore Switch, show real heartbeats, explicitly retry and inspect the resumed new attempt.

Speaking: “Switch is an architectural dependency. When it is unavailable, collaboration stops visibly.”

## Evidence checklist

Capture actual server version, two distinct agent IDs, real room URL, Switch message references, workflow ID, generated document version, human approval actor, sandbox message ID, follow-up record and final state. Record commands and results in `docs/VERIFICATION.md`. A live recording and public links have not been produced by this build.
