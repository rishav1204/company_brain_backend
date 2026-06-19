from app.modules.erp.banking.services.transaction_service import TransactionService, transaction_service

BankTransactionService = TransactionService
bank_transaction_service = transaction_service

__all__ = ["BankTransactionService", "bank_transaction_service", "transaction_service"]
