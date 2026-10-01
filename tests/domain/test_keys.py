"""Key recovery from signed C-Chain transactions, on two real transactions read from Routescan on 2026-10-01."""

from __future__ import annotations

import pytest

from avalanche_research.core.errors import DataError
from avalanche_research.domain import keys

# BENQI's sAVAX withdraw call 0x2259372f…fc53, an EIP-1559 transaction.
BENQI = {"type": "0x2", "chainId": "0xa86a", "nonce": "0x31a9b", "gasPrice": "0x1a13b8600", "maxPriorityFeePerGas": "0x77359400", "maxFeePerGas": "0x1a13b8600", "gas": "0x249f0", "to": "0x2b2c81e08f1af8835a78bb2a90ae924ace0ea4be", "value": "0x0", "input": "0x2e1a7d4d00000000000000000000000000000000000000000000000300be977eab57a200", "v": "0x1", "r": "0xd125867cf05fd69febb1aba9d99d9d38063581bb2b094129e7a8d7c29e8b5c93", "s": "0x1f25e0c5090e5c5737e8c08b6d04fef0adaba6436f3f1a87a619f3a327cd4f9a", "from": "0x565f0fe9715e3cb0df579f186c299d6707887e83", "accessList": []}
# The first outbound transaction of a wallet on Bitwise's BAVA page, 0x5f7f6adf…2620, a legacy EIP-155 transaction.
BAVA = {"type": "0x0", "chainId": "0xa86a", "nonce": "0x0", "gasPrice": "0x2a00d88", "gas": "0x5208", "to": "0xf4535ecfcb11fb1fc93d2a78cd00ef270a4bea93", "value": "0x7f3385f5f24ea194000", "input": "0x", "v": "0x150f7", "r": "0x6825f17ced6fbd38fddfad4fc0814556c2402bcf2ba1f34be6e8385716c98a3c", "s": "0x1726f178259ad7b372c3fc00b40f9c6a9b35906bdc06554c2267f63184580360", "from": "0x6181ed1d30050df3cdfe6f3444fa51f20640badd"}


def test_keccak_is_ethereums():
    assert keys.keccak256(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"


@pytest.mark.parametrize(("transaction", "p_chain"), [
    (BENQI, "avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy"),
    (BAVA, "avax13h7989asv3wjmh9gfaklyvtwuyg8mwwzh0fve4"),
])
def test_the_signer_has_the_p_chain_address(transaction, p_chain):
    found = keys.addresses(transaction)
    assert found == {"evm": transaction["from"].lower(), "p_chain": p_chain}


def test_a_changed_transaction_is_refused():
    with pytest.raises(DataError, match="not the sender"):
        keys.addresses({**BAVA, "value": hex(int(BAVA["value"], 16) + 1)})
    with pytest.raises(DataError, match="unsupported"):
        keys.addresses({**BAVA, "type": "0x1"})
