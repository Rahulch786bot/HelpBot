# Nimbus Corp — IT Policy & FAQ

**Document owner:** IT Operations
**Last updated:** March 2026

## 1. VPN Access

All employees accessing internal systems remotely must use the Nimbus VPN client.

- New employees: VPN access is provisioned automatically within 24 hours of your start date. If you haven't received credentials by day 2, raise a ticket with category "IT — Access."
- VPN credentials expire every 90 days and must be renewed via the self-service portal at `vpn.nimbuscorp.internal`.
- Contractors and interns require manager approval before VPN access is granted. Approval requests go through the manager's Nimbus HR portal, not IT.
- If VPN access is not working, first check that you are on a Nimbus-managed device with the latest client version (6.2 or above). If the issue persists after a restart, raise a ticket.

## 2. Password Resets

- Passwords must be reset every 60 days. You'll receive an automated reminder 5 days before expiry.
- Self-service password reset is available at `reset.nimbuscorp.internal` using your registered personal email for verification.
- If self-service reset fails twice, raise an IT ticket — do not attempt more than 2 resets in a 24-hour window, as this will lock your account for 1 hour.
- Locked accounts unlock automatically after 1 hour, or can be unlocked immediately by IT during business hours (9 AM–6 PM IST, Mon–Fri).

## 3. Laptop & Hardware

- Standard issue laptops are replaced on a **3-year refresh cycle** from the date of issue.
- Engineering and Design roles are eligible for a hardware upgrade request (not a full replacement) after 18 months if the current device no longer meets role requirements (e.g., insufficient RAM for local builds). This requires manager sign-off.
- Hardware damage (screen, keyboard, battery) is covered under warranty for the first 12 months. After that, repairs are chargeable unless due to manufacturing defect.
- Lost or stolen devices must be reported to IT **within 24 hours**. Failure to report promptly may result in the replacement cost being charged to the employee.

## 4. Software Requests

- Standard software (Slack, Zoom, VS Code, Office 365) is pre-installed on all company devices.
- Non-standard software requires a ticket with business justification and manager approval attached.
- Open-source packages for engineering use do not require approval but must go through the internal package proxy for security scanning.

## 5. Common Issues & Self-Help

| Issue | First Step |
|---|---|
| Can't connect to VPN | Restart device, check client version ≥ 6.2 |
| Forgot password | Use self-service reset portal |
| Slow laptop performance | Run the IT diagnostic tool (`nimbus-diag`) before raising a ticket |
| Printer not detected | Reconnect to office Wi-Fi, printers are not accessible via VPN |
| Zoom/Slack not working | Check status page at `status.nimbuscorp.internal` before raising a ticket — most outages are resolved centrally within 30 minutes |

## 6. Escalation

For urgent, business-critical outages (e.g., production system down, unable to access any company system), mark your ticket priority as "Critical." Critical tickets are reviewed within 30 minutes during business hours. Non-critical tickets are reviewed within 1 business day.

IT does not handle HR system access issues (e.g., payroll portal, benefits portal) — these are routed to HR Systems support instead.
