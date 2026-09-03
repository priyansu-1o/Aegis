import { useState } from "react";
import BalanceScreen from "./components/BalanceScreen";
import TransferForm from "./components/TransferForm";
import FDBreakFlow from "./components/FDBreakFlow";
import TransactionStatus from "./components/TransactionStatus";
import { saveTxId, clearTransaction } from "./utils/store";
import { submitTransfer } from "./utils/api";

// Senior user is seeded with user_id=2 in the backend.
const SENIOR_ID = 2;

function App() {
  // screens: 'balance' | 'transfer' | 'fdbreak' | 'status'
  const [screen, setScreen] = useState("balance");
  const [currentTx, setCurrentTx] = useState(null);
  const [apiError, setApiError] = useState(null);

  const handleBack = () => {
    setApiError(null);
    setScreen("balance");
  };

  const handleDone = () => {
    clearTransaction();
    setCurrentTx(null);
    setApiError(null);
    setScreen("balance");
  };

  /**
   * Called by TransferForm when the senior confirms a transfer.
   * Sends the real payload to POST /api/transfer.
   */
  const handleTransferSubmit = async (formData) => {
    setApiError(null);
    try {
      const result = await submitTransfer({
        sender_id:    SENIOR_ID,
        payee_name:   formData.payeeName,
        payee_account: formData.payeeAccount,
        amount:       formData.amount,
        note:         formData.note || "",
      });

      const tx = result.transaction;
      saveTxId(tx.tx_id);
      setCurrentTx({
        txId:            tx.tx_id,
        amount:          tx.amount,
        beneficiary:     tx.payee_name,
        riskReasons:     tx.risk_reasons,
        status:          tx.status,
        coolingOffExpiry: tx.cooling_off_expiry,
        transactionType: "transfer",
      });
      setScreen("status");
    } catch (err) {
      setApiError(err.message);
    }
  };

  /**
   * Called by FDBreakFlow when the senior confirms an FD break.
   * Routes through /api/transfer with preceded_by_fd_break=true.
   */
  const handleFDSubmit = async (formData) => {
    setApiError(null);
    try {
      const result = await submitTransfer({
        sender_id:             SENIOR_ID,
        payee_name:            "Savings Account",
        payee_account:         "0000004821",      // internal savings account
        amount:                formData.amount,
        note:                  "FD break — proceeds to savings",
        preceded_by_fd_break:  true,
        fd_break_timestamp:    new Date().toISOString(),
      });

      const tx = result.transaction;
      saveTxId(tx.tx_id);
      setCurrentTx({
        txId:            tx.tx_id,
        amount:          tx.amount,
        beneficiary:     "Savings Account · ····4821",
        riskReasons:     tx.risk_reasons,
        status:          tx.status,
        coolingOffExpiry: tx.cooling_off_expiry,
        transactionType: "fd_break",
      });
      setScreen("status");
    } catch (err) {
      setApiError(err.message);
    }
  };

  if (screen === "transfer") {
    return (
      <TransferForm
        onBack={handleBack}
        onSubmit={handleTransferSubmit}
        apiError={apiError}
      />
    );
  }

  if (screen === "fdbreak") {
    return (
      <FDBreakFlow
        onBack={handleBack}
        onSubmit={handleFDSubmit}
        apiError={apiError}
      />
    );
  }

  if (screen === "status") {
    return <TransactionStatus transaction={currentTx} onDone={handleDone} />;
  }

  return (
    <BalanceScreen
      onTransfer={() => { setApiError(null); setScreen("transfer"); }}
      onBreakFD={() => { setApiError(null); setScreen("fdbreak"); }}
    />
  );
}

export default App;