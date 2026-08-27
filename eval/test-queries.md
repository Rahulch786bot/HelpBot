# HelpBot — Sample Test Queries

These are examples of queries your system should handle correctly. This is not the full set we'll test with — treat it as a baseline sanity check, not a complete spec. Your system should be built to handle the general *categories* of request well (self-serve questions, new tickets, and existing-ticket actions), not just these exact sentences.

## Self-serve questions (expect: answered directly from the knowledge base, with a citation)

1. "How often do I need to reset my password?"
2. "What's the per diem for domestic travel?"
3. "How many days of casual leave do I get per year?"
4. "My laptop screen is flickering, is it covered under warranty?"
5. "Can I claim reimbursement for a client dinner with no receipt?"

## New ticket needed (expect: routed to Ticket agent, ticket created)

6. "My VPN keeps disconnecting every few minutes and restarting the client hasn't fixed it."
7. "I need software installed that isn't on the standard list — how do I request it?"

## Existing ticket — status / escalate / cancel (expect: correct action on the correct ticket)

8. "What's the status of ticket TCK-1015?"
9. "Can you escalate ticket TCK-1016? It's been open too long."
10. "Please cancel ticket TCK-1017, I don't need it anymore."
11. "What's the status of ticket TCK-9999?" (this ticket does not exist — your system should handle this gracefully rather than fabricating a status)
