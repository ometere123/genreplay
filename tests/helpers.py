from __future__ import annotations

import base64
from typing import Any


TX_ID = "0x" + "11" * 32
ADDRESS_A = "0x" + "aa" * 20
ADDRESS_B = "0x" + "bb" * 20
VALIDATORS = ["0x" + f"{i:040x}" for i in range(1, 4)]
SOURCE = b"from genlayer import *\n\nclass Example(gl.Contract):\n    pass\n"
SOURCE_B64 = base64.b64encode(SOURCE).decode("ascii")


def receipt(
    *,
    status: str = "Finalized",
    execution: str = "FinishedWithReturn",
    rounds: int = 1,
) -> dict[str, Any]:
    data = []
    for round_number in range(rounds):
        data.append(
            {
                "round": round_number,
                "leaderIndex": 1,
                "votesCommitted": 3,
                "votesRevealed": 3,
                "appealBond": 0,
                "rotationsLeft": 0,
                "result": 1,
                "roundValidators": VALIDATORS,
                "validatorVotes": "AA==",
                "validatorVotesHash": ["0x01", "0x02", "0x03"],
                "validatorResultHash": ["0x04", "0x05", "0x06"],
            }
        )
    return {
        "id": TX_ID,
        "txOrigin": ADDRESS_A,
        "sender": ADDRESS_A,
        "recipient": ADDRESS_B,
        "status": 7 if status.lower() == "finalized" else 5,
        "statusName": status,
        "initialRotations": 1,
        "numOfInitialValidators": 3,
        "randomSeed": "0x" + "22" * 32,
        "txExecutionHash": "0x" + "33" * 32,
        "txCallData": "deadbeef",
        "result": 1,
        "txExecutionResult": 1 if execution == "FinishedWithReturn" else 2,
        "txExecutionResultName": execution,
        "epoch": 9,
        "fees": {"userValue": "0"},
        "readStateBlockRanges": [
            {"ActivationBlock": 100, "ProcessingBlock": 101, "ProposalBlock": 102}
        ],
        "roundData": data,
    }


def lifecycle(*, action: str = "NoOp") -> dict[str, Any]:
    return {
        "storedStatus": "Finalized",
        "storedStatusCode": 7,
        "projectedStatus": "Finalized",
        "projectedStatusCode": 7,
        "resolutionAction": action,
        "resolutionActionCode": 0,
        "resolutionSource": "FullReveal",
        "resolutionSourceCode": 6,
        "decisionId": "42",
        "decisionActive": True,
        "evaluatedAt": 1780000000,
    }


def trace(*, disagreement: int | None = None, eq_outputs: list[str] | None = None) -> dict[str, Any]:
    return {
        "transaction_id": TX_ID,
        "result_code": 0,
        "return_data": "0x00",
        "stdout": "",
        "stderr": "",
        "genvm_log": [],
        "storage_proof": "0x1234",
        "run_time": "12ms",
        "eq_outputs": eq_outputs if eq_outputs is not None else ["0x01", "0x02"],
        "nondetDisagreementCallNo": disagreement,
    }
