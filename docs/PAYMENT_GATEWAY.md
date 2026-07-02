# ClickPesa Payment Gateway Guide

This guide explains how the VIKOBA system collects mobile-money payments,
records group funds, and releases approved loans through ClickPesa.

## Supported Flows

The integration supports:

- Member savings contributions
- Loan repayments
- Fine payments
- Mobile-money loan payouts
- ClickPesa payout previews and fees
- Transaction status polling
- Signed ClickPesa webhooks
- Decorated email and in-app transaction notifications

## Important Wallet Concepts

The system maintains two related records:

### Finance Group Wallet

The finance wallet is the group's accounting ledger. It is calculated from:

- Verified savings
- Fine payments
- Loan repayments
- Loan disbursements

It is used for reports, member analysis, and loan eligibility.

### Payment Group Wallet

The payment wallet tracks money received and released through the payment
gateway. Its balances are:

- `balance`: total gateway cash controlled by the group
- `available_balance`: cash currently available for a payout
- `reserved_balance`: cash held for a payout awaiting final confirmation

A loan payout requires enough money in both the finance wallet and payment
wallet.

## Environment Configuration

Add these variables to the backend environment:

```env
CLICKPESA_CLIENT_ID=your-client-id
CLICKPESA_API_KEY=your-api-key
CLICKPESA_CHECKSUM_KEY=your-checksum-key
CLICKPESA_SANDBOX=True
FRONTEND_URL=http://localhost:3000
```

Never commit real credentials to Git.

Use `CLICKPESA_SANDBOX=True` during development. For production:

```env
CLICKPESA_SANDBOX=False
```

Apply database migrations after configuring the application:

```bash
python manage.py migrate
```

## ClickPesa Webhook

Configure this application-level webhook in the ClickPesa dashboard:

```text
https://<backend-domain>/api/payments/webhook/clickpesa/
```

The endpoint:

- Does not require user authentication
- Requires a valid ClickPesa signature outside Django `DEBUG` mode
- Supports nested ClickPesa webhook payloads
- Prevents duplicate webhook processing
- Routes collection events and payout events separately

The checksum key must match the key configured for the ClickPesa application.

## Payment Collection Process

The frontend sends a collection request to:

```http
POST /api/payments/initiate/
```

Example:

```json
{
  "phone": "255712345678",
  "amount": "50000.00",
  "purpose": "CONTRIBUTION",
  "target_uuid": "contribution-uuid"
}
```

Supported purposes are:

- `CONTRIBUTION`
- `LOAN_REPAYMENT`
- `PENALTY_PAYMENT`

The backend performs the following steps:

1. Validates the phone number and amount.
2. Confirms that the target record exists.
3. Confirms that the member owns the contribution, loan, or fine.
4. Creates a pending `PaymentTransaction`.
5. Sends a ClickPesa USSD push request.
6. Waits for status polling or a signed webhook.
7. Credits the payment group wallet only after `SUCCESS`.
8. Records the successful action in the finance ledger.
9. Sends decorated email and in-app notifications.

For contributions, the gateway amount must exactly match the contribution
record. This prevents the payment wallet and finance wallet from disagreeing.

## Loan Payout Process

Only an active, verified group Treasurer can release an approved loan.

### Preview

```http
GET /api/payments/payouts/loans/<loan_uuid>/preview/
```

The preview returns:

- Borrower name
- Maskable mobile number
- Loan principal
- ClickPesa fee
- Total wallet debit
- Payment group wallet balance
- Finance group wallet balance
- ClickPesa account balance when supplied by the provider

The preview does not send money.

### Treasurer Confirmation

The Treasurer reviews the payout page and explicitly confirms the transaction:

```http
POST /api/payments/payouts/loans/<loan_uuid>/initiate/
```

Request:

```json
{
  "confirmed": true
}
```

The backend then:

1. Revalidates the loan and borrower.
2. Requests a fresh ClickPesa preview.
3. Calculates the principal, fee, and total debit.
4. Locks the group payment wallet.
5. Reserves the total debit.
6. Creates one loan-linked payout transaction.
7. Sends the real mobile-money payout request.
8. Waits for final ClickPesa confirmation.

The loan remains `APPROVED` while the payout is pending. It becomes `ACTIVE`
only when ClickPesa reports `SUCCESS`.

## Payout Status Handling

| ClickPesa status | System behavior |
| --- | --- |
| `AUTHORIZED` | Keep funds reserved and wait |
| `PENDING` | Keep funds reserved and wait |
| `PROCESSING` | Keep funds reserved and wait |
| `SUCCESS` | Debit reserved cash and activate the loan |
| `FAILED` | Restore reserved cash; loan stays approved |
| `REFUNDED` | Restore cash and mark the payout reversed |
| `REVERSED` | Restore cash and mark the payout reversed |

