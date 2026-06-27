# Robokassa Payment Pipeline

## Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant Frontend as Frontend
    participant Backend as FastAPI Backend
    database DB as Postgres / preorders
    participant Robokassa as Robokassa
    participant NPD as RoboReceipts SMZ / My Tax

    User->>Frontend: Enters email and clicks "Prepay"
    Frontend->>Backend: POST /payments/preorders
    Backend->>DB: INSERT preorder<br/>status=pending
    DB-->>Backend: preorder_id, invoice_id
    Backend->>Backend: Builds SignatureValue<br/>Password #1
    Backend-->>Frontend: confirmation_url

    Frontend->>Robokassa: Redirects to payment form
    User->>Robokassa: Pays by card / SBP / pay service

    Robokassa->>Backend: POST /payments/robokassa/result<br/>OutSum, InvId, SignatureValue
    Backend->>Backend: Verifies SignatureValue<br/>Password #2
    Backend->>DB: SELECT preorder by invoice_id
    DB-->>Backend: amount_value, status
    Backend->>Backend: Verifies amount
    Backend->>DB: UPDATE preorder<br/>status=paid<br/>tax_receipt_status=pending_provider
    Backend-->>Robokassa: OK&lt;InvId&gt;

    Robokassa->>NPD: Issues NPD receipt<br/>via RoboReceipts SMZ
    NPD-->>User: Sends receipt to buyer

    Frontend->>Backend: GET /payments/preorders/{preorder_id}
    Backend->>DB: SELECT preorder status
    DB-->>Backend: paid / pending
    Backend-->>Frontend: status, tax_receipt_status
    Frontend-->>User: Shows payment result
```

## State Diagram

```mermaid
stateDiagram-v2
    [*] --> Pending: POST /payments/preorders

    Pending: status=pending
    Pending: tax_receipt_status=pending_payment

    Pending --> Paid: Robokassa ResultURL<br/>signature ok + amount ok
    Pending --> PaymentCreateFailed: Payment URL creation failed
    Pending --> Canceled: FailURL / manual cancellation

    Paid: status=paid
    Paid: tax_receipt_status=pending_provider

    Paid --> ReceiptIssued: RoboReceipts SMZ issued receipt
    Paid --> ReceiptFailed: Receipt issue failed / manual review needed

    ReceiptIssued: tax_receipt_status=issued
    ReceiptFailed: tax_receipt_status=failed
    PaymentCreateFailed: status=payment_create_failed
    Canceled: status=canceled

    ReceiptIssued --> [*]
    ReceiptFailed --> [*]
    PaymentCreateFailed --> [*]
    Canceled --> [*]
```
