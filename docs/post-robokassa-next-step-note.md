# Next Step After Robokassa

Robokassa backend-hardening is done for now, and the website Telegram auth boundary is stable.

The next major step is the cabinet redesign, not Telegram Stars implementation yet.

Why this is the right next move:

- it lets us redesign the UI once instead of twice;
- it gives us a clean place to add a payment selector later;
- it keeps Robokassa as the current production path while leaving room for Stars;
- it prevents scope creep into payment-provider work before the cabinet UX is ready.

What the next phase should contain:

- a redesigned cabinet shell;
- explicit payment-state presentation;
- a reserved slot for future providers, especially Telegram Stars;
- no forced migration to Stars until the new UI is ready.

Revisit this decision when the cabinet redesign starts or when we are ready to add a second payment channel.