An ambiguous network timeout is treated as `PROCESSING`, not `FAILED`.
This prevents a Treasurer from retrying a payout that ClickPesa may already
have accepted.

## Transaction Status Polling

Authenticated involved members can check:

```http
GET /api/payments/status/<transaction_uuid>/
```

The endpoint refreshes pending transactions from ClickPesa when possible.
Webhooks remain the primary asynchronous confirmation mechanism.

## Security Rules

- Only Treasurers can initiate loan payouts.
- Explicit confirmation is required before a payout.
- Members can only pay their own contributions, loans, and fines.
- Unsupported payment purposes are rejected.
- Amounts must be positive.
- Contribution payments must match their contribution records.
- Wallet rows are locked while reserving or releasing funds.
- Active payout uniqueness prevents duplicate loan payouts.
- Webhook payloads are verified using HMAC-SHA256.
- Duplicate webhook deliveries are idempotent.
- Missing checksum configuration is rejected outside `DEBUG` mode.

## Notifications

Decorated email and in-app notifications are generated for:

- Collection initiated
- Collection succeeded
- Collection failed
- Loan payout initiated
- Loan payout succeeded
- Loan payout failed
- Loan payout reversed or refunded

Email delivery requires the Django email settings to be configured correctly.

## Safe Testing

Run backend checks and payment tests:

```bash
python manage.py check
python manage.py test apps.payments
python manage.py test apps.finance
```

Recommended sandbox test sequence:

1. Confirm `CLICKPESA_SANDBOX=True`.
2. Create a small pending contribution.
3. Complete the sandbox USSD request.
4. Confirm both wallet balances update after success.
5. Approve a small test loan.
6. Open the Treasurer payout confirmation page.
7. Review the fee and balances.
8. Confirm the payout.
9. Verify the loan remains approved while processing.
10. Verify it becomes active only after `SUCCESS`.

Never test production payouts using a large amount.

## Production Checklist

- [ ] Production ClickPesa credentials are stored securely
- [ ] `CLICKPESA_SANDBOX=False`
- [ ] `DEBUG=False`
- [ ] `CLICKPESA_CHECKSUM_KEY` is configured
- [ ] HTTPS is enabled
- [ ] The ClickPesa webhook URL is registered
- [ ] Database migrations are applied
- [ ] Email delivery is configured
- [ ] A small collection test succeeds
- [ ] A small payout test succeeds
- [ ] Transaction emails are received
- [ ] Wallet balances match the ClickPesa dashboard
- [ ] Treasurer permissions have been reviewed

## Troubleshooting

### Payout preview is unavailable

Check:

- ClickPesa credentials
- Sandbox or production mode
- Internet connectivity
- Borrower phone number format
- ClickPesa account permissions

### Insufficient group ClickPesa wallet

The finance ledger may show funds that were recorded manually but are not held
by ClickPesa. Only gateway-backed cash can be released through a real payout.

### Payout remains processing

Check:

- ClickPesa payout status by the transaction reference
- Webhook URL and HTTPS certificate
- Checksum key
- Backend logs
- ClickPesa dashboard events

Do not manually retry until the original payout status is known.

### Webhook returns an invalid signature error

Confirm:

- The dashboard and backend use the same checksum key
- The `X-ClickPesa-Signature` header reaches Django
- A proxy is not modifying the JSON body
- The request is being sent to the correct environment

### Email was not received

Check Django email settings, spam folders, backend logs, and the recipient's
stored email address.

## Relevant Code

- `apps/payments/gateway/clickpesa.py`
- `apps/payments/services/collection_service.py`
- `apps/payments/services/payout_service.py`
- `apps/payments/services/webhook_service.py`
- `apps/payments/services/payment_notification_service.py`
- `apps/payments/views/payment.py`
- `apps/payments/views/webhook.py`
- `apps/finance/services/loan_service.py`

Frontend Treasurer confirmation page:

```text
frontend/src/app/(protected)/(user)/(groups)/group/[groupId]/loans/[loanId]/payout/page.tsx
```

## Official ClickPesa Documentation

- Mobile Money Payments:
  <https://docs.clickpesa.com/payment-api/mobile-money-payment-api/mobile-money-payment-api-overview>
- Mobile Money Payouts:
  <https://docs.clickpesa.com/payout-api/mobile-money-payout-api/mobile-money-payout-api-overview>
- Webhooks:
  <https://docs.clickpesa.com/home/webhooks>
- Checksums:
  <https://docs.clickpesa.com/home/checksum>
- Payout Statuses:
  <https://docs.clickpesa.com/home/payout-status>
